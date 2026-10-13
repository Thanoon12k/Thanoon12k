"""Telegram: alerts out, status updates in. No server needed.

Out: one message per new approved pick (title, pay, why it fits, the draft inside
     an expandable quote, buttons to the posting and the dashboard). Nothing is
     sent when nothing new was approved.
In:  each run reads the bot's new messages. Replying to a pick with «قدمت»,
     «مقابلة», «ما تهمني»... (or sending "/applied <id>") saves that status;
     /start or /help gets a short how-to. Only messages from TELEGRAM_CHAT_ID are accepted.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import timedelta

from . import net
from .contacts import gmail_link, on_platform, telegram_share_link, whatsapp_link
from .scoring import normalize
from .status import apply as apply_status
from .text import clip, iso_time

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
    if on_platform(rec["url"]):
        lines.append("📋 التقديم من صفحة المشروع بالمنصة: نسخ المسودة ولصقها بخانة العرض (بدون أي وسيلة تواصل).")
    else:
        lines.append("📨 أزرار الإرسال تفتح التطبيق والمسودة جاهزة؛ الإرسال بضغطة منك.")
    lines.append("↩️ للتحديث: الرد على هالرسالة بكلمة «قدمت» أو «مقابلة» أو «ما تهمني».")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "…"
    return text, buttons(settings, rec)


def buttons(settings, rec: dict) -> list[list[dict]]:
    """Contact buttons first (each opens the app with the draft ready; sending stays a human tap), then links."""
    draft, found, person = rec.get("draft") or {}, rec.get("contacts") or {}, settings.person
    message = draft.get("message") or ""
    send = []
    if found.get("whatsapp"):
        send.append({"text": "📲 واتساب", "url": whatsapp_link(found["whatsapp"], message)})
    if found.get("email"):  # with WhatsApp too, the email button carries no body to keep the buttons light
        body = "" if found.get("whatsapp") else message
        send.append({"text": "✉️ إيميل", "url": gmail_link(found["email"], draft.get("subject") or rec["title"], body)})
    if found.get("telegram"):
        send.append({"text": "💬 تلگرام", "url": f"https://t.me/{found['telegram']}"})
    apply_url = found.get("apply_url") or ""
    if apply_url.startswith("http") and apply_url != rec["url"]:
        send.append({"text": "📝 رابط التقديم", "url": apply_url})
    if message and not on_platform(rec["url"]):  # platform proposals are pasted on the platform itself
        link = f"https://github.com/{person['github']}" if person.get("github") else (person.get("website") or rec["url"])
        send.append({"text": "📤 إرسال المسودة", "url": telegram_share_link(message, link)})
    info = [{"text": "🔗 الإعلان", "url": rec["url"]}]
    if settings.site_url:
        info.append({"text": "📄 التفاصيل", "url": f"{settings.site_url}#{rec['id']}"})
    return [send[i : i + 3] for i in range(0, len(send), 3)] + [info]


def announce(settings, store, picks: list[dict], summary: str = "") -> tuple[int, list[str]]:
    """One message per pick; returns (sent, errors).

    A delivered pick gets `notified_at` and its message id is remembered so replies can update its status.
    Without the bot secrets nothing is marked, so the picks go out once the bot is set up. A pick whose
    message fails does not block the others and is retried on the next runs (three tries).
    """
    sent, errors = 0, []
    memory = store.state.setdefault("telegram", {}).setdefault("messages", {})
    for n, rec in enumerate(picks, 1):
        text, keyboard = pick_message(settings, rec, n, len(picks), summary)
        try:
            message = send(settings, text, keyboard)
        except Exception as exc:
            rec["notify_tries"] = rec.get("notify_tries", 0) + 1
            errors.append(f"{rec['id']}: {exc}")
            continue
        if message:
            memory[str(message.get("message_id"))] = rec["id"]
            rec["notified_at"] = iso_time(settings.now)
            rec.pop("notify_tries", None)
            sent += 1
    for key in sorted(memory, key=int)[:-300]:  # keep the map small
        del memory[key]
    return sent, errors


def help_text(settings) -> str:
    lines = [
        "👋 هذا بوت «فرصة»: كل 6 ساعات يدوّر فرص شغل ويرسل أفضلها هنا، وإذا ماكو شي جديد موثوق ما يرسل.",
        "• كل فرصة برسالة وحدها: ليش تناسبك، أي مشروع ينعرض، المسودة، وأزرار الإرسال.",
        "• للتحديث: الرد على رسالة الفرصة بكلمة «قدمت» أو «مقابلة» أو «ما تهمني».",
        "• البوت يقرا الرسائل مع كل تشغيل، فالجواب يوصل خلال ساعات مو فوراً.",
    ]
    if settings.site_url:
        lines.append(f"• كل الفرص والمشاريع: {settings.site_url}")
    return "\n".join(lines)


def reply_status(text: str) -> str | None:
    """A short reply like «قدمت» or "/applied <id>". Long texts (a shared draft, a note) never change a status."""
    words = normalize(text)
    if len(words) > 200:
        return None
    command = re.match(r"^/(\w+)", words)
    if command and command.group(1) in REPLY_WORDS:
        return command.group(1)
    for status, options in REPLY_WORDS.items():
        for option in map(normalize, options):
            # English words whole ("sent" is not "represent"); Arabic ones may carry a prefix (وقدمت)
            if (re.search(rf"\b{re.escape(option)}\b", words) if option.isascii() else option in words):
                return status
    return None


def poll(settings, store) -> list[tuple[dict, str]]:
    """Apply status replies sent to the bot since the last run. Returns [(record, status)]."""
    if not configured(settings):
        return []
    tg = store.state.setdefault("telegram", {})
    memory = tg.setdefault("messages", {})
    updates = _call(settings, "getUpdates", {"offset": tg.get("offset", 0) + 1, "timeout": 0, "allowed_updates": ["message"]})
    applied, wants_help = [], False
    for update in updates or []:
        tg["offset"] = max(tg.get("offset", 0), update.get("update_id", 0))
        message = update.get("message") or {}
        if str((message.get("chat") or {}).get("id")) != str(settings.telegram_chat):
            continue  # only the owner's chat may change the memory
        text = message.get("text") or ""
        if re.match(r"^/(start|help)\b", text.strip()):
            wants_help = True
            continue
        replied = str((message.get("reply_to_message") or {}).get("message_id", ""))
        opp_id = memory.get(replied)
        explicit = re.search(r"\b([0-9a-f]{12})\b", text)
        if explicit:
            opp_id = explicit.group(1)
        status = reply_status(text)
        if opp_id and status and apply_status(store, opp_id, status, text):
            applied.append((store.opps[opp_id], status))
    if wants_help:  # one answer, however many times /start was pressed
        send(settings, help_text(settings))
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
