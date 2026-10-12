"""Freelancer.com public project search (active projects, no login needed to read)."""

from .. import net
from ..text import money
from . import opportunity

NAME, LABEL, EVERY_HOURS = "freelancer", "Freelancer.com", 6
API = "https://www.freelancer.com/api/projects/0.1/projects/active/"


def from_project(p: dict) -> dict | None:
    if p.get("status") != "active" or p.get("frontend_project_status") not in (None, "open"):
        return None
    if not p.get("seo_url") or p.get("language") not in (None, "en", "ar"):
        return None  # only postings he can read and answer
    budget = p.get("budget") or {}
    hourly = p.get("type") == "hourly"
    pay = money(budget.get("minimum"), budget.get("maximum"), (p.get("currency") or {}).get("code"), "hour" if hourly else None)
    if pay and not hourly:
        pay += " (fixed)"
    bids = (p.get("bid_stats") or {}).get("bid_count")
    rate = (p.get("currency") or {}).get("exchange_rate") or 1.0
    usd_max = round(float(budget.get("maximum") or budget.get("minimum") or 0) * float(rate), 2) or None
    return opportunity(
        NAME, LABEL, f"https://www.freelancer.com/projects/{p['seo_url']}",
        p.get("title"), "", p.get("description") or p.get("preview_description"),
        posted=p.get("time_submitted") or p.get("submitdate"),
        kind="freelance",
        remote=True,
        pay=pay,
        lang=p.get("language") if p.get("language") in ("ar", "en") else None,
        tags=[j.get("name", "") for j in (p.get("jobs") or [])][:8],
        extra={"bids": bids, "budget_usd_max": usd_max},
    )


def fetch(ctx) -> list[dict]:
    out = []
    for query in ctx.settings.search.get("queries", ["flutter", "django", "python"]):
        data = net.get_json(
            API,
            params={"query": query, "limit": 20, "full_description": "true", "job_details": "true", "compact": "true"},
        )
        for p in (data.get("result") or {}).get("projects", []):
            rec = from_project(p)
            if rec:
                out.append(rec)
    return out
