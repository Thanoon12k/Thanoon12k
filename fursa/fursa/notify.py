"""Telegram alerts: one short digest per run, only when the manager approved something new."""

from __future__ import annotations

import html
import logging
from datetime import timedelta

from . import net
from .text import clip

log = logging.getLogger("fursa.notify")

KIND_AR = {"job": "وظيفة", "freelance": "مشروع حر", "gig": "مهمة صغيرة", "bounty": "مكافأة bounty"}
ELIG_AR = {"yes": "✅ متاح للعراق", "likely": "🟡 غالباً متاح", "unclear": "⚠️ الأهلية غير محسومة", "no": "❌ غير متاح"}


def _e(value) -> str:
    return html.escape(str(value or ""), quote=False)


def digest(settings, picks: list[dict], summary: str = "") -> str:
    lines = [f"🎯 <b>فرصة: {len(picks)} {'فرصة جديدة' if len(picks) == 1 else 'فرص جديدة'}</b>"]
    if summary:
        lines.append(_e(clip(summary, 200)))
    for n, rec in enumerate(picks, 1):
        match = rec.get("match") or {}
        manager = rec.get("manager") or {}
        meta = " · ".join(x for x in (KIND_AR.get(rec.get("kind"), rec.get("kind")), rec.get("location"), ELIG_AR.get(rec.get("elig"), "")) if x)
        lines.append("")
        lines.append(f"{n}) <b>{_e(clip(rec['title'], 90))}</b>" + (f" — {_e(rec['company'])}" if rec.get("company") else ""))
        lines.append(_e(meta))
        if rec.get("pay"):
            lines.append(f"💵 {_e(rec['pay'])}")
        if rec.get("posted"):
            lines.append(f"📅 {_e(rec['posted'])} · {_e(rec.get('source_label'))}")
        note = manager.get("note_ar") or match.get("fit_reason_ar")
        if note:
            lines.append(f"💡 {_e(clip(note, 260))}")
        repos = ", ".join(r["name"] for r in match.get("repos", [])[:3])
        if repos:
            lines.append(f"🧩 {_e(repos)}")
        links = [f'<a href="{_e(rec["url"])}">الإعلان</a>']
        if settings.site_url:
            links.append(f'<a href="{_e(settings.site_url)}#{rec["id"]}">المسودة والتفاصيل</a>')
        lines.append("🔗 " + " · ".join(links))
    text = "\n".join(lines)
    return text if len(text) < 4000 else text[:3990] + "…"


def quiet(settings) -> bool:
    local = settings.now + timedelta(hours=3)  # Iraq time (UTC+3)
    return local.hour < 8


def send(settings, text: str) -> bool:
    if not (settings.telegram_token and settings.telegram_chat):
        log.info("Telegram not configured; digest not sent")
        return False
    response = net.session().post(
        f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
        json={
            "chat_id": settings.telegram_chat,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": quiet(settings),
        },
        timeout=30,
    )
    if not response.ok:
        log.warning("Telegram refused the message: %s", response.text[:200])
    return response.ok


def chat_ids(settings) -> list[tuple[str, str]]:
    """Helper for setup: who has messaged the bot (send /start to it first)."""
    data = net.get_json(f"https://api.telegram.org/bot{settings.telegram_token}/getUpdates")
    found = {}
    for update in data.get("result", []):
        chat = (update.get("message") or update.get("my_chat_member") or {}).get("chat") or {}
        if chat.get("id"):
            found[str(chat["id"])] = chat.get("username") or chat.get("title") or chat.get("first_name") or ""
    return sorted(found.items())
