"""Mostaql (مستقل), the largest Arab freelance platform: public project listings.

robots.txt allows /projects; we read two category pages per run and, for the few
postings worth it, one detail page (budget, status, full description).
"""

import html
import re
import xml.etree.ElementTree as ET

from .. import net
from ..text import html_to_text
from . import opportunity

NAME, LABEL, EVERY_HOURS = "mostaql", "مستقل Mostaql", 4
PAGES = ("https://mostaql.com/projects/development", "https://mostaql.com/projects/ai-machine-learning")
RSS = "https://mostaql.com/rss"

_LINK = re.compile(r'<h2[^>]*>\s*<a href="https://mostaql\.com/project/(\d+)[^"]*"[^>]*>(.*?)</a>', re.S)
_TIME = re.compile(r'<time datetime="([^"]+)"')
_BIDS = re.compile(r"(\d+)\s*(?:عروض|عرض)")
_BRIEF = re.compile(r'class="details-url"[^>]*>(.*?)</a>', re.S)
_BUDGET = re.compile(r"project-budget_range\s*>\s*<span[^>]*>([^<]+)</span>")
_STATE = re.compile(r"label-prj-(\w+)")
_BODY = re.compile(r'<div class="text-wrapper-div carda__content[^"]*"\s*>(.*?)</div>', re.S)


def _url(project_id: str) -> str:
    return f"https://mostaql.com/project/{project_id}"


def parse_listing(page: str) -> list[dict]:
    out = []
    for row in page.split('<tr class="project-row">')[1:]:
        link = _LINK.search(row)
        if not link:
            continue
        project_id, title = link.group(1), html_to_text(link.group(2))
        posted = _TIME.search(row)
        bids = _BIDS.search(row)
        brief = _BRIEF.search(row)
        out.append(
            opportunity(
                NAME, LABEL, _url(project_id), title, "", html_to_text(brief.group(1)) if brief else "",
                posted=posted.group(1) if posted else None,
                kind="freelance", remote=True, lang="ar",
                extra={"bids": int(bids.group(1)) if bids else None},
            )
        )
    return out


def parse_rss(xml_text: str) -> list[dict]:
    out = []
    for item in ET.fromstring(xml_text).findall("./channel/item"):
        link = (item.findtext("link") or "").strip()
        match = re.search(r"/(?:go|project)/(\d+)", link)
        if not match:
            continue
        out.append(
            opportunity(
                NAME, LABEL, _url(match.group(1)), item.findtext("title") or "", "",
                html_to_text(item.findtext("description")),
                posted=item.findtext("pubDate"), kind="freelance", remote=True, lang="ar",
            )
        )
    return out


def fetch(ctx) -> list[dict]:
    out = []
    for page in PAGES:
        out.extend(parse_listing(net.get_text(page)))
    if not out:  # the page layout changed: fall back to the open-projects RSS
        out = parse_rss(net.get_text(RSS))
    return out


def parse_detail(page: str) -> dict:
    budget, state, body = _BUDGET.search(page), _STATE.search(page), _BODY.search(page)
    return {
        "pay": html.unescape(budget.group(1)).strip() if budget else None,
        "open": state.group(1) == "open" if state else None,
        "text": html_to_text(body.group(1)) if body else "",
    }


def enrich(rec: dict, ctx) -> None:
    detail = parse_detail(net.get_text(rec["url"]))
    if detail["pay"]:
        rec["pay"] = detail["pay"]
    if detail["text"]:
        rec["text"] = detail["text"][:1500]
    if detail["open"] is False:
        rec["expires"] = rec.get("posted")  # closed: treated as expired
    rec.setdefault("extra", {})["checked_page"] = True
