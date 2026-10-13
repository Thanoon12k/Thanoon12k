"""The manager (strong model): final review of the team's work, plus weekly income ideas.

One call per run reviews every fresh draft together and approves at most
`max_picks`. Without AI the best-scored drafts are approved by rule and marked so.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from .scoring import normalize
from .text import age_days, clip, iso_time

NULLABLE = {"anyOf": [{"type": "string"}, {"type": "null"}]}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["approve", "reject"]},
                    "rank": {"type": "integer"},
                    "note_ar": {"type": "string"},
                    "fixed_message": NULLABLE,
                },
                "required": ["id", "decision", "rank", "note_ar", "fixed_message"],
                "additionalProperties": False,
            },
        },
        "summary_ar": {"type": "string"},
    },
    "required": ["picks", "summary_ar"],
    "additionalProperties": False,
}

IDEAS_SCHEMA = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title_ar": {"type": "string"},
                    "why_ar": {"type": "string"},
                    "steps_ar": {"type": "array", "items": {"type": "string"}},
                    "effort": {"type": "string", "enum": ["low", "medium", "high"]},
                    "where": {"type": "string"},
                },
                "required": ["title_ar", "why_ar", "steps_ar", "effort", "where"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["ideas"],
    "additionalProperties": False,
}


NEUTRAL_AR = ("Address the developer as 'you'; prefer Arabic wording that reads the same for any reader "
              "(avoid gendered verb endings where you can).")


def review_system(settings, max_picks: int) -> str:
    p = settings.person
    return (
        f"You manage a 3-agent job-hunting team (scout, portfolio matcher, writer) for {p.get('name', 'the developer')}, "
        f"{p.get('headline', 'a Flutter and Django developer')} in {p.get('city', 'Mosul, Iraq')}. Review their work like a "
        f"strict editor. Approve at most {max_picks} postings, and only when: the posting looks real and current, the developer can "
        "take it from Iraq (or the doubt is clearly stated), the pay or value is worth the developer's time, and the draft is truthful, "
        "specific and ready to send. Approve at most one posting per company (the same job in two cities counts once; "
        "keep the one easier to reach from Mosul). Reject the rest. note_ar: max 60 words in Iraqi Arabic dialect, addressed to the developer: why it fits, "
        "what to check before applying, which project to show first. If an approved draft has a factual problem or a weak "
        "opening, return the corrected full message in fixed_message (same language, same channel, keep any [placeholders] "
        "and {NAME}-style tokens), otherwise null. rank 1 is best. Never promise income. summary_ar: one line in Iraqi "
        "Arabic about this batch. " + NEUTRAL_AR
    )


def _brief(rec: dict) -> dict:
    scout, match, draft = rec.get("scout") or {}, rec.get("match") or {}, rec.get("draft") or {}
    return {
        "id": rec["id"], "title": rec["title"], "company": rec.get("company"), "source": rec.get("source_label"),
        "url": rec["url"], "kind": rec.get("kind"), "posted": rec.get("posted"), "pay": rec.get("pay"),
        "location": rec.get("location"), "eligibility": rec.get("elig"), "eligibility_note": rec.get("elig_note"),
        "verified": (rec.get("extra") or {}).get("verified", "from the source feed"),
        "red_flags": scout.get("red_flags", []), "brief": scout.get("brief") or rec.get("summary"),
        "fit": match.get("fit"), "fit_reason_ar": match.get("fit_reason_ar"),
        "repos": [f"{r['name']}: {r.get('why', '')}" for r in match.get("repos", [])],
        "draft": {"channel": draft.get("channel"), "subject": draft.get("subject"),
                  "message": clip(draft.get("message"), 1200), "cv_bullets": draft.get("cv_bullets", [])},
    }


def _approve(store, rec: dict, rank: int, note: str, ai: bool, now) -> None:
    store.set_status(rec, "approved", manager={"rank": rank, "rank_score": 100 - rank, "note_ar": note, "ai": ai, "at": iso_time(now)})


def review(ctx, recs: list[dict]) -> list[dict]:
    """Final review of drafted postings. Returns the newly approved records, best first."""
    if not recs:
        return []
    settings, store = ctx.settings, ctx.store
    max_picks = settings.agent_int("max_picks", 3)
    result = None
    if ctx.llm is not None and ctx.llm.available("manager"):
        payload = {"today": settings.now.strftime("%Y-%m-%d"), "postings": [_brief(r) for r in recs]}
        result = ctx.llm.structured("manager", review_system(settings, max_picks), payload, REVIEW_SCHEMA, max_tokens=12000)

    approved = []
    if result:
        by_id = {r["id"]: r for r in recs}
        picks = sorted((p for p in result["picks"] if p.get("id") in by_id), key=lambda p: p.get("rank", 99))
        for pick in picks:
            rec = by_id.pop(pick["id"])
            if pick["decision"] == "approve" and len(approved) < max_picks:
                if pick.get("fixed_message"):
                    from .writer import ensure_website, fill_tokens

                    lang = (rec.get("draft") or {}).get("lang", "en")
                    rec["draft"]["message"] = ensure_website(fill_tokens(pick["fixed_message"], settings.person, lang), settings.person, lang)
                    rec["draft"]["edited_by_manager"] = True
                _approve(store, rec, len(approved) + 1, pick.get("note_ar", ""), True, settings.now)
                approved.append(rec)
            else:
                store.set_status(rec, "rejected", reject_reason="manager: " + clip(pick.get("note_ar"), 200))
        for rec in by_id.values():  # not mentioned by the manager: keep for the next review
            rec.setdefault("manager_skips", 0)
            rec["manager_skips"] += 1
            if rec["manager_skips"] >= 2:
                store.set_status(rec, "rejected", reject_reason="manager did not pick it twice")
        store.state["last_summary_ar"] = result.get("summary_ar", "")
        return approved

    # rules only: a stricter bar, best fit first, honest note
    min_score = int(settings.search.get("min_score", 8)) + 6
    strong = [r for r in recs if r.get("elig") in ("yes", "likely") and (r.get("score") or 0) >= min_score
              and (r.get("match") or {}).get("fit", 0) >= 70]
    ranked = sorted(strong, key=lambda r: (-(r.get("match") or {}).get("fit", 0), -(r.get("score") or 0)))
    week_ago = iso_time(settings.now - timedelta(days=7))
    taken = {_company(r): r["title"] for r in store.items("approved") if (r.get("manager") or {}).get("at", "") >= week_ago}
    for rec in ranked:
        if len(approved) >= max_picks:
            break
        company = _company(rec)
        if company and company in taken:  # the same job in another city, or a second post by the same company
            store.set_status(rec, "rejected", reject_reason=f"same company as another pick: {clip(taken[company], 80)}")
            continue
        taken[company] = rec["title"]
        note = "اختيار تلقائي بدون مراجعة المدير (ماكو مفتاح API أو انتهت الميزانية)، ويحتاج مراجعة الإعلان والمسودة قبل الإرسال."
        _approve(store, rec, len(approved) + 1, note, False, settings.now)
        approved.append(rec)
    return approved


def _company(rec: dict) -> str:
    return normalize(rec.get("company") or "").strip()


IDEAS_SYSTEM = (
    "You advise a developer in Mosul, Iraq who needs income soon. Address the developer as 'you'; prefer Arabic wording that reads the same for any reader (avoid gendered verb endings where you can). Suggest exactly 3 concrete ways to earn money in the "
    "next 30 days by reusing what they have already built. Be realistic for someone in Iraq (payment methods that work "
    "there, Arabic and local markets as well as remote clients). No guaranteed income, no crypto trading, no MLM, no "
    "paid courses they must buy. Each idea: title_ar, why_ar (max 40 words, Iraqi Arabic, cite their repos or the demand "
    "data), steps_ar (3 short first steps), effort, where (platform or channel)."
)


def ideas(ctx) -> bool:
    """Weekly: three income ideas from the portfolio and what the market asked for lately."""
    settings, store = ctx.settings, ctx.store
    if ctx.llm is None or not ctx.llm.available("manager"):
        return False
    demand = Counter()
    for rec in store.items():
        if rec.get("status") != "rejected" and (age_days(rec.get("first_seen"), settings.now) or 0) <= 30:
            demand.update(rec.get("tags") or [])
    payload = {
        "today": settings.now.strftime("%Y-%m-%d"),
        "facts": settings.person.get("facts", []),
        "repos": [{"name": r["name"], "summary": clip(r.get("summary_en"), 160), "tags": r.get("tags", [])[:8]}
                  for r in store.portfolio[:15]],
        "demand_last_30_days": dict(demand.most_common(12)),
    }
    result = ctx.llm.structured("manager", IDEAS_SYSTEM, payload, IDEAS_SCHEMA, max_tokens=8000)
    if not result:
        return False
    store.ideas = {"at": iso_time(settings.now), "ideas": result["ideas"][:3]}
    store.touch("ideas")
    return True
