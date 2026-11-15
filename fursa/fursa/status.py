"""Your side of the memory: mark a posting applied / interview / ignored from the dashboard.

The dashboard opens a pre-filled GitHub issue titled "[fursa] <id> <status>".
Only issues opened by the repository owner are applied; each one is then closed.
No server, no tokens.
"""

from __future__ import annotations

import logging
import re

from . import net
from .store import USER_STATUSES
from .text import clip, iso_time

log = logging.getLogger("fursa.status")
TITLE = re.compile(r"^\s*\[fursa\]\s+([0-9a-f]{12})\s+(" + "|".join(USER_STATUSES) + r")\b", re.I)
API = "https://api.github.com"


def parse(title: str) -> tuple[str, str] | None:
    match = TITLE.match(title or "")
    return (match.group(1).lower(), match.group(2).lower()) if match else None


def apply(store, opp_id: str, status: str, note: str = "") -> bool:
    rec = store.opps.get(opp_id)
    if not rec:
        return False
    rec["user_status"] = status
    rec["user_note"] = clip(note, 500) or rec.get("user_note")
    rec["user_updated"] = iso_time(store.s.now)
    rec["updated"] = rec["user_updated"]
    return True


def sync_issues(settings, store) -> int:
    """Apply every open status issue from the owner, then close it. Returns how many were applied."""
    if not (settings.github_token and settings.github_repo):
        return 0
    headers = {"Authorization": f"Bearer {settings.github_token}", "Accept": "application/vnd.github+json"}
    owner = settings.github_repo.split("/")[0].lower()
    issues = net.get_json(
        f"{API}/repos/{settings.github_repo}/issues",
        params={"state": "open", "creator": owner, "per_page": 50},
        headers=headers,
    )
    applied = 0
    for issue in issues:
        parsed = parse(issue.get("title", ""))
        if not parsed or (issue.get("user") or {}).get("login", "").lower() != owner or issue.get("pull_request"):
            continue
        opp_id, status = parsed
        ok = apply(store, opp_id, status, issue.get("body") or "")
        applied += ok
        reply = f"✅ تم — الحالة صارت `{status}`." if ok else "⚠️ ما لگيت هالفرصة بالذاكرة (يمكن انحذفت لأنها قديمة)."
        base = f"{API}/repos/{settings.github_repo}/issues/{issue['number']}"
        try:
            net.session().post(f"{base}/comments", json={"body": reply}, headers=headers, timeout=30).raise_for_status()
            net.session().patch(base, json={"state": "closed", "state_reason": "completed"}, headers=headers, timeout=30).raise_for_status()
        except Exception as exc:  # the status is saved even if closing the issue fails
            log.warning("could not close issue #%s: %s", issue["number"], exc)
    return applied
