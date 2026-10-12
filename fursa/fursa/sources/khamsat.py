"""Khamsat (خمسات) community requests: small paid tasks posted by buyers."""

import html
import re

from .. import net
from ..text import html_to_text
from . import opportunity

NAME, LABEL, EVERY_HOURS = "khamsat", "خمسات Khamsat", 4
PAGE = "https://khamsat.com/community/requests"

_LINK = re.compile(r'<h3 class="details-head">\s*<a[^>]*href="/community/requests/(\d+)[^"]*"[^>]*>(.*?)</a>', re.S)
_DATE = re.compile(r'title="(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2}) GMT"')


def parse_listing(page: str) -> list[dict]:
    out = []
    for row in page.split('<tr id="forum_post-')[1:]:
        link = _LINK.search(row)
        if not link:
            continue
        posted = _DATE.search(html.unescape(row))
        title = html_to_text(link.group(2))
        out.append(
            opportunity(
                NAME, LABEL, f"https://khamsat.com/community/requests/{link.group(1)}", title, "", title,
                posted=posted.group(1) if posted else None,
                kind="gig", remote=True, lang="ar",
            )
        )
    return out


def fetch(ctx) -> list[dict]:
    return parse_listing(net.get_text(PAGE))
