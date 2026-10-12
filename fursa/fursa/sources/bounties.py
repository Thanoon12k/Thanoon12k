"""Open GitHub issues that carry a bounty label, in Dart and Python repositories.

Paid tasks rather than jobs. Payout platforms (Algora, Opire...) may not pay out
to Iraq, so every bounty starts as eligibility "unclear".
"""

import re
from datetime import timedelta

from .. import net
from ..text import clip
from . import opportunity

NAME, LABEL, EVERY_HOURS = "github_bounties", "GitHub bounties", 24
API = "https://api.github.com/search/issues"
QUERIES = (
    "label:bounty state:open is:issue language:dart",
    "label:bounty state:open is:issue language:python",
    'label:"💎 Bounty" state:open is:issue',
)
_AMOUNT = re.compile(r"\$\s?(\d[\d,]{1,6})")


def available(ctx) -> tuple[bool, str]:
    if not ctx.settings.github_token:
        return False, "needs GITHUB_TOKEN (automatic inside GitHub Actions)"
    return True, ""


def from_issue(item: dict) -> dict | None:
    if item.get("pull_request") or not item.get("html_url"):
        return None
    repo = "/".join((item.get("repository_url") or "").split("/")[-2:])
    labels = " ".join(label.get("name", "") for label in item.get("labels") or [])
    amount = _AMOUNT.search(f"{labels} {item.get('title', '')}") or _AMOUNT.search(item.get("body") or "")
    return opportunity(
        NAME, LABEL, item["html_url"], f"{repo}: {item.get('title', '')}", repo,
        clip(item.get("body") or "", 1500),
        posted=item.get("created_at"),
        kind="bounty",
        remote=True,
        pay=f"${amount.group(1)} bounty" if amount else None,
        tags=[label.get("name", "") for label in item.get("labels") or []],
        extra={"comments": item.get("comments")},
    )


def fetch(ctx) -> list[dict]:
    since = (ctx.settings.now - timedelta(days=30)).strftime("%Y-%m-%d")
    headers = {"Authorization": f"Bearer {ctx.settings.github_token}", "Accept": "application/vnd.github+json"}
    out = []
    for query in QUERIES:
        data = net.get_json(API, params={"q": f"{query} created:>={since}", "per_page": 30, "sort": "created"}, headers=headers)
        out.extend(rec for rec in (from_issue(i) for i in data.get("items", [])) if rec)
    return out
