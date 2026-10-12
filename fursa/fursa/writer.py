"""Agent 3 — the writer. CV bullets plus an email, WhatsApp message or platform proposal.

The AI writes {NAME}/{EMAIL}/... tokens instead of personal details; code fills
them from profile.toml, so contact details are never invented. Unknown facts stay
as visible [placeholders] for the user to fill.
"""

from __future__ import annotations

from .text import clip

NULLABLE = {"anyOf": [{"type": "string"}, {"type": "null"}]}
SCHEMA = {
    "type": "object",
    "properties": {
        "cv_bullets": {"type": "array", "items": {"type": "string"}},
        "subject": NULLABLE,
        "message": {"type": "string"},
    },
    "required": ["cv_bullets", "subject", "message"],
    "additionalProperties": False,
}

SYSTEM = (
    "You write job applications for one developer. Use ONLY the facts and repositories given. Never invent years, "
    "numbers, clients, certificates, salaries or results; where a needed detail is unknown write a placeholder in "
    "square brackets, e.g. [expected rate]. Use these tokens exactly where his details belong: {NAME}, {EMAIL}, "
    "{PHONE}, {WEBSITE}, {GITHUB}. Write in the requested language (Arabic: clear, polite Modern Standard Arabic; "
    "English: plain and confident, no clichés). Channel rules: email = a subject line and 120-180 words; whatsapp = "
    "no subject, 50-90 friendly words; platform = a freelance proposal with no subject, 90-150 words: show you "
    "understood the task, give a 3-step plan, link the relevant repositories, end with one question; linkedin, form "
    "or other = an 80-120 word cover note. Link 2-3 repositories naturally (full URLs). cv_bullets: 3-5 lines for "
    "this posting, each starting with a verb, facts only."
)

TEMPLATES = {
    "en": (
        "Application: {title}",
        "Hello{team},\n\nI'm {{NAME}}, a Flutter and Django developer based in Mosul, Iraq. Your post for \"{title}\" "
        "matches work I have already built:\n{repos}\n\nI can share more details about my approach and availability. "
        "Portfolio: {{WEBSITE}} · GitHub: {{GITHUB}}\n\nBest regards,\n{{NAME}}\n{{EMAIL}} · {{PHONE}}",
    ),
    "ar": (
        "طلب تقديم: {title}",
        "السلام عليكم{team}،\n\nأنا {{NAME}}، مطوّر Flutter وDjango من الموصل، العراق. اطلعت على إعلانكم \"{title}\" "
        "ولدي أعمال قريبة منه:\n{repos}\n\nيسعدني توضيح طريقة التنفيذ والمدة المتوقعة. معرض أعمالي: {{WEBSITE}} · GitHub: {{GITHUB}}\n\n"
        "مع التحية،\n{{NAME}}\n{{EMAIL}} · {{PHONE}}",
    ),
}


def fill_tokens(text: str | None, person: dict, lang: str) -> str | None:
    if text is None:
        return None
    missing = {
        "NAME": "[الاسم الكامل]" if lang == "ar" else "[Full name]",
        "EMAIL": "[البريد الإلكتروني]" if lang == "ar" else "[Email]",
        "PHONE": "[رقم الهاتف]" if lang == "ar" else "[Phone]",
        "WEBSITE": "[رابط معرض الأعمال]" if lang == "ar" else "[Portfolio link]",
        "GITHUB": "[رابط GitHub]" if lang == "ar" else "[GitHub link]",
    }
    values = {
        "NAME": person.get("name"), "EMAIL": person.get("email"), "PHONE": person.get("phone"),
        "WEBSITE": person.get("website"),
        "GITHUB": f"https://github.com/{person['github']}" if person.get("github") else None,
    }
    for key, placeholder in missing.items():
        text = text.replace("{" + key + "}", values.get(key) or placeholder)
    return text


def _template(rec: dict, repos: list[dict], lang: str) -> dict:
    subject, body = TEMPLATES["ar" if lang == "ar" else "en"]
    team = f" {rec['company']}" if rec.get("company") else ""
    lines = "\n".join(f"- {r['name']}: {r['url']}" for r in repos) or "-"
    return {
        "cv_bullets": [f"Built {r['name']}: {clip(r.get('why'), 140)}" for r in repos],
        "subject": subject.format(title=rec["title"]),
        "message": body.format(title=rec["title"], team=team, repos=lines),
        "ai": False,
    }


def run(ctx, recs: list[dict]) -> int:
    person = ctx.settings.person
    by_ai = 0
    for rec in recs:
        scout = rec.get("scout") or {}
        match = rec.get("match") or {}
        lang = scout.get("lang") or rec.get("lang") or "en"
        channel = scout.get("channel") or ("platform" if rec.get("kind") in ("freelance", "gig", "bounty") else "other")
        repos = match.get("repos") or []
        result = None
        if ctx.llm is not None and ctx.llm.available("worker"):
            payload = {
                "posting": {"title": rec["title"], "company": rec.get("company"), "kind": rec.get("kind"),
                            "brief": scout.get("brief") or rec.get("summary"), "skills": scout.get("skills") or rec.get("tags"),
                            "pay": rec.get("pay"), "channel": channel, "language": lang},
                "facts": person.get("facts", []) + [f"Languages: {', '.join(person.get('languages', []))}", f"Based in {person.get('city', 'Mosul, Iraq')}"],
                "repositories": [{"name": r["name"], "url": r["url"], "proves": r.get("why")} for r in repos],
            }
            result = ctx.llm.structured("worker", SYSTEM, payload, SCHEMA, max_tokens=3000)
        draft = dict(result, ai=True) if result else _template(rec, repos, lang)
        by_ai += 1 if result else 0
        draft["subject"] = fill_tokens(draft.get("subject"), person, lang) if channel == "email" or not result else None
        draft["message"] = fill_tokens(draft["message"], person, lang)
        draft["cv_bullets"] = [fill_tokens(b, person, lang) for b in draft.get("cv_bullets", [])][:5]
        draft.update({"lang": lang, "channel": channel, "contact": scout.get("contact")})
        ctx.store.set_status(rec, "drafted", draft=draft)
    return by_ai
