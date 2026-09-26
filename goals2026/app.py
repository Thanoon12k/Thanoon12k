"""Goals 2026 — a board of goal boxes, each with missions and checklist steps.

Anyone can view the board; editing needs the owner password (hash in config.json).
"""
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "goals.db")
CONFIG_PATH = os.path.join(BASE, "config.json")

COLORS = ["ember", "ocean", "forest", "violet", "sun", "rose", "slate", "teal"]
TEXTURES = ["grain", "dots", "lines", "grid", "waves", "cross", "topo", "paper"]


def load_config():
    if not os.path.exists(CONFIG_PATH):
        password = secrets.token_urlsafe(9)
        cfg = {"secret_key": secrets.token_hex(32),
               "password_hash": generate_password_hash(password)}
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f)
        print(f"[goals] created config.json — owner password: {password}")
    with open(CONFIG_PATH) as f:
        return json.load(f)


CONFIG = load_config()
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = CONFIG["secret_key"]
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 60)

SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    emoji TEXT NOT NULL DEFAULT '🎯',
    color TEXT NOT NULL DEFAULT 'ember',
    texture TEXT NOT NULL DEFAULT 'grain',
    category TEXT NOT NULL DEFAULT '',
    deadline TEXT NOT NULL DEFAULT '',
    why TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    done_at TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0
);
"""

SEED = [
    ("Complete my Master's degree", "🎓", "violet", "paper", "Education",
     "Close the chapter and open new doors.", [
         ("Finish coursework", ["Pass all remaining courses", "Submit final assignments", "Clear any pending grades"]),
         ("Write the thesis", ["Finalize research question", "Complete literature review", "Run experiments", "Write results & discussion", "Supervisor review"]),
         ("Defend", ["Prepare slides", "Rehearse with a friend", "Defend the thesis", "Submit final corrected copy"]),
     ]),
    ("Reach 1K followers", "🚀", "ember", "dots", "Brand",
     "Build an audience that trusts my work.", [
         ("Set up the profile", ["Clear bio & profile photo", "Pinned post about what I do", "Link to portfolio"]),
         ("Content engine", ["Plan 30 post ideas", "Post 3 times a week for a month", "Make 5 short videos"]),
         ("Grow & engage", ["Reply to every comment", "Collaborate with 3 creators", "Hit 250", "Hit 500", "Hit 1000 🎉"]),
     ]),
    ("Get employed", "💼", "ocean", "grid", "Career",
     "A stable role where I grow as an engineer.", [
         ("Sharpen the CV", ["Update CV with latest projects", "Get CV reviewed", "Update LinkedIn"]),
         ("Apply", ["List 20 target companies", "Send 10 applications", "Send 20 more applications"]),
         ("Interview", ["Practice 10 coding problems", "Mock interview", "Pass an interview", "Sign the offer"]),
     ]),
    ("Find first online work", "🌍", "forest", "waves", "Freelance",
     "Earn my first income from a remote client.", [
         ("Freelance profiles", ["Create Upwork profile", "Create Fiverr gig", "Add 3 portfolio samples"]),
         ("Land the client", ["Send 15 proposals", "Get a reply", "Win the first job"]),
         ("Deliver", ["Deliver on time", "Get a 5-star review"]),
     ]),
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 0:
        for gi, (title, emoji, color, tex, cat, why, missions) in enumerate(SEED):
            gid = conn.execute(
                "INSERT INTO goals (title, emoji, color, texture, category, why, position, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)", (title, emoji, color, tex, cat, why, gi, now())).lastrowid
            for mi, (mtitle, steps) in enumerate(missions):
                mid = conn.execute("INSERT INTO missions (goal_id, title, position) VALUES (?,?,?)",
                                   (gid, mtitle, mi)).lastrowid
                conn.executemany("INSERT INTO steps (mission_id, text, position) VALUES (?,?,?)",
                                 [(mid, s, si) for si, s in enumerate(steps)])
    conn.commit()
    conn.close()


init_db()


# ---------- helpers ----------

def is_owner():
    return bool(session.get("owner"))


def owner_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_owner():
            return jsonify(error="Log in to edit."), 401
        # JSON-only mutations: a cross-site form can't send application/json without CORS.
        if not request.is_json:
            return jsonify(error="Expected JSON."), 415
        return fn(*args, **kwargs)
    return wrapper


def body():
    return request.get_json(silent=True) or {}


def clean(value, limit=200):
    return str(value or "").strip()[:limit]


def board():
    conn = db()
    goals = [dict(r) for r in conn.execute("SELECT * FROM goals ORDER BY position, id")]
    missions = [dict(r) for r in conn.execute("SELECT * FROM missions ORDER BY position, id")]
    steps = [dict(r) for r in conn.execute("SELECT * FROM steps ORDER BY position, id")]
    by_mission = {}
    for s in steps:
        s["done"] = bool(s["done"])
        by_mission.setdefault(s["mission_id"], []).append(s)
    by_goal = {}
    for m in missions:
        m["steps"] = by_mission.get(m["id"], [])
        by_goal.setdefault(m["goal_id"], []).append(m)
    for gl in goals:
        gl["missions"] = by_goal.get(gl["id"], [])
    return jsonify(goals=goals, owner=is_owner(), colors=COLORS, textures=TEXTURES)


def next_pos(table, col=None, val=None):
    q = f"SELECT COALESCE(MAX(position), -1) + 1 FROM {table}"
    if col:
        return db().execute(q + f" WHERE {col} = ?", (val,)).fetchone()[0]
    return db().execute(q).fetchone()[0]


def goal_fields(data, partial):
    out = {}
    for key, limit in (("title", 120), ("emoji", 16), ("category", 40), ("deadline", 10), ("why", 400)):
        if key in data or not partial:
            out[key] = clean(data.get(key), limit)
    if "color" in data or not partial:
        out["color"] = data.get("color") if data.get("color") in COLORS else secrets.choice(COLORS)
    if "texture" in data or not partial:
        out["texture"] = data.get("texture") if data.get("texture") in TEXTURES else secrets.choice(TEXTURES)
    if "emoji" in out and not out["emoji"]:
        out["emoji"] = "🎯"
    return out


def update_row(table, row_id, fields):
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    db().execute(f"UPDATE {table} SET {sets} WHERE id = ?", (*fields.values(), row_id))


def move(table, row_id, direction, scope_col=None):
    """Swap an item's position with its neighbour (direction -1 = up, 1 = down)."""
    conn = db()
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if not row:
        return
    where, args = ("", ())
    if scope_col:
        where, args = (f"WHERE {scope_col} = ?", (row[scope_col],))
    ids = [r["id"] for r in conn.execute(f"SELECT id FROM {table} {where} ORDER BY position, id", args)]
    i = ids.index(row_id)
    j = i + (1 if direction > 0 else -1)
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
    conn.executemany(f"UPDATE {table} SET position = ? WHERE id = ?", [(p, x) for p, x in enumerate(ids)])


