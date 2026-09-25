"""LinkedIn Autopost: a small Flask dashboard for PythonAnywhere.

First visit → set an admin password and paste the LinkedIn app's Client ID and
Secret. Then click "Connect LinkedIn" once (repeat every 60 days), and manage
the post queue from the browser. A PythonAnywhere scheduled task running
`post.py --scheduled` publishes on the chosen weekdays.
"""
import re
import secrets
import time
import urllib.parse
import urllib.request
import json
from datetime import datetime
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import post as lp

app = Flask(__name__)
cfg = lp.load_config()
if not cfg.get("secret_key"):
    cfg["secret_key"] = secrets.token_hex(32)
    lp.save_config(cfg)
app.secret_key = cfg["secret_key"]
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=8 * 1024 * 1024)

SCOPES = "openid profile w_member_social"

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>LinkedIn Autopost</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg"><meta name="theme-color" content="#0A66C2">
<style>
:root{--bg:#f6f3ee;--card:#fff;--ink:#16130d;--muted:#6b645a;--line:#e4ddd2;--accent:#0a66c2;--ok:#12805c;--bad:#c0392b}
@media (prefers-color-scheme:dark){:root{--bg:#16130d;--card:#221e17;--ink:#f3eee6;--muted:#a79f92;--line:#3a342a;--accent:#70b5f9;--ok:#4cc38a;--bad:#ff7b6b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 16px}h2{font-size:17px;margin:0 0 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
input,textarea,select{width:100%;padding:9px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}
textarea{min-height:320px}label{display:block;font-weight:600;margin:10px 0 4px}
button,.btn{display:inline-block;background:var(--accent);color:#fff;border:0;border-radius:8px;padding:9px 16px;font:inherit;font-weight:600;cursor:pointer;text-decoration:none}
.btn.light,button.light{background:transparent;color:var(--accent);border:1px solid var(--accent)}button.danger{background:var(--bad)}
.muted{color:var(--muted);font-size:13px}.ok{color:var(--ok)}.bad{color:var(--bad)}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.flash{padding:10px 14px;border-radius:8px;margin-bottom:12px;background:var(--card);border-left:4px solid var(--accent)}
pre{white-space:pre-wrap;font:inherit;margin:8px 0}ol{padding-left:20px}li{margin:6px 0}code{word-break:break-all}
img.prev{max-width:100%;border-radius:8px;border:1px solid var(--line)}.days label{display:inline-flex;gap:4px;font-weight:400;margin-right:10px}.days input{width:auto}
</style></head><body><main>
<div class="row" style="justify-content:space-between"><h1>LinkedIn Autopost</h1>
{% if session.get('admin') %}<form method="post" action="{{ url_for('logout') }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="light">Log out</button></form>{% endif %}</div>
{% for cat, msg in get_flashed_messages(with_categories=true) %}<div class="flash {{ cat }}">{{ msg }}</div>{% endfor %}
{{ body|safe }}
</main></body></html>"""


def render(template, **ctx):
    ctx["csrf"] = csrf_token()
    inner = render_template_string(template, **ctx)
    return render_template_string(PAGE, body=inner, csrf=ctx["csrf"])


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


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


# ---------- setup and login ----------

@app.route("/setup", methods=["GET", "POST"])
def setup():
    c = lp.load_config()
    if c.get("admin_hash") and not session.get("admin"):
        return redirect(url_for("login"))
    first_run = not c.get("admin_hash")
    if request.method == "POST":
        if first_run and c.get("setup_code") and request.form.get("setup_code", "").strip() != c["setup_code"]:
            time.sleep(1)
            flash("Wrong setup code.", "bad")
            return redirect(url_for("setup"))
        pw = request.form.get("password", "")
        if not c.get("admin_hash") and len(pw) < 8:
            flash("Choose a password of at least 8 characters.", "bad")
            return redirect(url_for("setup"))
        if pw:
            c["admin_hash"] = generate_password_hash(pw)
        for key in ("client_id", "client_secret", "api_version"):
            value = request.form.get(key, "").strip()
            if value:
                c[key] = value
        c["post_days"] = request.form.getlist("days") or ["Tue", "Thu"]
        c.pop("setup_code", None)
        lp.save_config(c)
        session["admin"] = True
        flash("Settings saved.", "ok")
        return redirect(url_for("dashboard"))
    return render("""
<div class="card"><h2>{{ 'Settings' if c.admin_hash else 'First-time setup' }}</h2>
<p class="muted">In your LinkedIn app → <b>Auth</b> tab → <b>Authorized redirect URLs</b>, add exactly:<br><code>{{ redirect }}</code></p>
<form method="post"><input type="hidden" name="csrf" value="{{ csrf }}">
{% if not c.admin_hash and c.setup_code %}<label>Setup code (you got it from Claude)</label><input name="setup_code" autocomplete="off">{% endif %}
<label>Admin password for this dashboard{% if c.admin_hash %} (leave empty to keep){% endif %}</label><input type="password" name="password" autocomplete="new-password">
<label>LinkedIn Client ID{% if c.client_id %} (saved, leave empty to keep){% endif %}</label><input name="client_id" autocomplete="off">
<label>LinkedIn Client Secret{% if c.client_secret %} (saved, leave empty to keep){% endif %}</label><input type="password" name="client_secret" autocomplete="off">
<label>Posting days (the scheduled task publishes 1 post on each)</label>
<div class="days">{% for d in days %}<label><input type="checkbox" name="days" value="{{ d }}" {{ 'checked' if d in c.get('post_days', ['Tue','Thu']) }}>{{ d }}</label>{% endfor %}</div>
<label>LinkedIn API version (optional, YYYYMM; leave empty for automatic)</label><input name="api_version" placeholder="{{ c.get('api_version') or 'automatic' }}">
<p><button>Save</button></p></form></div>""", c=c, redirect=redirect_uri(), days=lp.WEEKDAYS)


@app.route("/login", methods=["GET", "POST"])
def login():
    c = lp.load_config()
    if not c.get("admin_hash"):
        return redirect(url_for("setup"))
    if request.method == "POST":
        time.sleep(1)  # slow down password guessing
        if check_password_hash(c["admin_hash"], request.form.get("password", "")):
            session["admin"] = True
            return redirect(url_for("dashboard"))
        flash("Wrong password.", "bad")
    return render("""<div class="card"><h2>Log in</h2><form method="post"><input type="hidden" name="csrf" value="{{ csrf }}">
<label>Password</label><input type="password" name="password" autofocus><p><button>Log in</button></p></form></div>""")


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
        flash("Add the Client ID and Secret in Settings first.", "bad")
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
        return redirect(url_for("dashboard"))
    if not request.args.get("state") or request.args.get("state") != session.pop("oauth_state", None):
        flash("Login expired, please click Connect LinkedIn again.", "bad")
        return redirect(url_for("dashboard"))
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
        return redirect(url_for("dashboard"))
    c.update(access_token=token["access_token"], expires_at=time.time() + token.get("expires_in", 0),
             person_urn=f"urn:li:person:{me['sub']}", person_name=me.get("name", ""))
    lp.save_config(c)
    flash(f"Connected as {c['person_name']}.", "ok")
    return redirect(url_for("dashboard"))


# ---------- dashboard and queue ----------

@app.route("/")
@admin_required
def dashboard():
    c = lp.load_config()
    days_left = int((c.get("expires_at", 0) - time.time()) // 86400) if c.get("access_token") else None
    queue = [(p.name, *lp.read_post(p)) for p in lp.queued()]
    published = sorted(lp.PUBLISHED.glob("*.md"), reverse=True) if lp.PUBLISHED.exists() else []
    published = [lp.read_post(p)[0] for p in published]
    return render("""
<div class="card"><h2>LinkedIn connection</h2>
{% if days_left is none %}<p class="bad">Not connected.</p>
{% elif days_left < 0 %}<p class="bad">Login expired. Reconnect to keep posting.</p>
{% else %}<p class="{{ 'bad' if days_left < 7 else 'ok' }}">Connected as <b>{{ c.person_name }}</b>, valid for {{ days_left }} more days (until {{ until }}).</p>{% endif %}
<div class="row"><form method="post" action="{{ url_for('connect') }}"><input type="hidden" name="csrf" value="{{ csrf }}">
<button>{{ 'Reconnect' if c.access_token else 'Connect' }} LinkedIn</button></form>
<a class="btn light" href="{{ url_for('setup') }}">Settings</a></div>
<p class="muted">Posting days: {{ c.get('post_days', ['Tue','Thu'])|join(', ') }}. On those days, the first post in the queue is published automatically after 09:00 Iraq time.</p></div>

<div class="card"><div class="row" style="justify-content:space-between"><h2>Queue ({{ queue|length }})</h2>
<a class="btn light" href="{{ url_for('edit', name='new') }}">+ New post</a></div>
{% if queue %}<form method="post" action="{{ url_for('publish_now') }}" onsubmit="return confirm('Publish the next post to LinkedIn now?')">
<input type="hidden" name="csrf" value="{{ csrf }}"><button>Publish next post now</button></form>{% endif %}
<ol>{% for name, meta, body in queue %}<li><a href="{{ url_for('edit', name=name) }}"><b>{{ meta.title or name }}</b></a>
<span class="muted">· {{ 'image' if meta.image else 'no image' }}{{ ' · comment link' if meta.comment }}</span>
{% if loop.first %}<pre class="muted">{{ body[:280] }}…</pre>{% endif %}</li>{% else %}<p class="muted">Empty. Add a post.</p>{% endfor %}</ol></div>

<div class="card"><h2>Published ({{ published|length }})</h2><ul>{% for m in published %}
<li>{{ m.published }} · <a href="https://www.linkedin.com/feed/update/{{ m.post_urn }}/" target="_blank" rel="noopener">{{ m.title }}</a></li>
{% else %}<p class="muted">Nothing yet.</p>{% endfor %}</ul></div>""",
                  c=c, days_left=days_left, queue=queue, published=published,
                  until=datetime.fromtimestamp(c.get("expires_at", 0)).strftime("%Y-%m-%d"))


@app.route("/publish", methods=["POST"])
@admin_required
def publish_now():
    queue = lp.queued()
    if not queue:
        flash("Queue is empty.", "bad")
        return redirect(url_for("dashboard"))
    try:
        url, warning = lp.publish(queue[0])
        flash(f"Published! {url}", "ok")
        if warning:
            flash(warning, "bad")
    except lp.LinkedInError as err:
        flash(str(err), "bad")
    return redirect(url_for("dashboard"))


@app.route("/post/<name>", methods=["GET", "POST"])
@admin_required
def edit(name):
    is_new = name == "new"
    path = None if is_new else safe_queue_path(name)
    meta, body = ({"title": "", "image": "", "comment": ""}, "") if is_new else lp.read_post(path)
    if request.method == "POST":
        if request.form.get("action") == "delete" and path:
            path.unlink()
            flash("Post deleted.", "ok")
            return redirect(url_for("dashboard"))
        meta["title"] = request.form.get("title", "").strip().replace("\n", " ") or "Untitled"
        meta["comment"] = request.form.get("comment", "").strip().replace("\n", " ")
        body = request.form.get("body", "").replace("\r\n", "\n")
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
        if is_new:
            nums = [int(p.name[:2]) for p in lp.QUEUE.glob("*.md") if p.name[:2].isdigit()]
            slug = re.sub(r"[^a-z0-9]+", "-", meta["title"].lower()).strip("-")[:40] or "post"
            lp.QUEUE.mkdir(exist_ok=True)
            path = lp.QUEUE / f"{max(nums, default=0) + 1:02d}-{slug}.md"
        lp.write_post(path, meta, body)
        flash("Saved.", "ok")
        return redirect(url_for("dashboard"))
    return render("""
<div class="card"><h2>{{ 'New post' if is_new else 'Edit post' }}</h2>
<form method="post" enctype="multipart/form-data"><input type="hidden" name="csrf" value="{{ csrf }}">
<label>Title (only for you)</label><input name="title" value="{{ meta.title }}">
<label>Post text <span class="muted" id="count"></span></label><textarea name="body" id="body">{{ body }}</textarea>
<label>First comment (put links here)</label><input name="comment" value="{{ meta.comment }}">
<label>Image (JPG / PNG / GIF)</label>
{% if meta.image %}<img class="prev" src="{{ url_for('image', name=meta.image.split('/')[-1]) }}" alt="">
<label style="font-weight:400"><input type="checkbox" name="remove_image" style="width:auto"> Remove image</label>{% endif %}
<input type="file" name="image" accept=".jpg,.jpeg,.png,.gif">
<p class="row"><button>Save</button><a class="btn light" href="{{ url_for('dashboard') }}">Cancel</a>
{% if not is_new %}<button class="danger" name="action" value="delete" onclick="return confirm('Delete this post?')">Delete</button>{% endif %}</p>
</form></div>
<script>const b=document.getElementById('body'),c=document.getElementById('count');
const u=()=>c.textContent=`(${b.value.length} / 3000)`;b.addEventListener('input',u);u();</script>""",
                  meta=meta, body=body, is_new=is_new)


@app.route("/image/<name>")
@admin_required
def image(name):
    from flask import send_from_directory
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
