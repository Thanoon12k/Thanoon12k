"""Agent 2 — the portfolio matcher. Picks the 2-3 repos that best prove the user can do the job.

Code shortlists 6 repos from the index (free); the AI only chooses among them,
so it cannot cite a repository that does not exist.
"""

from __future__ import annotations

from .portfolio import SKILL_TAGS, preselect
from .text import clip

SCHEMA = {
    "type": "object",
    "properties": {
        "repos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "why": {"type": "string"}},
                "required": ["name", "why"],
                "additionalProperties": False,
            },
        },
        "fit": {"type": "integer"},
        "fit_reason_ar": {"type": "string"},
    },
    "required": ["repos", "fit", "fit_reason_ar"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are the portfolio matcher of a job-hunting team. Choose the 2-3 repositories that best prove the developer "
    "can do this work. Use only the facts given about each repository; prefer substantial work he wrote himself; never "
    "say a repository does something its facts do not show. 'why' (max 25 words, in the posting's language) tells the "
    "employer what that repository proves for this job. fit is 0-100: how well his proven skills cover the "
    "requirements. fit_reason_ar: max 40 words in Iraqi Arabic dialect, to him: why it suits him and what is missing."
)


def _why(repo: dict, lang: str) -> str:
    text = (repo.get("summary_ar") if lang == "ar" else None) or repo.get("summary_en")
    if text:
        return text
    tags = ", ".join(repo.get("tags", [])[:5])
    return f"مبني بـ {tags}" if lang == "ar" else f"built with {tags}"


def _rules(rec: dict, shortlist: list[dict]) -> dict:
    lang = (rec.get("scout") or {}).get("lang") or rec.get("lang", "en")
    picks = [{"name": r["name"], "url": r["url"], "why": _why(r, lang)} for r in shortlist[:3]]
    wanted = set(rec.get("tags") or [])
    covered = set().union(*(set(r.get("tags", [])) for r in shortlist[:3])) if shortlist else set()
    hits = sum(1 for tag in wanted if SKILL_TAGS.get(tag, {tag}) & covered)
    coverage = hits / len(wanted) if wanted else 0
    fit = int(min(85, 35 + 35 * coverage + min(rec.get("score") or 0, 30) / 2)) if picks else 0
    tags = "، ".join(rec.get("tags") or []) or "عامة"
    return {"repos": picks, "fit": fit, "fit_reason_ar": f"مطابقة تلقائية حسب المهارات ({tags}) بدون مراجعة ذكاء اصطناعي.", "ai": False}


def run(ctx, recs: list[dict]) -> int:
    by_ai = 0
    for rec in recs:
        shortlist = preselect(rec, ctx.store.portfolio, k=6)
        result = None
        if shortlist and ctx.llm is not None and ctx.llm.available("worker"):
            scout = rec.get("scout") or {}
            payload = {
                "posting": {"title": rec["title"], "company": rec.get("company"), "kind": rec.get("kind"),
                            "brief": scout.get("brief") or rec.get("summary"), "skills": scout.get("skills") or rec.get("tags"),
                            "language": scout.get("lang") or rec.get("lang")},
                "repos": [{"name": r["name"], "summary": clip(r.get("summary_en"), 200), "tags": r.get("tags", [])[:12],
                           "maturity": r.get("maturity"), "own_share": r.get("own_share"), "tests": r.get("has_tests")}
                          for r in shortlist],
            }
            result = ctx.llm.structured("worker", SYSTEM, payload, SCHEMA, max_tokens=2500)
        if result:
            urls = {r["name"]: r["url"] for r in shortlist}
            picks = [{"name": p["name"], "url": urls[p["name"]], "why": p["why"]} for p in result["repos"] if p.get("name") in urls][:3]
            if picks:
                match = {"repos": picks, "fit": max(0, min(100, int(result["fit"]))), "fit_reason_ar": result["fit_reason_ar"], "ai": True}
                by_ai += 1
            else:
                match = _rules(rec, shortlist)
        else:
            match = _rules(rec, shortlist)
        ctx.store.set_status(rec, "matched", match=match)
    return by_ai