# ---------- routes ----------

@app.get("/")
def index():
    resp = send_from_directory(app.static_folder, "index.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "icon-32.png", mimetype="image/png")


@app.get("/api/board")
def get_board():
    return board()


@app.post("/api/login")
def login():
    if check_password_hash(CONFIG["password_hash"], clean(body().get("password"), 200)):
        session.permanent = True
        session["owner"] = True
        return board()
    time.sleep(1)
    return jsonify(error="Wrong password."), 403


@app.post("/api/logout")
def logout():
    session.clear()
    return board()


@app.post("/api/goals")
@owner_required
def add_goal():
    fields = goal_fields(body(), partial=False)
    if not fields["title"]:
        return jsonify(error="Title is required."), 400
    fields.update(position=next_pos("goals"), created_at=now())
    cols = ", ".join(fields)
    db().execute(f"INSERT INTO goals ({cols}) VALUES ({','.join('?' * len(fields))})", tuple(fields.values()))
    db().commit()
    return board()


@app.patch("/api/goals/<int:gid>")
@owner_required
def edit_goal(gid):
    data = body()
    if "move" in data:
        move("goals", gid, int(data["move"]))
    fields = goal_fields(data, partial=True)
    if "title" in fields and not fields["title"]:
        fields.pop("title")
    update_row("goals", gid, fields)
    db().commit()
    return board()


@app.delete("/api/goals/<int:gid>")
@owner_required
def delete_goal(gid):
    db().execute("DELETE FROM goals WHERE id = ?", (gid,))
    db().commit()
    return board()


@app.post("/api/goals/<int:gid>/missions")
@owner_required
def add_mission(gid):
    title = clean(body().get("title"), 160)
    if not title:
        return jsonify(error="Mission title is required."), 400
    db().execute("INSERT INTO missions (goal_id, title, position) VALUES (?,?,?)",
                 (gid, title, next_pos("missions", "goal_id", gid)))
    db().commit()
    return board()


@app.patch("/api/missions/<int:mid>")
@owner_required
def edit_mission(mid):
    data = body()
    if "move" in data:
        move("missions", mid, int(data["move"]), "goal_id")
    title = clean(data.get("title"), 160)
    if title:
        update_row("missions", mid, {"title": title})
    db().commit()
    return board()


@app.delete("/api/missions/<int:mid>")
@owner_required
def delete_mission(mid):
    db().execute("DELETE FROM missions WHERE id = ?", (mid,))
    db().commit()
    return board()


@app.post("/api/missions/<int:mid>/steps")
@owner_required
def add_step(mid):
    text = clean(body().get("text"), 200)
    if not text:
        return jsonify(error="Step text is required."), 400
    db().execute("INSERT INTO steps (mission_id, text, position) VALUES (?,?,?)",
                 (mid, text, next_pos("steps", "mission_id", mid)))
    db().commit()
    return board()


@app.patch("/api/steps/<int:sid>")
@owner_required
def edit_step(sid):
    data = body()
    fields = {}
    if "move" in data:
        move("steps", sid, int(data["move"]), "mission_id")
    if clean(data.get("text"), 200):
        fields["text"] = clean(data.get("text"), 200)
    if "done" in data:
        fields["done"] = 1 if data["done"] else 0
        fields["done_at"] = now() if data["done"] else ""
    update_row("steps", sid, fields)
    db().commit()
    return board()


@app.delete("/api/steps/<int:sid>")
@owner_required
def delete_step(sid):
    db().execute("DELETE FROM steps WHERE id = ?", (sid,))
    db().commit()
    return board()


if __name__ == "__main__":
    app.run(debug=True, port=5055)
