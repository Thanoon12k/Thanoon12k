"""ReliefWeb jobs API (UN OCHA): NGO and UN vacancies in Iraq, many in Ninewa/Mosul.

Needs a free *approved* appname since late 2025: request one at
https://apidoc.reliefweb.int/parameters#appname and save it as the
RELIEFWEB_APPNAME repository variable. Without it this source is skipped.
"""

from .. import net
from ..text import html_to_text
from . import opportunity

NAME, LABEL, EVERY_HOURS = "reliefweb", "ReliefWeb", 24
API = "https://api.reliefweb.int/v2/jobs"
QUERY = (
    "developer OR programmer OR software OR \"information technology\" OR ICT OR database OR "
    "\"information management\" OR GIS OR \"data officer\" OR \"IT officer\" OR digital"
)


def available(ctx) -> tuple[bool, str]:
    if not ctx.settings.reliefweb_appname:
        return False, "needs RELIEFWEB_APPNAME (free, from ReliefWeb)"
    return True, ""


def from_item(item: dict) -> dict | None:
    f = item.get("fields") or {}
    url = f.get("url_alias") or f.get("url")
    if not url:
        return None
    cities = ", ".join(c.get("name", "") for c in f.get("city") or [] if c.get("name"))
    sources = ", ".join(s.get("name", "") for s in f.get("source") or [] if s.get("name"))
    body = html_to_text(f.get("body-html") or f.get("body") or "")
    how = html_to_text(f.get("how_to_apply-html") or f.get("how_to_apply") or "")
    date = f.get("date") or {}
    return opportunity(
        NAME, LABEL, url, f.get("title"), sources, f"{body}\n\nHow to apply: {how}" if how else body,
        posted=date.get("created"),
        expires=date.get("closing"),
        location=f"Iraq{' - ' + cities if cities else ''}",
        remote=False,
        extra={"org": sources},
    )


def fetch(ctx) -> list[dict]:
    payload = {
        "limit": 40,
        "sort": ["date.created:desc"],
        "query": {"value": QUERY, "fields": ["title"]},
        "filter": {"field": "country.iso3", "value": "IRQ"},
        "fields": {"include": ["title", "url", "url_alias", "date", "source.name", "city.name", "body", "how_to_apply"]},
    }
    response = net.session().post(API, params={"appname": ctx.settings.reliefweb_appname}, json=payload, timeout=30)
    response.raise_for_status()
    return [rec for rec in (from_item(i) for i in response.json().get("data", [])) if rec]
