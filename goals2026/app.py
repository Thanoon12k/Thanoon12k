"""Goals 2026 — a board of goal boxes, each with missions and checklist steps.

Anyone can view the board. Editing needs either the owner password (browser session)
or the API token (agents: REST with a Bearer header, or the MCP server at /mcp).
Both secrets live only as hashes in config.json.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, Response, g, jsonify, request, send_from_directory, session
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


# ---------- auth ----------

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def valid_token(token):
    expected = CONFIG.get("api_token_sha256")
    return bool(token and expected and hmac.compare_digest(token_hash(token), expected))


def bearer_token():
    auth = request.headers.get("Authorization", "")
    return auth[7:].strip() if auth.lower().startswith("bearer ") else ""


def is_owner():
    return bool(session.get("owner")) or valid_token(bearer_token())


def owner_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if valid_token(bearer_token()):
            return fn(*args, **kwargs)
        if not session.get("owner"):
            return jsonify(error="Log in (or send 'Authorization: Bearer <API token>') to edit."), 401
        # Cookie sessions: JSON-only, since a cross-site form can't send application/json without CORS.
        if not request.is_json:
            return jsonify(error="Expected JSON."), 415
        return fn(*args, **kwargs)
    return wrapper


# ---------- service layer (shared by the web page, REST API and MCP tools) ----------

class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


@app.errorhandler(ApiError)
def handle_api_error(e):
    return jsonify(error=e.message), e.status


def clean(value, limit=200):
    return str(value if value is not None else "").strip()[:limit]


def progress(steps):
    total = len(steps)
    done = sum(1 for s in steps if s["done"])
    return {"done": done, "total": total, "pct": round(done * 100 / total) if total else 0,
            "complete": total > 0 and done == total}


def board_data(goal_id=None):
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
        m["progress"] = progress(m["steps"])
        by_goal.setdefault(m["goal_id"], []).append(m)
    for gl in goals:
        gl["missions"] = by_goal.get(gl["id"], [])
        gl["progress"] = progress([s for m in gl["missions"] for s in m["steps"]])
        gl["progress"]["missions_done"] = sum(1 for m in gl["missions"] if m["progress"]["complete"])
        gl["progress"]["complete"] = bool(gl["missions"]) and gl["progress"]["missions_done"] == len(gl["missions"])
    if goal_id is not None:
        return next((gl for gl in goals if gl["id"] == goal_id), None)
    return goals


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
    if out.get("deadline") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", out["deadline"]):
        raise ApiError("deadline must be YYYY-MM-DD (or empty).")
    if "color" in data or not partial:
        out["color"] = data.get("color") if data.get("color") in COLORS else secrets.choice(COLORS)
    if not partial:
        out["texture"] = secrets.choice(TEXTURES)
    if "emoji" in out and not out["emoji"]:
        out["emoji"] = "🎯"
    if partial and "title" in out and not out["title"]:
        out.pop("title")
    return out


def update_row(table, row_id, fields):
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        db().execute(f"UPDATE {table} SET {sets} WHERE id = ?", (*fields.values(), row_id))


def require(table, row_id):
    row = db().execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if not row:
        raise ApiError(f"{table[:-1]} {row_id} not found.", 404)
    return row


def move(table, row_id, direction, scope_col=None):
    """Swap an item's position with its neighbour (direction < 0 = earlier, > 0 = later)."""
    conn = db()
    row = require(table, row_id)
    where, args = ("", ())
    if scope_col:
        where, args = (f"WHERE {scope_col} = ?", (row[scope_col],))
    ids = [r["id"] for r in conn.execute(f"SELECT id FROM {table} {where} ORDER BY position, id", args)]
    i = ids.index(row_id)
    j = i + (1 if int(direction) > 0 else -1)
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
    conn.executemany(f"UPDATE {table} SET position = ? WHERE id = ?", [(p, x) for p, x in enumerate(ids)])


def text_list(items, limit):
    if isinstance(items, str):
        items = [items]
    if not isinstance(items, list):
        raise ApiError("steps must be a list of strings.")
    return [t for t in (clean(x, limit) for x in items) if t]


