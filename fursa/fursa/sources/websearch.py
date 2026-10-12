"""Claude web search: the only way to see LinkedIn, X, Facebook and Google results.

Runs every `web_search_every_hours` with at most `web_search_max_uses` searches,
rotating through the angles below, so the cost stays at a few cents a day.
Results are search snippets: the scout and the manager treat them as unverified.
"""

from ..llm import extract_json_array
from . import opportunity

NAME, LABEL, EVERY_HOURS = "websearch", "Web search", 24


def every_hours(settings) -> float:
    return float(settings.agents.get("web_search_every_hours", EVERY_HOURS))

ANGLES = (
    '"Flutter developer" remote job worldwide OR anywhere site:linkedin.com/jobs',
    '"Django developer" OR "Python Django" remote job worldwide site:linkedin.com/jobs',
    "مطلوب مبرمج فلاتر Flutter العراق OR الموصل OR بغداد OR أربيل",
    "وظيفة مطور بايثون Django العراق",
    '"hiring" "Flutter developer" remote site:x.com',
    "Flutter developer job Iraq Erbil OR Baghdad OR Mosul",
    "site:facebook.com مطلوب مبرمج تطبيقات Flutter العراق",
    '"Python developer" remote MENA OR "Middle East" hiring',
    "مطلوب مطور تطبيقات موبايل عن بعد فلاتر",
    'NGO Iraq vacancy "IT officer" OR developer OR "database officer" Ninewa OR Mosul',
    '"Django" contract remote worldwide hiring',
    'Flutter freelance project "remote" "Middle East" OR Arabic',
)

SYSTEM = (
    "You are the scout of a small job-hunting team. Use the web_search tool to find paid work that was "
    "posted recently and is still open. Report only postings you actually saw in search results, with the "
    "URL of the original posting. Never invent URLs, dates, pay, company names or contact details: write null "
    "when a value is not shown. Skip anything that asks applicants to pay. Finish with ONLY a JSON array."
)


def available(ctx) -> tuple[bool, str]:
    if not ctx.settings.agents.get("web_search", True):
        return False, "switched off in profile.toml"
    if ctx.llm is None:
        return False, "needs the AI key (free mode)"
    if not ctx.llm.available("worker"):
        return False, ctx.llm.disabled_reason or "AI unavailable"
    return True, ""


def prompt(settings, angles: list[str]) -> str:
    person = settings.person
    return (
        f"Today is {settings.now:%Y-%m-%d}. Candidate: {person.get('headline', 'Flutter and Django developer')}, "
        f"living in {person.get('city', 'Mosul, Iraq')}. They can take remote work open to Iraq (worldwide, MENA), "
        "on-site or hybrid work in Iraq, freelance projects and paid tasks.\n"
        "Run one search for each of these angles:\n- " + "\n- ".join(angles) + "\n\n"
        "Keep only postings from the last 21 days. Return up to 8 items as a JSON array of objects with keys: "
        '"title", "company", "url", "platform", "posted" (YYYY-MM-DD or null), "location" (as written, or null), '
        '"pay" (as written, or null), "kind" ("job"|"freelance"|"gig"|"bounty"), "language" ("ar"|"en"), '
        '"snippet" (what the result says, max 300 characters).'
    )


def to_records(items: list) -> list[dict]:
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        if not url.startswith("http"):
            continue
        kind = item.get("kind") if item.get("kind") in ("job", "freelance", "gig", "bounty") else "job"
        platform = str(item.get("platform") or "web")
        out.append(
            opportunity(
                NAME, f"{platform} (web search)", url, str(item.get("title") or ""), str(item.get("company") or ""),
                str(item.get("snippet") or ""),
                posted=item.get("posted"),
                location=item.get("location"),
                kind=kind,
                pay=item.get("pay"),
                lang=item.get("language") if item.get("language") in ("ar", "en") else None,
                extra={"verified": "search result only"},
            )
        )
    return out


def fetch(ctx) -> list[dict]:
    uses = int(ctx.settings.agents.get("web_search_max_uses", 4))
    turn = int(ctx.store.state.get("websearch_turn", 0))
    angles = [ANGLES[(turn * uses + i) % len(ANGLES)] for i in range(uses)]
    ctx.store.state["websearch_turn"] = turn + 1
    text = ctx.llm.search(SYSTEM, prompt(ctx.settings, angles), max_uses=uses)
    return to_records(extract_json_array(text))
