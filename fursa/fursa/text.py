"""Small text, URL and date helpers shared by every module."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_BLOCK_TAGS = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr|table|section|article)\b[^>]*>", re.I)
_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"[ \t\r\f\v ]+")
_NEWLINES = re.compile(r"\n\s*\n+")
_TRACKING = ("utm_", "ref", "fbclid", "gclid", "mc_", "trk", "trackingid", "refid")


def html_to_text(value: str | None) -> str:
    """Turn an HTML fragment into readable plain text."""
    if not value:
        return ""
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", value, flags=re.I | re.S)
    text = _BLOCK_TAGS.sub("\n", text)
    text = _TAGS.sub(" ", text)
    text = html.unescape(text)
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _NEWLINES.sub("\n", text).strip()


def clip(value: str | None, limit: int) -> str:
    """Shorten text to at most `limit` characters, cutting at a word boundary."""
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    cut = value[: limit - 1]
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,.;:-") + "…"


def norm_url(url: str) -> str:
    """Canonical form of a URL so the same posting always gets the same id."""
    parts = urlsplit((url or "").strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith(_TRACKING)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", parts.netloc.lower(), path, urlencode(query), ""))


def make_id(url: str) -> str:
    return hashlib.sha1(norm_url(url).encode("utf-8")).hexdigest()[:12]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_date(value) -> datetime | None:
    """Parse the many date shapes job feeds use; always returns aware UTC or None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        number = float(value)
        if number > 1e12:  # milliseconds
            number /= 1000
        return datetime.fromtimestamp(number, tz=timezone.utc)
    text = str(value).strip()
    # DD/MM/YYYY HH:MM:SS GMT (Khamsat)
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?", text)
    if match:
        d, m, y, hh, mm, ss = match.groups()
        return datetime(int(y), int(m), int(d), int(hh or 0), int(mm or 0), int(ss or 0), tzinfo=timezone.utc)
    iso = text.replace("Z", "+00:00")
    if re.match(r"^\d{4}-\d{2}-\d{2} \d", iso):
        iso = iso.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(iso)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def iso_day(value) -> str | None:
    parsed = parse_date(value)
    return parsed.strftime("%Y-%m-%d") if parsed else None


def iso_time(value: datetime | None = None) -> str:
    return (value or now_utc()).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def age_days(value, now: datetime | None = None) -> float | None:
    parsed = parse_date(value)
    if not parsed:
        return None
    return ((now or now_utc()) - parsed).total_seconds() / 86400


def money(low, high, currency: str | None = None, period: str | None = None) -> str | None:
    """Format a stated pay range; returns None when nothing was stated."""
    def fmt(n):
        n = float(n)
        return f"{n / 1000:g}k" if n >= 1000 else f"{n:g}"

    low = low if low not in (None, "", 0, "0") else None
    high = high if high not in (None, "", 0, "0") else None
    if low is None and high is None:
        return None
    cur = (currency or "").upper()
    sign = "$" if cur in ("", "USD") else ""
    suffix = f" {cur}" if cur and cur != "USD" else ""
    span = f"{sign}{fmt(low)}–{sign}{fmt(high)}" if low and high and low != high else f"{sign}{fmt(low or high)}"
    per = f"/{period}" if period else ""
    return f"{span}{suffix}{per}"
