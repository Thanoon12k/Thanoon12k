"""Collectors. Each one turns a free public feed into the same posting shape.

A collector module exposes:
    NAME          key in profile.toml [sources]
    LABEL         name shown on the dashboard (sources ask for credit and a link back)
    EVERY_HOURS   minimum time between two fetches (be polite)
    fetch(ctx)    -> list[dict] built with opportunity()
    enrich(rec, ctx)   optional: fetch one posting's detail page
    available(ctx)     optional: -> (bool, reason) when it needs a key
"""

from __future__ import annotations

import re

from ..text import clip, iso_day, make_id

_ARABIC = re.compile(r"[؀-ۿ]")


def guess_lang(text: str) -> str:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return "en"
    arabic = sum(1 for c in letters if _ARABIC.match(c))
    return "ar" if arabic / len(letters) > 0.3 else "en"


def opportunity(
    source: str,
    label: str,
    url: str,
    title: str,
    company: str | None = "",
    text: str | None = "",
    *,
    posted=None,
    expires=None,
    location: str | None = None,
    remote: bool | None = None,
    kind: str = "job",
    pay: str | None = None,
    lang: str | None = None,
    tags: list | None = None,
    extra: dict | None = None,
) -> dict:
    text = text or ""
    return {
        "id": make_id(url),
        "source": source,
        "source_label": label,
        "url": url,
        "title": clip(title or "(untitled)", 160),
        "company": clip(company or "", 80),
        "kind": kind,
        "posted": iso_day(posted),
        "expires": iso_day(expires),
        "location": clip(location, 160) or None,
        "remote": remote,
        "pay": pay or None,
        "lang": lang or guess_lang(f"{title} {text}"),
        "tags": [str(t).lower() for t in (tags or [])][:12],
        "text": clip(text, 1500),
        "summary": clip(text, 320),
        "status": "new",
        "user_status": None,
        "extra": extra or {},
    }


def registry() -> list:
    from . import (
        bounties,
        freelancer,
        himalayas,
        hn,
        jobicy,
        khamsat,
        mostaql,
        reliefweb,
        remoteok,
        remotive,
        websearch,
        wwr,
    )

    return [remotive, remoteok, himalayas, jobicy, wwr, hn, freelancer, mostaql, khamsat, reliefweb, bounties, websearch]