def create_goal(data):
    fields = goal_fields(data, partial=False)
    if not fields["title"]:
        raise ApiError("title is required.")
    fields.update(position=next_pos("goals"), created_at=now())
    cols = ", ".join(fields)
    gid = db().execute(f"INSERT INTO goals ({cols}) VALUES ({','.join('?' * len(fields))})",
                       tuple(fields.values())).lastrowid
    for m in data.get("missions") or []:
        m = m if isinstance(m, dict) else {"title": m}
        add_mission(gid, m.get("title"), m.get("steps") or [])
    return gid


def update_goal(gid, data):
    require("goals", gid)
    if data.get("move"):
        move("goals", gid, data["move"])
    update_row("goals", gid, goal_fields(data, partial=True))


def delete_goal(gid):
    require("goals", gid)
    db().execute("DELETE FROM goals WHERE id = ?", (gid,))


def add_mission(gid, title, steps=()):
    require("goals", gid)
    title = clean(title, 160)
    if not title:
        raise ApiError("mission title is required.")
    mid = db().execute("INSERT INTO missions (goal_id, title, position) VALUES (?,?,?)",
                       (gid, title, next_pos("missions", "goal_id", gid))).lastrowid
    add_steps(mid, steps)
    return mid


def update_mission(mid, data):
    require("missions", mid)
    if data.get("move"):
        move("missions", mid, data["move"], "goal_id")
    title = clean(data.get("title"), 160)
    if title:
        update_row("missions", mid, {"title": title})


def delete_mission(mid):
    require("missions", mid)
    db().execute("DELETE FROM missions WHERE id = ?", (mid,))


def add_steps(mid, texts):
    require("missions", mid)
    ids = []
    for text in text_list(texts, 200):
        ids.append(db().execute("INSERT INTO steps (mission_id, text, position) VALUES (?,?,?)",
                                (mid, text, next_pos("steps", "mission_id", mid))).lastrowid)
    return ids


def update_step(sid, data):
    require("steps", sid)
    if data.get("move"):
        move("steps", sid, data["move"], "mission_id")
    fields = {}
    if clean(data.get("text"), 200):
        fields["text"] = clean(data.get("text"), 200)
    if "done" in data and data["done"] is not None:
        done = data["done"] if isinstance(data["done"], bool) else str(data["done"]).lower() in ("1", "true", "yes")
        fields["done"] = 1 if done else 0
        fields["done_at"] = now() if done else ""
    update_row("steps", sid, fields)


def delete_step(sid):
    require("steps", sid)
    db().execute("DELETE FROM steps WHERE id = ?", (sid,))


def goal_of(table, row_id):
    if table == "missions":
        return require("missions", row_id)["goal_id"]
    return db().execute("SELECT m.goal_id FROM steps s JOIN missions m ON m.id = s.mission_id WHERE s.id = ?",
                        (row_id,)).fetchone()[0]


# ---------- web routes / REST API ----------

def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def board(**extra):
    return jsonify(goals=board_data(), owner=is_owner(), colors=COLORS, textures=TEXTURES, **extra)


def commit_board(**extra):
    db().commit()
    return board(**extra)


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


@app.get("/api/goals/<int:gid>")
def get_goal(gid):
    goal = board_data(gid)
    if not goal:
        raise ApiError(f"goal {gid} not found.", 404)
    return jsonify(goal)


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
def api_add_goal():
    return commit_board(created_id=create_goal(body()))


@app.patch("/api/goals/<int:gid>")
@owner_required
def api_edit_goal(gid):
    update_goal(gid, body())
    return commit_board()


@app.delete("/api/goals/<int:gid>")
@owner_required
def api_delete_goal(gid):
    delete_goal(gid)
    return commit_board()


@app.post("/api/goals/<int:gid>/missions")
@owner_required
def api_add_mission(gid):
    data = body()
    return commit_board(created_id=add_mission(gid, data.get("title"), data.get("steps") or []))


@app.patch("/api/missions/<int:mid>")
@owner_required
def api_edit_mission(mid):
    update_mission(mid, body())
    return commit_board()


@app.delete("/api/missions/<int:mid>")
@owner_required
def api_delete_mission(mid):
    delete_mission(mid)
    return commit_board()


@app.post("/api/missions/<int:mid>/steps")
@owner_required
def api_add_step(mid):
    data = body()
    texts = data.get("steps") if "steps" in data else [data.get("text")]
    ids = add_steps(mid, texts)
    if not ids:
        raise ApiError("step text is required.")
    return commit_board(created_id=ids[0], created_ids=ids)


@app.patch("/api/steps/<int:sid>")
@owner_required
def api_edit_step(sid):
    update_step(sid, body())
    return commit_board()


