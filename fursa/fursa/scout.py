"""Agent 1 — the scout. Checks each new posting: real, open, paid, takeable from Iraq.

The AI sees only postings that already passed the free rules, in batches of 6,
and only a clipped text. Without AI the rules' verdict is used as is.
"""

from __future__ import annotations

import re

from .scoring import normalize
from .text import clip

BATCH = 6
NULLABLE = {"anyOf": [{"type": "string"}, {"type": "null"}]}

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer"},
                    "keep": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "eligibility": {"type": "string", "enum": ["yes", "likely", "unclear", "no"]},
                    "eligibility_note": {"type": "string"},
                    "open": {"type": "string", "enum": ["yes", "unknown", "no"]},
                    "pay": NULLABLE,
                    "work_type": {"type": "string", "enum": ["full-time", "part-time", "contract", "freelance", "gig", "bounty", "internship", "unknown"]},
                    "channel": {"type": "string", "enum": ["email", "whatsapp", "form", "platform", "linkedin", "other"]},
                    "contact": NULLABLE,
                    "lang": {"type": "string", "enum": ["ar", "en"]},
                    "red_flags": {"type": "array", "items": {"type": "string"}},
                    "brief": {"type": "string"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["i", "keep", "reason", "eligibility", "eligibility_note", "open", "pay", "work_type",
                             "channel", "contact", "lang", "red_flags", "brief", "skills"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def system_prompt(settings) -> str:
    p = settings.person
    return (
        f"You are the scout of a job-hunting team for one developer: {p.get('headline', 'Flutter and Django developer')}, "
        f"living in {p.get('city', 'Mosul, Iraq')}. They can take: remote work open to residents of Iraq, on-site or hybrid "
        "work inside Iraq, freelance projects and paid tasks. Judge each posting:\n"
        "- keep=true only if it is paid work that fits their skills (Flutter/Dart, Python/Django/Flask/FastAPI, REST APIs, "
        "automation, AI integration, IoT, teaching programming) and they can take it from Iraq.\n"
        "- eligibility: yes = Iraq or worldwide explicitly allowed; likely = a region containing Iraq, or a freelance "
        "platform; unclear = not stated; no = Iraq excluded. Explain in eligibility_note (max 15 words).\n"
        "- open: no if the text says closed, filled or expired.\n"
        "- pay and contact: copy only what the text states, else null. Never estimate or invent.\n"
        "- channel: how the text says to apply (platform = through the job board or freelance site).\n"
        "- red_flags: e.g. asks for payment, unpaid or equity only, very low budget, vague, many bids.\n"
        "- brief: max 45 words in English: what they need and the key requirements.\n"
        "- skills: up to 8 lowercase skill keywords. lang: the language to apply in.\n"
        "Return one item per input index i."
    )


def _payload(recs: list[dict], settings) -> dict:
    return {
        "today": settings.now.strftime("%Y-%m-%d"),
        "postings": [
            {
                "i": i, "title": r["title"], "company": r.get("company") or None, "source": r.get("source_label"),
                "posted": r.get("posted"), "location": r.get("location"), "kind": r.get("kind"),
                "pay_stated": r.get("pay"), "text": clip(r.get("text") or r.get("summary") or "", 1300),
            }
            for i, r in enumerate(recs)
        ],
    }


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _rules_verdict(rec: dict) -> dict:
    email = _EMAIL.search(rec.get("text") or "")
    return {
        "keep": True, "reason": "passed the free rules (no AI review)", "eligibility": rec.get("elig", "unclear"),
        "eligibility_note": rec.get("elig_note", ""), "open": "unknown", "pay": rec.get("pay"),
        "work_type": {"freelance": "freelance", "gig": "gig", "bounty": "bounty"}.get(rec.get("kind"), "unknown"),
        "channel": "email" if email else ("platform" if rec.get("kind") in ("freelance", "gig", "bounty") else "other"),
        "contact": email.group(0) if email else None, "lang": rec.get("lang", "en"), "red_flags": [],
        "brief": clip(rec.get("summary") or rec.get("title"), 300), "skills": rec.get("tags", []), "ai": False,
    }


def _apply(store, rec: dict, verdict: dict) -> None:
    text = normalize(rec.get("text") or "")
    contact = verdict.get("contact")
    if contact and normalize(contact) not in text:
        verdict["contact"] = None  # the model may not invent contact details
    if verdict.get("pay") and not rec.get("pay"):
        rec["pay"] = verdict["pay"]
    if verdict.get("eligibility") in ("yes", "likely", "unclear", "no"):
        rec["elig"], rec["elig_note"] = verdict["eligibility"], verdict.get("eligibility_note") or rec.get("elig_note")
    verdict.pop("i", None)
    rec["scout"] = verdict
    rec.pop("text", None)  # the long text is no longer needed; keeps the public file small
    if verdict.get("keep") and verdict.get("eligibility") != "no" and verdict.get("open") != "no":
        store.set_status(rec, "screened")
    else:
        store.set_status(rec, "rejected", reject_reason=verdict.get("reason") or "scout said no")


def run(ctx, recs: list[dict]) -> int:
    """Screen `recs` (status new). Returns how many were screened by AI."""
    by_ai = 0
    system = system_prompt(ctx.settings)
    for start in range(0, len(recs), BATCH):
        batch = recs[start : start + BATCH]
        result = None
        if ctx.llm is not None and ctx.llm.available("worker"):
            result = ctx.llm.structured("worker", system, _payload(batch, ctx.settings), SCHEMA, max_tokens=5000)
        verdicts = {v.get("i"): v for v in (result or {}).get("items", []) if isinstance(v, dict)}
        for i, rec in enumerate(batch):
            if i in verdicts:
                verdicts[i]["ai"] = True
                _apply(ctx.store, rec, verdicts[i])
                by_ai += 1
            elif result is None:
                _apply(ctx.store, rec, _rules_verdict(rec))
    return by_ai
