"""Zero-token judgement: relevance score, Iraq eligibility hint, scam/fee flags, freshness.

Everything here is plain code so the AI only ever sees postings worth its tokens.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .text import age_days, parse_date

# keyword -> tag shown on the dashboard and used for matching repos
TAG_ALIASES = {
    "flutter": "flutter", "فلاتر": "flutter", "فلتر": "flutter", "dart": "dart",
    "django": "django", "جانغو": "django", "دجانغو": "django", "django rest": "django", "drf": "django",
    "python": "python", "بايثون": "python", "fastapi": "fastapi", "flask": "flask",
    "firebase": "firebase", "supabase": "supabase", "bloc": "flutter",
    "mobile app": "mobile", "mobile developer": "mobile", "cross-platform": "mobile",
    "تطبيق جوال": "mobile", "تطبيق موبايل": "mobile", "تطبيق اندرويد": "mobile",
    "rest api": "api", "backend": "backend", "لوحة تحكم": "dashboard",
    "opencv": "opencv", "arduino": "iot", "iot": "iot",
    "automation": "automation", "اتمتة": "automation", "scraping": "automation", "playwright": "automation",
    "ai agent": "ai", "chatbot": "ai",
}

_AR_NORMAL = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ـ": None})
_AR_DIACRITICS = re.compile(r"[ً-ْٰ]")

# location wording that means "Iraq can apply"
OPEN_WORDS = (
    "worldwide", "anywhere", "global", "globally", "international", "all countries", "any country",
    "any location", "remote (global)", "iraq", "العراق", "عن بعد من اي دولة",
)
REGION_WORDS = ("mena", "middle east", "emea", "asia", "arab", "gulf", "gcc", "gmt+3", "utc+3", "الشرق الاوسط", "الوطن العربي")
# phrases that rule an applicant in Iraq out
CLOSED_PHRASES = (
    "us citizen", "u.s. citizen", "us only", "usa only", "u.s. only", "united states only", "us-based only",
    "must be based in the us", "must reside in the us", "authorized to work in the us", "authorized to work in the united states",
    "security clearance", "w-2 only", "w2 only", "canada only", "uk only", "right to work in the uk",
    "eu only", "eu work permit", "must be located in europe", "europe only", "latam only", "north america only",
)
FEE_PHRASES = (
    "registration fee", "training fee", "application fee", "pay a fee", "pay to apply", "deposit required",
    "security deposit", "send money", "investment required", "upfront payment", "pay for training",
    "رسوم تسجيل", "رسوم اشتراك", "رسوم التسجيل", "دفع رسوم", "رسوم تدريب", "مبلغ تأمين", "ادفع مبلغ", "ايداع مبلغ",
)


def normalize(text: str | None) -> str:
    text = (text or "").lower().translate(_AR_NORMAL)
    return _AR_DIACRITICS.sub("", text)


@lru_cache(maxsize=512)
def _pattern(keyword: str) -> re.Pattern:
    kw = normalize(keyword)
    body = re.escape(kw).replace(r"\ ", r"[\s\-]+")
    ascii_kw = kw.isascii()
    left = r"(?<![\w])" if ascii_kw and kw[:1].isalnum() else ""
    right = r"(?![\w])" if ascii_kw and kw[-1:].isalnum() else ""
    return re.compile(left + body + right)


def relevance(title: str, body: str, keywords: dict, penalties: dict | None = None) -> tuple[int, list[str]]:
    """Weighted keyword score; a title hit counts double. Returns (score, tags)."""
    t, b = normalize(title), normalize(body)
    score, tags = 0, []
    for kw, weight in {**keywords, **(penalties or {})}.items():
        pat = _pattern(kw)
        if pat.search(t):
            score += 2 * int(weight)
        elif pat.search(b):
            score += int(weight)
        else:
            continue
        if weight > 0:
            tag = TAG_ALIASES.get(kw, normalize(kw))
            if tag not in tags:
                tags.append(tag)
    return score, tags


def eligibility(location: str | None, text: str, kind: str, source: str) -> tuple[str, str]:
    """Best guess, without AI, whether someone living in Mosul can take this.

    Returns (verdict, note) with verdict in yes / likely / unclear / no.
    """
    loc = normalize(location)
    blob = normalize(text)
    for phrase in CLOSED_PHRASES:
        pat = _pattern(phrase)
        if pat.search(loc) or pat.search(blob):
            return "no", f"restriction: '{phrase}'"
    if any(w in loc for w in ("iraq", "العراق", "mosul", "الموصل", "erbil", "اربيل", "baghdad", "بغداد")):
        return "yes", "Iraq is listed"
    if any(w in loc for w in OPEN_WORDS):
        return "yes", f"open location: {location}"
    if any(w in loc for w in REGION_WORDS):
        return "likely", f"region includes Iraq: {location}"
    if kind in ("freelance", "gig"):
        return "likely", "freelance platform; check that payouts work from Iraq"
    if kind == "bounty":
        return "unclear", "bounty payout platform may not support Iraq"
    if loc and loc not in ("remote", "remote job", "remote only", "100% remote", "fully remote", "n/a"):
        return "no", f"limited to: {location}"
    if any(w in blob for w in OPEN_WORDS):
        return "likely", "description mentions worldwide/anywhere"
    return "unclear", "location not stated"


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def stated_usd(rec: dict) -> tuple[float | None, bool]:
    """Highest stated amount in USD and whether it is hourly; (None, False) when unknown."""
    extra = rec.get("extra") or {}
    pay = rec.get("pay") or ""
    hourly = "/hour" in pay or "/hr" in pay or "/h" in pay.replace("/hour", "")
    if extra.get("budget_usd_max"):
        return float(extra["budget_usd_max"]), hourly
    if "$" not in pay:
        return None, hourly
    numbers = []
    for raw in _NUMBER.findall(pay.replace("k", "000")):
        try:
            numbers.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return (max(numbers) if numbers else None), hourly


def fee_flags(text: str) -> list[str]:
    blob = normalize(text)
    return [p for p in FEE_PHRASES if normalize(p) in blob]


def assess(rec: dict, settings) -> tuple[bool, str]:
    """Score one normalized posting in place. Returns (keep, reason_if_dropped)."""
    search = settings.search
    keywords = search.get("keywords", {})
    penalties = search.get("penalties", {})
    body = rec.get("text") or rec.get("summary") or ""
    score, tags = relevance(rec.get("title", ""), " ".join([body, " ".join(rec.get("tags") or [])]), keywords, penalties)
    if rec.get("remote") or "remote" in normalize(rec.get("location")):
        score += 1
    rec["score"] = score
    rec["tags"] = tags
    elig, note = eligibility(rec.get("location"), body, rec.get("kind", "job"), rec.get("source", ""))
    rec["elig"], rec["elig_note"] = elig, note
    flags = fee_flags(" ".join([rec.get("title", ""), body]))
    rec["flags"] = ["fee: " + f for f in flags]

    kind = rec.get("kind", "job")
    if kind not in search.get("kinds", ["job", "freelance", "gig", "bounty"]):
        return False, f"kind '{kind}' switched off"
    if flags:
        return False, "asks the applicant to pay"
    max_age = search.get("max_age_days_freelance", 10) if kind in ("freelance", "gig") else search.get("max_age_days", 30)
    days = age_days(rec.get("posted"), settings.now)
    if days is not None and days > max_age:
        return False, f"too old ({int(days)} days)"
    expires = parse_date(rec.get("expires"))
    if expires and expires < settings.now:
        return False, "expired"
    if elig == "no":
        return False, note
    if kind in ("freelance", "gig"):
        amount, hourly = stated_usd(rec)
        floor = search.get("min_hourly_usd", 8) if hourly else search.get("min_budget_usd", 50)
        if amount is not None and amount < float(floor):
            return False, f"budget too small (${amount:g}{'/h' if hourly else ''})"
    if score < int(search.get("min_score", 8)):
        return False, f"low relevance ({score})"
    return True, ""
