"""Public Telegram channels, read through Telegram's own web preview (https://t.me/s/<channel>).

No account, no bot and no API key: only public channels with the preview turned
on. One request per channel per run, with a pause between channels. Channels are
listed in profile.toml [telegram]; Iraqi ones get "Iraq" as their location.
Official channels of freelance platforms (e.g. @nafezly) post each new project with
its link; that project page then counts as the original posting.
"""

import logging
import re
import time

from .. import net
from ..text import clip, html_to_text
from . import opportunity

log = logging.getLogger("fursa.telegram")
NAME, LABEL, EVERY_HOURS = "telegram", "Telegram", 6
PREVIEW = "https://t.me/s/{}"

_POST = re.compile(r'data-post="([\w]+)/(\d+)"')
_TEXT = re.compile(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
_TIME = re.compile(r'<time datetime="([^"]+)"')
_HREF = re.compile(r'href="(https?://[^"]+)"')
_FREELANCE = re.compile(r"(freelanc|مشروع|مستقل|عمل حر|بالقطعة)", re.I)
_FIELD = re.compile(
    r"^\W*(title|job title|position|company name|company|location|anywhere|budget|المسمى الوظيفي|العنوان الوظيفي|عنوان المشروع"
    r"|الوظيفة|الشركة|الموقع|المكان|الميزانية)"
    r"\s*[:：]\s*(.+?)\s*$",
    re.I | re.M,
)
_NOISE = re.compile(r"^\W*(published time|posted|date|job opportunity|tags|ready to apply|apply|تم إضافة مشروع جديد)\b", re.I)
_PLATFORM = re.compile(r"https://(?:www\.)?(?:nafezly\.com/project|mostaql\.com/project|khamsat\.com/community/requests)/\d+", re.I)
FIELD_KEYS = {
    "title": "title", "job title": "title", "position": "title", "المسمى الوظيفي": "title", "العنوان الوظيفي": "title",
    "الوظيفة": "title", "عنوان المشروع": "title", "company name": "company", "company": "company", "الشركة": "company",
    "location": "location", "الموقع": "location", "المكان": "location", "anywhere": "anywhere",
    "budget": "pay", "الميزانية": "pay",
}


def fields(body: str) -> dict:
    """Pull 'Title : …', 'Company: …', '📍 الموقع: …' style lines that many job channels use."""
    found = {}
    for key, value in _FIELD.findall(body):
        found.setdefault(FIELD_KEYS[key.lower()], value.strip())
    return found


def headline(body: str) -> str:
    for line in body.split("\n"):
        line = line.strip(" -–•*#📌📢🔴🔵✅🚀💼🔥🟥⬅️")
        if len(line) > 8 and not _NOISE.match(line):
            return line
    return body


def channels(settings) -> tuple[list[str], set[str]]:
    cfg = settings.profile.get("telegram", {})
    iraq = [c.lstrip("@") for c in cfg.get("iraq_channels", [])]
    other = [c.lstrip("@") for c in cfg.get("channels", [])]
    return iraq + [c for c in other if c not in iraq], {c.lower() for c in iraq}


def parse(page: str, channel: str, in_iraq: bool = False) -> list[dict]:
    out = []
    for block in page.split('<div class="tgme_widget_message_wrap')[1:]:
        post, text, when = _POST.search(block), _TEXT.search(block), _TIME.search(block)
        if not post or not text:
            continue
        body = html_to_text(text.group(1))
        if len(body) < 30:  # stickers, photos without a caption, one-word posts
            continue
        links = [u for u in _HREF.findall(text.group(1)) if "t.me/" not in u and "telegram.org" not in u]
        if links and links[0] not in body:  # the "apply" link is usually hidden behind link text; keep it visible
            body += f"\nApply: {links[0]}"
        info = fields(body)
        location = info.get("location")
        if (info.get("anywhere") or "").lower().startswith("yes"):
            location = "Worldwide"
        if in_iraq:
            location = f"Iraq - {location}" if location else "Iraq"
        post_url = f"https://t.me/{post.group(1)}/{post.group(2)}"
        platform = next((u for u in links if _PLATFORM.match(u)), None)
        extra = {"channel": post.group(1), **({"apply_url": links[0]} if links else {})}
        if platform:
            extra["telegram_post"] = post_url
        out.append(
            opportunity(
                NAME, f"Telegram @{post.group(1)}", platform or post_url,
                clip(info.get("title") or headline(body), 120), clip(info.get("company") or "", 80), body,
                posted=when.group(1) if when else None,
                location=location,
                remote=True if platform else None,
                kind="freelance" if _FREELANCE.search(body) else "job",
                pay=clip(info.get("pay"), 80) or None,
                extra=extra,
            )
        )
    return out


def available(ctx) -> tuple[bool, str]:
    names, _ = channels(ctx.settings)
    return (True, "") if names else (False, "no channels in profile.toml [telegram]")


def fetch(ctx) -> list[dict]:
    names, iraq = channels(ctx.settings)
    out, failed = [], []
    for n, channel in enumerate(names):
        if n:
            time.sleep(1.5)  # be gentle with t.me
        try:
            out.extend(parse(net.get_text(PREVIEW.format(channel)), channel, channel.lower() in iraq))
        except Exception as exc:  # one closed or renamed channel must not stop the others
            failed.append(channel)
            log.info("telegram @%s skipped: %s", channel, exc)
    if failed and len(failed) == len(names):
        raise net.SourceError(f"no channel could be read ({', '.join(failed[:3])}…)")
    return out
