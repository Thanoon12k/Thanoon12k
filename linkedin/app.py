"""LinkedIn Autopost: a small Flask dashboard for PythonAnywhere.

First visit → set an admin password and paste the LinkedIn app's Client ID and
Secret (Setup). Click "Connect LinkedIn" once (repeat every 60 days), then write
and order posts from the browser. GitHub Actions calls /cron hourly and the app
publishes at most one post on each posting day, at the chosen hour.
"""
import json
import re
import secrets
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, abort, flash, redirect, render_template, request, send_from_directory,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import post as lp
import profile_kit

app = Flask(__name__)
_cfg = lp.load_config()
if not _cfg.get("secret_key"):
    _cfg["secret_key"] = secrets.token_hex(32)
    lp.save_config(_cfg)
app.secret_key = _cfg["secret_key"]
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=8 * 1024 * 1024)

SCOPES = "openid profile w_member_social"
IRAQ = timezone(timedelta(hours=3))
DEFAULT_HEADLINE = "Full-Stack Developer · Flutter & Django"


# ---------- helpers ----------

@app.template_filter("linkify")
def linkify(text):
    """Escape text, then turn https:// URLs into links."""
    from markupsafe import Markup, escape
    return Markup(re.sub(r"(https://[^\s<]+)", r'<a href="\1" target="_blank" rel="noopener">open ↗</a>',
                         str(escape(text))))


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


@app.context_processor
def inject():
    c = lp.load_config()
    days_left = int((c.get("expires_at", 0) - time.time()) // 86400) if c.get("access_token") else None
    return {"csrf": csrf_token(), "cfg": c, "days_left": days_left,
            "queue_count": len(lp.queued()), "endpoint": request.endpoint}


@app.before_request
def check_csrf():
    if request.method == "POST" and request.form.get("csrf") != session.get("csrf"):
        abort(400, "Form expired, go back and try again.")


def admin_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not lp.load_config().get("admin_hash"):
            return redirect(url_for("setup"))
        if not session.get("admin"):
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def redirect_uri():
    return url_for("callback", _external=True, _scheme="https")


def safe_queue_path(name):
    if not re.fullmatch(r"[\w.-]+\.md", name or ""):
        abort(404)
    path = lp.QUEUE / name
    if not path.exists():
        abort(404)
    return path


def post_hour(c):
    """Posting hour in Iraq time."""
    return int(c.get("post_hour_local", 9))


def upcoming_slots(c, count):
    """The next `count` posting times (Iraq time), skipping today if it's used or past."""
    days = c.get("post_days", ["Tue", "Thu"])
    if not days:
        return [None] * count
    # Today still counts until a post goes out: the hourly cron publishes at or after the hour.
    slot = datetime.now(IRAQ).replace(hour=post_hour(c), minute=0, second=0, microsecond=0)
    if lp.published_today():
        slot += timedelta(days=1)
    slots = []
    while len(slots) < count:
        if lp.WEEKDAYS[slot.weekday()] in days:
            slots.append(slot)
        slot += timedelta(days=1)
    return slots


def queue_items(c):
    paths = lp.queued()
    items = []
    for path, slot in zip(paths, upcoming_slots(c, len(paths))):
        meta, body = lp.read_post(path)
        items.append({"name": path.name, "meta": meta, "body": body, "slot": slot})
    return items


def published_items():
    if not lp.PUBLISHED.exists():
        return []
    items = []
    for path in lp.PUBLISHED.glob("*.md"):
        meta, body = lp.read_post(path)
        items.append({"name": path.name, "meta": meta, "body": body})
    return sorted(items, key=lambda i: (i["meta"].get("published", ""), i["name"]), reverse=True)


def renumber(paths):
    """Rename queue files to 01-, 02-, … in the given order."""
    temp = []
    for i, path in enumerate(paths):
        tmp = path.with_name(f".tmp{i}-{path.name}")
        path.rename(tmp)
        temp.append(tmp)
    for i, tmp in enumerate(temp, 1):
        slug = re.sub(r"^\.tmp\d+-(\d+-)?", "", tmp.name)
        tmp.rename(lp.QUEUE / f"{i:02d}-{slug}")


def try_publish(path):
    try:
        url, warning = lp.publish(path)
        flash(f"Published to LinkedIn ✓ {url}", "ok")
        if warning:
            flash(warning, "bad")
        return True
    except lp.LinkedInError as err:
        flash(str(err), "bad")
    except Exception as err:  # never show a bare 500 page
        app.logger.exception("publish failed")
        flash(f"Unexpected error: {err!r}", "bad")
    return False


# ---------- setup and login ----------

@app.route("/setup", methods=["GET", "POST"])
def setup():
    c = lp.load_config()
    first_run = not c.get("admin_hash")
    if not first_run and not session.get("admin"):
        return redirect(url_for("login"))
    if request.method == "POST":
        if first_run and c.get("setup_code") and request.form.get("setup_code", "").strip() != c["setup_code"]:
            time.sleep(1)
            flash("Wrong setup code.", "bad")
            return redirect(url_for("setup"))
        pw = request.form.get("password", "")
        if first_run and len(pw) < 8:
            flash("Choose a password of at least 8 characters.", "bad")
            return redirect(url_for("setup"))
        if pw:
            if len(pw) < 8:
                flash("Passwords need at least 8 characters.", "bad")
                return redirect(url_for("setup"))
            c["admin_hash"] = generate_password_hash(pw)
        for key in ("client_id", "client_secret", "api_version"):
            value = request.form.get(key, "").strip()
            if value:
                c[key] = value
        c["headline"] = request.form.get("headline", "").strip() or c.get("headline", "")
        if "days_form" in request.form:
            c["post_days"] = request.form.getlist("days")
            hour = request.form.get("hour", "9")
            c["post_hour_local"] = int(hour) if hour.isdigit() and 0 <= int(hour) <= 23 else 9
            c["post_hour_utc"] = (c["post_hour_local"] - 3) % 24
        c.pop("setup_code", None)
        lp.save_config(c)
        session["admin"] = True
        flash("Settings saved ✓", "ok")
        return redirect(url_for("setup") if not first_run else url_for("overview"))
    return render_template("setup.html", first_run=first_run, redirect_uri=redirect_uri(),
                           weekdays=lp.WEEKDAYS, default_headline=DEFAULT_HEADLINE)


@app.route("/login", methods=["GET", "POST"])
def login():
    c = lp.load_config()
    if not c.get("admin_hash"):
        return redirect(url_for("setup"))
    if request.method == "POST":
        time.sleep(1)  # slow down password guessing
        if check_password_hash(c["admin_hash"], request.form.get("password", "")):
            session["admin"] = True
            return redirect(url_for("overview"))
        flash("Wrong password.", "bad")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- LinkedIn OAuth ----------

@app.route("/connect", methods=["POST"])
@admin_required
def connect():
    c = lp.load_config()
    if not (c.get("client_id") and c.get("client_secret")):
        flash("Add the Client ID and Secret first.", "bad")
        return redirect(url_for("setup"))
    session["oauth_state"] = secrets.token_urlsafe(16)
    return redirect("https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": c["client_id"], "redirect_uri": redirect_uri(),
        "state": session["oauth_state"], "scope": SCOPES}))


