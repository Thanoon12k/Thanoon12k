"""Contact details written in a posting: WhatsApp/phone, email, Telegram username, apply link.

Only what the posting itself shows; nothing is guessed. Iraqi mobile numbers
(07xx xxx xxxx) become international (9647xx...) so WhatsApp links open the chat.
"""

from __future__ import annotations

import re
from urllib.parse import quote

_WA = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send/?\?phone=)\+?(\d{8,15})", re.I)
_IQ_MOBILE = re.compile(r"(?<![\d+])(?:\+?964|00964|0)[\s-]?(7\d{2})[\s-]?(\d{3})[\s-]?(\d{4})(?!\d)")
_INTL = re.compile(r"(?<![\w+])\+(\d[\d\s-]{7,16}\d)")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_TG = re.compile(r"(?:t\.me/|telegram\.me/)([A-Za-z]\w{3,31})|(?<![\w@.])@([A-Za-z]\w{3,31})\b")
WHATSAPP_WORDS = ("whatsapp", "whats app", "واتساب", "واتس", "وتساب")
CONTACT_CUES = ("تواصل", "راسل", "مراسلة", "للتقديم", "ارسال", "إرسال", "ارسل", "أرسل", "contact", "dm", "message", "apply", "send", "cv")
SKIP_TG = {"share", "joinchat", "addstickers", "proxy", "iv"}
SKIP_EMAIL = ("example.com", "sentry.io", "noreply", "no-reply")


def extract(text: str | None, *, apply_url: str | None = None, channel: str | None = None) -> dict:
    text = text or ""
    found: dict[str, str] = {}
    wa = _WA.search(text)
    if wa:
        found["whatsapp"] = wa.group(1)
    else:
        iq = _IQ_MOBILE.search(text)
        if iq:
            found["whatsapp"] = "964" + "".join(iq.groups())
        elif any(w in text.lower() for w in WHATSAPP_WORDS):
            intl = _INTL.search(text)
            if intl:
                found["whatsapp"] = re.sub(r"\D", "", intl.group(1))
    for email in _EMAIL.findall(text):
        if not any(skip in email.lower() for skip in SKIP_EMAIL):
            found["email"] = email
            break
    for match in _TG.finditer(text):
        name = match.group(1) or match.group(2)
        before = text[max(0, match.start() - 40) : match.start()].lower()
        if name.lower() in SKIP_TG or name.lower() == (channel or "").lower():
            continue
        if not any(cue in before for cue in CONTACT_CUES):
            continue  # a mention without "contact/apply" around it is usually an ad for another channel
        found["telegram"] = name
        break
    if apply_url:
        found["apply_url"] = apply_url
    return found


def clip_for_url(text: str, limit: int = 1800) -> str:
    """Prefilled messages ride inside a link; keep them to a size every app accepts."""
    text = text or ""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return cut[: cut.rfind("\n")] if "\n" in cut[limit // 2 :] else cut


def whatsapp_link(number: str, message: str = "") -> str:
    return f"https://wa.me/{number}" + (f"?text={quote(clip_for_url(message))}" if message else "")


def gmail_link(to: str, subject: str = "", body: str = "") -> str:
    url = f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(to)}&su={quote(subject or '')}"
    return url + (f"&body={quote(clip_for_url(body))}" if body else "")


def telegram_share_link(message: str, link: str) -> str:
    return f"https://t.me/share/url?url={quote(link)}&text={quote(clip_for_url(message))}"