@app.delete("/api/steps/<int:sid>")
@owner_required
def api_delete_step(sid):
    delete_step(sid)
    return commit_board()


# ---------- MCP server (Streamable HTTP, stateless JSON responses) ----------

MCP_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]
MCP_INSTRUCTIONS = (
    "Goals 2026 board: each goal is a box holding ordered missions; each mission is a checklist of steps. "
    "Call get_board first to learn ids. Progress is computed from checked steps; a goal is achieved when every "
    "mission's steps are all done. Prefer create_goal with nested missions/steps to build a whole goal at once, "
    "and check_steps to tick several steps in one call."
)

_ID = {"type": "integer", "minimum": 1}
_MOVE = {"type": "integer", "enum": [-1, 1], "description": "-1 moves it one place earlier, 1 one place later."}
_STEPS = {"type": "array", "items": {"type": "string", "maxLength": 200}, "description": "Checklist step texts, in order."}
_GOAL_PROPS = {
    "title": {"type": "string", "maxLength": 120},
    "emoji": {"type": "string", "description": "One emoji shown on the box, e.g. 🎓."},
    "category": {"type": "string", "maxLength": 40, "description": "Short label, e.g. Career."},
    "deadline": {"type": "string", "description": "YYYY-MM-DD, or empty string to clear."},
    "why": {"type": "string", "maxLength": 400, "description": "One line on why this goal matters."},
    "color": {"type": "string", "enum": COLORS},
}


def _tool(name, description, props=None, required=(), read_only=False, destructive=False):
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": props or {}, "required": list(required),
                        "additionalProperties": False},
        "annotations": {"readOnlyHint": read_only, "destructiveHint": destructive, "idempotentHint": read_only},
    }


MCP_TOOLS = [
    _tool("get_board", "List every goal with its missions and steps (ids, done flags, progress).", read_only=True),
    _tool("get_goal", "Get one goal with its missions and steps.", {"goal_id": _ID}, ["goal_id"], read_only=True),
    _tool("create_goal", "Create a goal box, optionally with missions and their checklist steps in one call.",
          {**_GOAL_PROPS, "missions": {"type": "array", "items": {
              "type": "object", "properties": {"title": {"type": "string", "maxLength": 160}, "steps": _STEPS},
              "required": ["title"]}}}, ["title"]),
    _tool("update_goal", "Change a goal's fields and/or move it earlier/later on the board. Omitted fields stay as they are.",
          {"goal_id": _ID, **_GOAL_PROPS, "move": _MOVE}, ["goal_id"]),
    _tool("delete_goal", "Delete a goal with all its missions and steps.", {"goal_id": _ID}, ["goal_id"], destructive=True),
    _tool("add_mission", "Add a mission (optionally with steps) to the end of a goal.",
          {"goal_id": _ID, "title": {"type": "string", "maxLength": 160}, "steps": _STEPS}, ["goal_id", "title"]),
    _tool("update_mission", "Rename a mission and/or move it within its goal.",
          {"mission_id": _ID, "title": {"type": "string", "maxLength": 160}, "move": _MOVE}, ["mission_id"]),
    _tool("delete_mission", "Delete a mission and its steps.", {"mission_id": _ID}, ["mission_id"], destructive=True),
    _tool("add_steps", "Append checklist steps to a mission.", {"mission_id": _ID, "steps": _STEPS}, ["mission_id", "steps"]),
    _tool("update_step", "Edit a step's text, mark it done/undone, and/or move it within its mission.",
          {"step_id": _ID, "text": {"type": "string", "maxLength": 200}, "done": {"type": "boolean"}, "move": _MOVE},
          ["step_id"]),
    _tool("check_steps", "Mark several steps done (or undone with done=false) at once.",
          {"step_ids": {"type": "array", "items": _ID, "minItems": 1}, "done": {"type": "boolean", "default": True}},
          ["step_ids"]),
    _tool("delete_step", "Delete a checklist step.", {"step_id": _ID}, ["step_id"], destructive=True),
]


def _compact(goal):
    """Agent-friendly view of a goal: drop layout-only fields."""
    return {
        "id": goal["id"], "title": goal["title"], "emoji": goal["emoji"], "category": goal["category"],
        "deadline": goal["deadline"], "why": goal["why"], "color": goal["color"], "progress": goal["progress"],
        "missions": [{"id": m["id"], "title": m["title"], "progress": m["progress"],
                      "steps": [{"id": s["id"], "text": s["text"], "done": s["done"]} for s in m["steps"]]}
                     for m in goal["missions"]],
    }