@app.route("/callback")
@admin_required
def callback():
    if request.args.get("error"):
        flash(f"LinkedIn refused: {request.args.get('error_description') or request.args['error']}", "bad")
        return redirect(url_for("setup"))
    if not request.args.get("state") or request.args.get("state") != session.pop("oauth_state", None):
        flash("Login expired, please click Connect LinkedIn again.", "bad")
        return redirect(url_for("setup"))
    c = lp.load_config()
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": request.args["code"], "redirect_uri": redirect_uri(),
        "client_id": c["client_id"], "client_secret": c["client_secret"]}).encode()
    try:
        with urllib.request.urlopen("https://www.linkedin.com/oauth/v2/accessToken", data, timeout=30) as r:
            token = json.load(r)
        req = urllib.request.Request("https://api.linkedin.com/v2/userinfo",
                                     headers={"Authorization": f"Bearer {token['access_token']}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            me = json.load(r)
    except Exception as err:  # show LinkedIn's reason instead of a 500 page
        detail = err.read().decode(errors="replace") if hasattr(err, "read") else str(err)
        flash(f"Connecting failed: {detail}", "bad")
        return redirect(url_for("setup"))
    c.update(access_token=token["access_token"], expires_at=time.time() + token.get("expires_in", 0),
             person_urn=f"urn:li:person:{me['sub']}", person_name=me.get("name", ""),
             picture=me.get("picture", ""))
    lp.save_config(c)
    flash(f"Connected as {c['person_name']} ✓", "ok")
    return redirect(url_for("overview"))


# ---------- pages ----------

@app.route("/")
@admin_required
def overview():
    c = lp.load_config()
    queue = queue_items(c)
    return render_template("overview.html", queue=queue, next_post=queue[0] if queue else None,
                           published=published_items(), post_hour=post_hour(c))


@app.route("/posts")
@admin_required
def posts():
    return render_template("posts.html", queue=queue_items(lp.load_config()), published=published_items(),
                           tab=request.args.get("tab", "queue"))


@app.route("/posts/move", methods=["POST"])
@admin_required
def move():
    paths = lp.queued()
    names = [p.name for p in paths]
    name, direction = request.form.get("name"), request.form.get("dir")
    if name not in names:
        abort(404)
    i = names.index(name)
    j = {"up": i - 1, "down": i + 1, "top": 0}.get(direction, i)
    if 0 <= j < len(paths) and j != i:
        paths.insert(j, paths.pop(i))
        renumber(paths)
    return redirect(url_for("posts"))


@app.route("/posts/publish", methods=["POST"])
@admin_required
def publish_now():
    name = request.form.get("name")
    queue = lp.queued()
    if not queue:
        flash("The queue is empty.", "bad")
        return redirect(url_for("overview"))
    path = safe_queue_path(name) if name else queue[0]
    try_publish(path)
    renumber(lp.queued())
    return redirect(request.form.get("next") or url_for("overview"))


@app.route("/compose", defaults={"name": None}, methods=["GET", "POST"])
@app.route("/compose/<name>", methods=["GET", "POST"])
@admin_required
def compose(name):
    path = safe_queue_path(name) if name else None
    meta, body = lp.read_post(path) if path else ({"title": "", "image": "", "comment": ""}, "")
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "delete" and path:
            path.unlink()
            renumber(lp.queued())
            flash("Post deleted.", "ok")
            return redirect(url_for("posts"))
        body = request.form.get("body", "").replace("\r\n", "\n").strip()
        if not body:
            flash("Write something first.", "bad")
            return redirect(request.url)
        meta["title"] = request.form.get("title", "").strip().replace("\n", " ") or body.split("\n")[0][:60]
        meta["comment"] = request.form.get("link", "").strip().replace("\n", " ")
        if request.form.get("remove_image"):
            meta["image"] = ""
        upload = request.files.get("image")
        if upload and upload.filename:
            ext = upload.filename.rsplit(".", 1)[-1].lower()
            if ext not in ("jpg", "jpeg", "png", "gif"):
                flash("Images must be JPG, PNG or GIF.", "bad")
                return redirect(request.url)
            fname = f"{int(time.time())}-{secure_filename(upload.filename)}"
            lp.IMAGES.mkdir(exist_ok=True)
            upload.save(lp.IMAGES / fname)
            meta["image"] = f"images/{fname}"
        if not path:
            lp.QUEUE.mkdir(exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-", meta["title"].lower()).strip("-")[:40] or "post"
            path = lp.QUEUE / f"{int(time.time())}-{slug}.md"
            position = request.form.get("position", "end")
            lp.write_post(path, meta, body)
            paths = [p for p in lp.queued() if p != path]
            paths.insert(0 if position in ("top", "now") else len(paths), path)
            renumber(paths)
            path = lp.queued()[0] if position in ("top", "now") else lp.queued()[-1]
        else:
            lp.write_post(path, meta, body)
        if action == "publish":
            try_publish(path)
            renumber(lp.queued())
            return redirect(url_for("overview"))
        flash("Saved to the queue ✓", "ok")
        return redirect(url_for("posts"))
    return render_template("compose.html", name=name, meta=meta, body=body,
                           image_url=url_for("image", name=meta["image"].split("/")[-1]) if meta.get("image") else "")


@app.route("/profile")
@admin_required
def profile():
    return render_template("profile.html", steps=profile_kit.STEPS)


@app.route("/image/<name>")
@admin_required
def image(name):
    return send_from_directory(lp.IMAGES, secure_filename(name))


@app.route("/favicon.svg")
@app.route("/favicon.ico")
def favicon():
    return app.response_class((lp.HERE / "favicon.svg").read_bytes(), mimetype="image/svg+xml",
                              headers={"Cache-Control": "public, max-age=604800"})


@app.route("/cron")
def cron():
    # Public on purpose: it only publishes what the schedule would anyway, once per posting day.
    try:
        return lp.run_scheduled() + "\n", 200, {"Content-Type": "text/plain; charset=utf-8"}
    except lp.LinkedInError as err:
        return f"Error: {err}\n", 500, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/health")
def health():
    return "ok"
