"""Shared memory of the team: plain JSON files inside the repository.

docs/data/   is public: the dashboard reads it.
state/       is internal: ids already seen, source timers, token usage, caches.
Every run is a git commit, so the history of the memory is free and auditable.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path

from .text import age_days, iso_time, parse_date

PIPELINE = ("new", "screened", "matched", "drafted", "approved")
STATUS_RANK = {"approved": 0, "drafted": 1, "matched": 2, "screened": 3, "new": 4, "rejected": 8}
USER_STATUSES = ("todo", "applied", "interview", "offer", "rejected", "ignored")
MAX_RECORDS = 400


def _read(path: Path, default):
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        # never crash the whole team on one corrupted file; start that file fresh
        return default


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


class Store:
    def __init__(self, settings):
        self.s = settings
        self.opps: dict[str, dict] = {}
        self.seen: dict[str, str] = {}
        self.state: dict = {}
        self.runs: list[dict] = []
        self.ideas: dict = {}
        self.portfolio: list[dict] = []
        self.portfolio_cache: dict = {}

    # ---------- files ----------
    @property
    def _files(self) -> dict:
        d, st = self.s.data_dir, self.s.state_dir
        return {
            "opps": d / "opportunities.json",
            "portfolio": d / "portfolio.json",
            "ideas": d / "ideas.json",
            "runs": d / "runs.json",
            "meta": d / "meta.json",
            "seen": st / "seen.json",
            "state": st / "state.json",
            "portfolio_cache": st / "portfolio_cache.json",
        }

    def load(self) -> "Store":
        f = self._files
        self.opps = {o["id"]: o for o in _read(f["opps"], []) if isinstance(o, dict) and o.get("id")}
        self.portfolio = _read(f["portfolio"], [])
        self.ideas = _read(f["ideas"], {})
        self.runs = _read(f["runs"], [])
        self.seen = _read(f["seen"], {})
        self.state = _read(f["state"], {})
        self.portfolio_cache = _read(f["portfolio_cache"], {})
        return self

    def save(self, meta: dict | None = None) -> None:
        f = self._files
        ordered = sorted(
            self.opps.values(),
            key=lambda o: (
                STATUS_RANK.get(o.get("status"), 5),
                -(o.get("manager") or {}).get("rank_score", 0),
                -(o.get("score") or 0),
                o.get("posted") or "",
            ),
        )
        _write(f["opps"], ordered)
        _write(f["portfolio"], self.portfolio)
        _write(f["ideas"], self.ideas)
        _write(f["runs"], self.runs[-60:])
        _write(f["seen"], dict(sorted(self.seen.items())))
        _write(f["state"], self.state)
        _write(f["portfolio_cache"], self.portfolio_cache)
        if meta is not None:
            _write(f["meta"], meta)

    # ---------- opportunities ----------
    def known(self, opp_id: str) -> bool:
        return opp_id in self.opps or opp_id in self.seen

    def mark_seen(self, opp_id: str) -> None:
        self.seen.setdefault(opp_id, self.s.now.strftime("%Y-%m-%d"))

    def add(self, rec: dict) -> bool:
        """Remember a new posting. Returns False if the team already saw it."""
        if self.known(rec["id"]):
            return False
        rec.setdefault("first_seen", iso_time(self.s.now))
        rec["updated"] = iso_time(self.s.now)
        self.opps[rec["id"]] = rec
        self.mark_seen(rec["id"])
        return True

    def items(self, *statuses: str) -> list[dict]:
        return [o for o in self.opps.values() if not statuses or o.get("status") in statuses]

    def set_status(self, rec: dict, status: str, **fields) -> None:
        rec["status"] = status
        rec["updated"] = iso_time(self.s.now)
        rec.update(fields)

    def prune(self) -> int:
        """Forget what no longer matters; ids stay in `seen` so nothing is re-processed."""
        now = self.s.now
        removed = 0
        max_age = int(self.s.search.get("max_age_days", 30))
        for opp_id, rec in list(self.opps.items()):
            status = rec.get("status")
            user = rec.get("user_status")
            first_seen_days = age_days(rec.get("first_seen"), now) or 0
            posted_days = age_days(rec.get("posted"), now)
            touched_days = age_days(rec.get("updated"), now) or 0
            drop = False
            if user in ("applied", "interview", "offer"):
                drop = touched_days > 180
            elif user == "ignored":
                drop = touched_days > 7
            elif status == "rejected":
                drop = touched_days > 7
            elif status in ("new", "screened", "matched"):
                drop = first_seen_days > 21 or (posted_days is not None and posted_days > max_age + 7)
            elif status in ("drafted", "approved"):
                drop = (posted_days or first_seen_days) > 60
            if drop:
                del self.opps[opp_id]
                removed += 1
        if len(self.opps) > MAX_RECORDS:
            # drop the least useful first: rejected, then lowest score
            victims = sorted(
                self.opps.values(),
                key=lambda o: (o.get("status") != "rejected", o.get("user_status") is not None, o.get("score") or 0),
            )
            for rec in victims[: len(self.opps) - MAX_RECORDS]:
                del self.opps[rec["id"]]
                removed += 1
        cutoff = (now - timedelta(days=180)).strftime("%Y-%m-%d")
        self.seen = {k: v for k, v in self.seen.items() if v >= cutoff or k in self.opps}
        return removed

    # ---------- timers and usage ----------
    def due(self, key: str, every_hours: float) -> bool:
        last = parse_date(self.state.get("timers", {}).get(key))
        return last is None or (self.s.now - last).total_seconds() >= every_hours * 3600 - 300

    def touch(self, key: str) -> None:
        self.state.setdefault("timers", {})[key] = iso_time(self.s.now)

    def usage(self) -> dict:
        month = self.s.now.strftime("%Y-%m")
        all_usage = self.state.setdefault("usage", {})
        for old in sorted(all_usage)[:-6]:  # keep half a year of history
            del all_usage[old]
        return all_usage.setdefault(
            month, {"usd": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0, "searches": 0}
        )
