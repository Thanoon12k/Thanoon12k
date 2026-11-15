"""Hacker News "Ask HN: Who is hiring?" (monthly thread) via the free Algolia API."""

from .. import net
from ..text import html_to_text
from . import opportunity

NAME, LABEL, EVERY_HOURS = "hackernews", "Hacker News: Who is hiring", 24
API = "https://hn.algolia.com/api/v1"


def latest_thread_id() -> str | None:
    data = net.get_json(f"{API}/search_by_date", params={"tags": "story,author_whoishiring", "hitsPerPage": 6})
    for hit in data.get("hits", []):
        if (hit.get("title") or "").lower().startswith("ask hn: who is hiring"):
            return str(hit["objectID"])
    return None


def _location(header: str) -> str:
    parts = [p.strip() for p in header.split("|")]
    remote = [p for p in parts if "remote" in p.lower()]
    return remote[0] if remote else header


def from_comment(hit: dict, story_id: str) -> dict | None:
    if str(hit.get("parent_id")) != story_id or not hit.get("comment_text"):
        return None  # only top-level posts are job ads
    text = html_to_text(hit["comment_text"])
    header = text.split("\n", 1)[0]
    company = header.split("|", 1)[0].strip()
    return opportunity(
        NAME, LABEL, f"https://news.ycombinator.com/item?id={hit['objectID']}",
        header, company, text,
        posted=hit.get("created_at"),
        location=_location(header),
        remote="remote" in header.lower() or None,
    )


def fetch(ctx) -> list[dict]:
    story_id = latest_thread_id()
    if not story_id:
        return []
    out, seen = [], set()
    for query in ("flutter", "django"):
        data = net.get_json(f"{API}/search", params={"tags": f"comment,story_{story_id}", "query": query, "hitsPerPage": 50})
        for hit in data.get("hits", []):
            rec = from_comment(hit, story_id)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                out.append(rec)
    return out
