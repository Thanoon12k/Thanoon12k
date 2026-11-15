"""We Work Remotely RSS feeds (programming categories)."""

import re
import xml.etree.ElementTree as ET

from .. import net
from ..text import html_to_text
from . import opportunity

NAME, LABEL, EVERY_HOURS = "weworkremotely", "We Work Remotely", 12
FEEDS = (
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
)
_FLAGS = re.compile("[\U0001F1E6-\U0001F1FF]")


def _location(region: str, countries: str) -> str:
    names = [c.strip() for c in _FLAGS.sub("", countries or "").split(",") if c.strip()]
    if any("iraq" in n.lower() for n in names):
        return "Iraq; " + region
    if len(names) > 2:  # an explicit allow-list of countries that leaves Iraq out
        return "Only: " + ", ".join(names)
    return region or ", ".join(names)


def parse(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for item in root.findall("./channel/item"):
        get = lambda tag: (item.findtext(tag) or "").strip()  # noqa: E731
        link = get("link") or get("guid")
        if not link:
            continue
        company, _, role = get("title").partition(":")
        if not role:
            company, role = "", company
        out.append(
            opportunity(
                NAME, LABEL, link, role.strip(), company.strip(), html_to_text(get("description")),
                posted=get("pubDate"),
                expires=get("expires_at") or None,
                location=_location(get("region"), get("country")),
                remote=True,
                tags=[s.strip() for s in get("skills").replace(" and ", ",").split(",") if s.strip()],
                extra={"type": get("type")},
            )
        )
    return out


def fetch(ctx) -> list[dict]:
    out = []
    for feed in FEEDS:
        out.extend(parse(net.get_text(feed)))
    return out