def _goal_result(gid, **extra):
    goal = board_data(gid)
    return {"ok": True, **extra, "goal": _compact(goal) if goal else None}


def _int(args, key):
    try:
        return int(args[key])
    except (KeyError, TypeError, ValueError):
        raise ApiError(f"{key} (integer) is required.")


def run_tool(name, args):
    if name == "get_board":
        goals = board_data()
        total = sum(gl["progress"]["total"] for gl in goals)
        done = sum(gl["progress"]["done"] for gl in goals)
        return {"overall_pct": round(done * 100 / total) if total else 0,
                "goals_achieved": sum(1 for gl in goals if gl["progress"]["complete"]),
                "goals": [_compact(gl) for gl in goals]}
    if name == "get_goal":
        goal = board_data(_int(args, "goal_id"))
        if not goal:
            raise ApiError(f"goal {args['goal_id']} not found.", 404)
        return _compact(goal)
    if name == "create_goal":
        gid = create_goal(args)
        db().commit()
        return _goal_result(gid, created_goal_id=gid)
    if name == "update_goal":
        gid = _int(args, "goal_id")
        update_goal(gid, args)
        db().commit()
        return _goal_result(gid)
    if name == "delete_goal":
        gid = _int(args, "goal_id")
        title = require("goals", gid)["title"]
        delete_goal(gid)
        db().commit()
        return {"ok": True, "deleted_goal": {"id": gid, "title": title}}
    if name == "add_mission":
        gid = _int(args, "goal_id")
        mid = add_mission(gid, args.get("title"), args.get("steps") or [])
        db().commit()
        return _goal_result(gid, created_mission_id=mid)
    if name == "update_mission":
        mid = _int(args, "mission_id")
        update_mission(mid, args)
        db().commit()
        return _goal_result(goal_of("missions", mid))
    if name == "delete_mission":
        mid = _int(args, "mission_id")
        gid = goal_of("missions", mid)
        delete_mission(mid)
        db().commit()
        return _goal_result(gid, deleted_mission_id=mid)
    if name == "add_steps":
        mid = _int(args, "mission_id")
        ids = add_steps(mid, args.get("steps") or [])
        if not ids:
            raise ApiError("steps must contain at least one non-empty string.")
        db().commit()
        return _goal_result(goal_of("missions", mid), created_step_ids=ids)
    if name == "update_step":
        sid = _int(args, "step_id")
        update_step(sid, args)
        db().commit()
        return _goal_result(goal_of("steps", sid))
    if name == "check_steps":
        ids = args.get("step_ids")
        if not isinstance(ids, list) or not ids:
            raise ApiError("step_ids must be a non-empty list of integers.")
        done = args.get("done", True)
        goal_ids = []
        for sid in ids:
            update_step(int(sid), {"done": done})
            gid = goal_of("steps", int(sid))
            if gid not in goal_ids:
                goal_ids.append(gid)
        db().commit()
        return {"ok": True, "updated_step_ids": ids,
                "goals": [_compact(board_data(gid)) for gid in goal_ids]}
    if name == "delete_step":
        sid = _int(args, "step_id")
        gid = goal_of("steps", sid)
        delete_step(sid)
        db().commit()
        return _goal_result(gid, deleted_step_id=sid)
    raise ApiError(f"Unknown tool: {name}")


def _rpc_result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _rpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle_rpc(msg):
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
        return _rpc_error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    if "id" not in msg:  # notification (e.g. notifications/initialized): nothing to answer
        return None
    msg_id, method, params = msg["id"], msg["method"], msg.get("params") or {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        return _rpc_result(msg_id, {
            "protocolVersion": asked if asked in MCP_VERSIONS else MCP_VERSIONS[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "goals2026", "title": "Goals 2026", "version": "1.0.0"},
            "instructions": MCP_INSTRUCTIONS,
        })
    if method == "ping":
        return _rpc_result(msg_id, {})
    if method == "tools/list":
        return _rpc_result(msg_id, {"tools": MCP_TOOLS})
    if method == "tools/call":
        name = params.get("name")
        if name not in {t["name"] for t in MCP_TOOLS}:
            return _rpc_error(msg_id, -32602, f"Unknown tool: {name}")
        args = params.get("arguments") or {}
        try:
            result = run_tool(name, args if isinstance(args, dict) else {})
        except ApiError as e:
            db().rollback()
            return _rpc_result(msg_id, {"content": [{"type": "text", "text": f"Error: {e.message}"}], "isError": True})
        except (TypeError, ValueError) as e:
            db().rollback()
            return _rpc_result(msg_id, {"content": [{"type": "text", "text": f"Error: invalid arguments ({e})"}],
                                        "isError": True})
        return _rpc_result(msg_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                                    "structuredContent": result})
    return _rpc_error(msg_id, -32601, f"Method not found: {method}")


