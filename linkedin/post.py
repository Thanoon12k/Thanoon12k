"""LinkedIn publishing: shared by the web app (app.py) and the scheduled task.

Scheduling: GitHub Actions (.github/workflows/linkedin-cron.yml) calls the web
app's /cron URL daily; run_scheduled() publishes at most one post per posting
day, so extra calls are harmless. `post.py --scheduled` does the same from a shell.

    python3 linkedin/post.py --dry-run   # show the next post, publish nothing
    python3 linkedin/post.py --now       # publish the next post right away

Queue files in linkedin/queue/ are published in file-name order; each published
file moves to linkedin/published/ with the post URN and date added.
Settings and the access token live in linkedin/data/config.json (never committed).
"""
import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUEUE = HERE / "queue"
PUBLISHED = HERE / "published"
IMAGES = HERE / "images"
CONFIG = HERE / "data" / "config.json"
API = "https://api.linkedin.com/rest"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class LinkedInError(Exception):
    pass


def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save_config(cfg):
    CONFIG.parent.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    CONFIG.chmod(0o600)


def api_version(cfg):
    if cfg.get("api_version"):
        return cfg["api_version"]
    # LinkedIn keeps each monthly API version for about a year; use one from 2 months ago.
    today = date.today()
    months = today.year * 12 + today.month - 1 - 2
    return f"{months // 12}{months % 12 + 1:02d}"


def read_post(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    meta = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, match.group(2).strip()


def write_post(path, meta, body):
    head = "".join(f"{k}: {v}\n" for k, v in meta.items())
    path.write_text(f"---\n{head}---\n{body.strip()}\n", encoding="utf-8")


def queued():
    return sorted(QUEUE.glob("*.md"))


def to_little_text(text):
    """Escape LinkedIn's reserved characters; turn #Word into a real hashtag."""
    escaped = re.sub(r"([\\|{}@\[\]()<>#*_~])", r"\\\1", text)
    return re.sub(r"\\#(\w+)", r"{hashtag|\\#|\1}", escaped)


def _call(cfg, method, url, body=None):
    headers = {
        "Authorization": f"Bearer {cfg['access_token']}",
        "LinkedIn-Version": api_version(cfg),
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read()
            return resp.headers, (json.loads(payload) if payload else {})
    except urllib.error.URLError as err:
        if not isinstance(err, urllib.error.HTTPError):
            raise LinkedInError(f"Could not reach LinkedIn: {err.reason}")
        detail = err.read().decode(errors="replace")
        if err.code == 401:
            raise LinkedInError("LinkedIn login expired. Click 'Reconnect LinkedIn' in the dashboard.")
        if err.code == 426 or "VERSION" in detail:
            raise LinkedInError(f"LinkedIn rejected API version {api_version(cfg)}. "
                                f"Set a current version (YYYYMM) in the dashboard settings. {detail}")
        raise LinkedInError(f"{method} {url} failed with {err.code}: {detail}")


def _upload_image(cfg, path):
    _, init = _call(cfg, "POST", f"{API}/images?action=initializeUpload",
                    {"initializeUploadRequest": {"owner": cfg["person_urn"]}})
    value = init["value"]
    # Without an explicit Content-Type, urllib sends a form type and LinkedIn answers 400.
    req = urllib.request.Request(value["uploadUrl"], data=path.read_bytes(), method="PUT",
                                 headers={"Authorization": f"Bearer {cfg['access_token']}",
                                          "Content-Type": "application/octet-stream"})
    try:
        urllib.request.urlopen(req, timeout=120).close()
    except urllib.error.HTTPError as err:
        raise LinkedInError(f"Image upload failed with {err.code}: {err.read().decode(errors='replace')}")
    except OSError as err:
        raise LinkedInError(f"Image upload failed: {err}")
    return value["image"]


def full_text(meta, body):
    """Post text as published. The API can't add comments without partner access,
    so the post's link (stored as `comment`) goes at the end of the post."""
    link = meta.get("comment", "").strip()
    body = body.strip()
    if not link:
        return body
    paragraphs = body.split("\n\n")
    if len(paragraphs) > 1 and all(w.startswith("#") for w in paragraphs[-1].split()):
        return "\n\n".join(paragraphs[:-1] + [f"🔗 {link}", paragraphs[-1]])
    return f"{body}\n\n🔗 {link}"


def publish(path, cfg=None):
    """Publish one queue file. Returns (post_url, warning or None)."""
    cfg = cfg or load_config()
    if not cfg.get("access_token"):
        raise LinkedInError("LinkedIn is not connected yet. Click 'Connect LinkedIn' in the dashboard.")
    if cfg.get("expires_at", 0) < datetime.now().timestamp():
        raise LinkedInError("LinkedIn login expired. Click 'Reconnect LinkedIn' in the dashboard.")

    meta, body = read_post(path)
    commentary = to_little_text(full_text(meta, body))
    if len(commentary) > 3000:
        raise LinkedInError(f"{path.name} is {len(commentary)} characters; LinkedIn allows 3000.")

    post = {
        "author": cfg["person_urn"],
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                         "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    image = HERE / meta["image"] if meta.get("image") else None
    if image and image.exists():
        post["content"] = {"media": {"id": _upload_image(cfg, image), "altText": meta.get("title", "")}}
    headers, _ = _call(cfg, "POST", f"{API}/posts", post)
    post_urn = headers["x-restli-id"]
    warning = None

    PUBLISHED.mkdir(exist_ok=True)
    meta.update(post_urn=post_urn, published=str(date.today()))
    write_post(PUBLISHED / path.name, meta, body)
    path.unlink()
    return f"https://www.linkedin.com/feed/update/{post_urn}/", warning


def published_today():
    return PUBLISHED.exists() and any(read_post(p)[0].get("published") == str(date.today())
                                      for p in PUBLISHED.glob("*.md"))


def run_scheduled(cfg=None):
    """Publish at most one post per posting day. Safe to call as often as you like."""
    cfg = cfg or load_config()
    now = datetime.utcnow()
    today = WEEKDAYS[now.weekday()]
    if today not in cfg.get("post_days", ["Tue", "Thu"]):
        return f"{today} is not a posting day."
    if now.hour < cfg.get("post_hour_utc", 6):
        return f"Too early, posting starts at {cfg.get('post_hour_local', 9):02d}:00 Iraq time."
    if published_today():
        return "Already published today."
    queue = queued()
    if not queue:
        return "Queue is empty."
    url, warning = publish(queue[0], cfg)
    return f"Published {queue[0].name}: {url}" + (f" ({warning})" if warning else "")


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--scheduled", action="store_true", help="publish only on the chosen weekdays")
    mode.add_argument("--now", action="store_true", help="publish the next post right away")
    mode.add_argument("--dry-run", action="store_true", help="show the next post, publish nothing")
    args = parser.parse_args()

    cfg = load_config()
    queue = queued()
    if not queue:
        print("Queue is empty, nothing to publish.")
        return
    if args.dry_run:
        meta, body = read_post(queue[0])
        print(f"Next: {queue[0].name}\nImage: {meta.get('image') or 'none'}\n"
              f"Link: {meta.get('comment') or 'none'}\n\n{body}\n\n--- as sent ---\n{to_little_text(full_text(meta, body))}")
        return
    if args.scheduled:
        print(run_scheduled(cfg))
        return
    url, warning = publish(queue[0], cfg)
    print(f"Published {queue[0].name}: {url}")
    if warning:
        print(warning)


if __name__ == "__main__":
    main()
