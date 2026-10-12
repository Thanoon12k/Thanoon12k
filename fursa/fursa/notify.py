"""Telegram: alerts out, status updates in. No server needed.

Out: one message per new approved pick (title, pay, why it fits, the draft inside
     an expandable quote, buttons to the posting and the dashboard). Nothing is
     sent when nothing new was approved.
In:  each run reads the bot's new messages. Replying to a pick with «قدمت»,
     «مقابلة», «ما تهمني»... (or sending "/applied <id>") saves that status.
     Only messages from TELEGRAM_CHAT_ID are accepted.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import timedelta

from . import net
from .scoring import normalize
from .status import apply as apply_status
from .text import clip

log = logging.getLogger("fursa.notify")
API = "https://api.telegram.org/bot{token}/{method}"

KIND_AR = {"job": "وظيفة", "freelance": "مشروع حر", "gig": "مهمة صغيرة", "bounty": "مكافأة bounty"}
ELIG_AR = {"yes": "✅ متاح للعراق", "likely": "🟡 غالباً متاح", "unclear": "⚠️ الأهلية غير محسومة", "no": "❌ غير متاح"}
STATUS_AR = {"applied": "تم التقديم ✓", "interview": "مقابلة", "offer": "عرض شغل", "rejected": "انرفضت", "ignored": "ما تهم", "todo": "مؤجلة"}
REPLY_WORDS = {
    "applied": ("قدمت", "تم التقديم", "applied", "sent"),
    "interview": ("مقابله", "interview"),
    "offer": ("عرض شغل", "offer"),
    "rejected": ("انرفضت", "رفضوني", "rejected"),
    "ignored": ("ما تهمني", "ما تهم", "تجاهل", "ignore", "ignored", "skip"),
    "todo": ("مؤجله", "بعدين", "later", "todo"),
}


def configured(settings) -> bool:
    return bool(settings.telegram_token and settings.telegram_chat)


def _e(value) -> str:
    return html.escape(str(value or ""), quote=False)


def _call(settings, method: str, payload: dict) -> dict:
    response = net.session().post(API.format(token=settings.telegram_token, method=method), json=payload, timeout=30)
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if not data.get("ok"):
        raise net.SourceError(f"Telegram {method} failed: {data.get('description') or response.status_code}")
    return data.get("result")


def quiet(settings) -> bool:
    local = settings.now + timedelta(hours=3)  # Iraq time (UTC+3)
    return local.hour < 8


def send(settings, text: str, buttons: list | None = None) -> dict | None:
    """Send one HTML message; returns Telegram's message object, or None when not configured."""
    if not configured(settings):
        log.info("Telegram not configured; message not sent")
        return None
    payload = {
        "chat_id": settings.telegram_chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": quiet(settings),
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    return _call(settings, "sendMessage", payload)


def pick_message(settings, rec: dict, n: int, total: int, summary: str = "") -> tuple[str, list]:
    match, manager, draft = rec.get("match") or {}, rec.get("manager") or {}, rec.get("draft") or {}
    lines = []
    if summary and n == 1:
        lines += [f"🗂 {_e(clip(summary, 200))}", ""]
    lines.append(f"🎯 <b>{n}/{total} · {_e(clip(rec['title'], 100))}</b>")
    lines.append(" · ".join(_e(x) for x in (rec.get("company"), rec.get("source_label")) if x))
    meta = [KIND_AR.get(rec.get("kind"), rec.get("kind")), rec.get("location"), ELIG_AR.get(rec.get("elig"), "")]
    lines.append(" · ".join(_e(x) for x in meta if x))
    lines.append(f"💵 {_e(rec['pay'])}" if rec.get("pay") else "💵 الأجر غير معلن")
    if rec.get("posted"):
        lines.append(f"📅 {_e(rec['posted'])}")
    note = manager.get("note_ar") or match.get("fit_reason_ar")
    if note:
        lines.append(f"💡 {_e(clip(note, 300))}")
    repos = ", ".join(r["name"] for r in match.get("repos", [])[:3])
    if repos:
        lines.append(f"🧩 {_e(repos)}")
    if draft.get("message"):
        if draft.get("subject"):
            lines.append(f"✉️ <b>{_e(clip(draft['subject'], 150))}</b>")
        lines.append(f"<blockquote expandable>{_e(clip(draft['message'], 2300))}</blockquote>")
    lines.append("↩️ للتحديث: الرد على هالرسالة بكلمة «قدمت» أو «مقابلة» أو «ما تهمني».")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "…"
    row = [{"text": "🔗 الإعلان", "url": rec["url"]}]
    if settings.site_url:
        row.append({"text": "📝 التفاصيل والمسودة", "url": f"{settings.site_url}#{rec['id']}"})
    return text, [row]


def announce(settings, store, picks: list[dict], summary: str = "") -> int:
    """One message per pick. Remembers message ids so replies can update the status."""
    sent = 0
    memory = store.state.setdefault("telegram", {}).setdefault("messages", {})
    for n, rec in enumerate(picks, 1):
        text, buttons = pick_message(settings, rec, n, len(picks), summary)
        message = send(settings, text, buttons)
        if message:
            memory[str(message.get("message_id"))] = rec["id"]
            sent += 1
    for key in sorted(memory, key=int)[:-300]:  # keep the map small
        del memory[key]
    return sent


def reply_status(text: str) -> str | None:
    words = normalize(text)
    command = re.match(r"^/(\w+)", words)
    if command and command.group(1) in REPLY_WORDS:
        return command.group(1)
    for status, options in REPLY_WORDS.items():
        if any(normalize(o) in words for o in options):
            return status
    return None


def poll(settings, store) -> list[tuple[dict, str]]:
    """Apply status replies sent to the bot since the last run. Returns [(record, status)]."""
    if not configured(settings):
        return []
    tg = store.state.setdefault("telegram", {})
    memory = tg.setdefault("messages", {})
    updates = _call(settings, "getUpdates", {"offset": tg.get("offset", 0) + 1, "timeout": 0, "allowed_updates": ["message"]})
    applied = []
    for update in updates or []:
        tg["offset"] = max(tg.get("offset", 0), update.get("update_id", 0))
        message = update.get("message") or {}
        if str((message.get("chat") or {}).get("id")) != str(settings.telegram_chat):
            continue  # only the owner's chat may change the memory
        text = message.get("text") or ""
        replied = str((message.get("reply_to_message") or {}).get("message_id", ""))
        opp_id = memory.get(replied)
        explicit = re.search(r"\b([0-9a-f]{12})\b", text)
        if explicit:
            opp_id = explicit.group(1)
        status = reply_status(text)
        if opp_id and status and apply_status(store, opp_id, status, text):
            applied.append((store.opps[opp_id], status))
    return applied


def confirm(settings, applied: list[tuple[dict, str]]) -> None:
    if not applied:
        return
    lines = ["✅ انحفظت بالذاكرة:"] + [f"• {_e(clip(rec['title'], 70))} ← {STATUS_AR.get(status, status)}" for rec, status in applied]
    send(settings, "\n".join(lines))


def chat_ids(settings) -> list[tuple[str, str]]:
    """Setup helper: who has messaged the bot (send it any message first)."""
    found = {}
    for update in _call(settings, "getUpdates", {"timeout": 0}) or []:
        chat = (update.get("message") or update.get("my_chat_member") or {}).get("chat") or {}
        if chat.get("type") == "private" and chat.get("id"):
            found[str(chat["id"])] = chat.get("username") or chat.get("first_name") or ""
    return sorted(found.items())


def bot_name(settings) -> str:
    return (_call(settings, "getMe", {}) or {}).get("username", "")