@app.route("/mcp", methods=["GET", "POST", "DELETE"])
@app.route("/mcp/<path_token>", methods=["GET", "POST", "DELETE"])
def mcp(path_token=None):
    # Token in the Authorization header, or in the URL for clients that can't set headers.
    if not valid_token(bearer_token()) and not valid_token(path_token or ""):
        resp = jsonify(_rpc_error(None, -32001, "Unauthorized: send 'Authorization: Bearer <API token>'."))
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = 'Bearer realm="goals2026"'
        return resp
    if request.method != "POST":  # stateless server: no SSE stream, no sessions to delete
        return Response(status=405, headers={"Allow": "POST"})
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(_rpc_error(None, -32700, "Parse error")), 400
    if isinstance(payload, list):
        replies = [r for r in (handle_rpc(m) for m in payload) if r is not None]
        return (jsonify(replies), 200) if replies else Response(status=202)
    reply = handle_rpc(payload)
    return jsonify(reply) if reply is not None else Response(status=202)


@app.get("/llms.txt")
def llms_txt():
    base = request.host_url.rstrip("/")
    tools = "\n".join(f"- `{t['name']}` — {t['description']}" for t in MCP_TOOLS)
    text = f"""# Goals 2026

> A personal goal board: each goal is a box of ordered missions; each mission is a checklist of steps.
> Reading is public. Changing anything needs the owner's API token.

## For AI agents: MCP server (recommended)

Endpoint: `{base}/mcp` (Streamable HTTP, JSON responses, no SSE)
Auth: `Authorization: Bearer <API token>` — or put the token in the path, `{base}/mcp/<API token>`,
for clients that cannot set headers.

Claude Code:

    claude mcp add --transport http goals2026 {base}/mcp --header "Authorization: Bearer <API token>"

Tools:
{tools}

## REST API

All responses are JSON. Mutations return the whole board (`goals`) plus `created_id`/`created_ids` when
something was created. Send `Authorization: Bearer <API token>` and `Content-Type: application/json`.

- `GET    /api/board` — all goals with missions, steps and progress (public)
- `GET    /api/goals/<id>` — one goal (public)
- `POST   /api/goals` — {{"title", "emoji"?, "category"?, "deadline"? (YYYY-MM-DD), "why"?, "color"?,
  "missions"?: [{{"title", "steps": [str]}}]}}
- `PATCH  /api/goals/<id>` — any goal field, and/or {{"move": -1|1}}
- `DELETE /api/goals/<id>`
- `POST   /api/goals/<id>/missions` — {{"title", "steps"?: [str]}}
- `PATCH  /api/missions/<id>` — {{"title"?, "move"?: -1|1}}
- `DELETE /api/missions/<id>`
- `POST   /api/missions/<id>/steps` — {{"text"}} or {{"steps": [str]}}
- `PATCH  /api/steps/<id>` — {{"text"?, "done"?: bool, "move"?: -1|1}}
- `DELETE /api/steps/<id>`

Colors: {", ".join(COLORS)}.

Example:

    curl -X PATCH {base}/api/steps/12 -H "Authorization: Bearer $TOKEN" \\
         -H "Content-Type: application/json" -d '{{"done": true}}'
"""
    return Response(text, mimetype="text/plain; charset=utf-8")


def new_api_token():
    """Create (or rotate) the API token; only its SHA-256 is stored."""
    token = "g26_" + secrets.token_urlsafe(32)
    CONFIG["api_token_sha256"] = token_hash(token)
    with open(CONFIG_PATH, "w") as f:
        json.dump(CONFIG, f)
    return token


if __name__ == "__main__":
    if "--new-token" in sys.argv:
        print(f"New API token (shown once, old one stops working): {new_api_token()}")
    else:
        app.run(debug=True, port=5055)
