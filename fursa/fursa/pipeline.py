"""One run of the team, start to finish. GitHub Actions calls this every 6 hours.

  0. apply your status clicks (issues)          free
  1. re-index your GitHub portfolio (weekly)    free (+ cached AI summaries)
  2. collect from the free sources              free
  3. scout   screens new postings               Haiku, batched
  4. matcher picks repos for the best ones      Haiku
  5. writer  drafts applications                Haiku
  6. manager final review, max 3 picks          Opus, one call
  7. weekly income ideas                        Opus, once a week
  8. Telegram digest (only if something new)    free
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from datetime import timedelta
from types import SimpleNamespace

from . import contacts, manager, matcher, notify, portfolio, scoring, scout, sources, status, writer
from .llm import LLM
from .scoring import normalize
from .store import Store
from .text import iso_time

log = logging.getLogger("fursa")


def _dup_key(rec: dict) -> str | None:
    if not rec.get("company"):
        return None
    raw = normalize(rec["title"])[:60] + "|" + normalize(rec["company"])[:40]
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def collect(ctx, report: dict) -> None:
    settings, store = ctx.settings, ctx.store
    titles = store.state.setdefault("title_keys", {})
    today = settings.now.strftime("%Y-%m-%d")
    for mod in sources.registry():
        name = mod.NAME
        info = {"label": mod.LABEL}
        report["sources"][name] = info
        if not settings.source_enabled(name):
            info["state"] = "off"
            continue
        ok, why = mod.available(ctx) if hasattr(mod, "available") else (True, "")
        if not ok:
            info["state"] = f"skipped: {why}"
            continue
        every = mod.every_hours(settings) if hasattr(mod, "every_hours") else mod.EVERY_HOURS
        if not store.due(f"source:{name}", every):
            info["state"] = "waiting"
            continue
        try:
            items = mod.fetch(ctx)
        except Exception as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code == 403:  # the site refuses GitHub's servers; nothing to fix on our side, the web search covers it
                info["state"] = "blocked: HTTP 403 (the site refuses requests from GitHub's servers)"
            else:
                info["state"] = f"error: HTTP {code}" if code else f"error: {type(exc).__name__}: {str(exc)[:140]}"
            store.state.setdefault("sources", {})[name] = {**info, "at": iso_time(settings.now)}
            log.warning("%s failed: %s", name, exc)
            continue
        store.touch(f"source:{name}")
        batch, kept = set(), []
        for rec in items:
            key = _dup_key(rec)
            if rec["id"] in batch or store.known(rec["id"]) or (key and key in titles):
                continue  # already seen here, in an earlier run, or on another job board
            batch.add(rec["id"])
            if key:
                titles[key] = today
            if scoring.assess(rec, settings)[0]:
                kept.append(rec)
            else:
                store.mark_seen(rec["id"])
        cap = int(settings.search.get("max_per_source", 8))  # keeps one noisy board from crowding out the rest
        kept.sort(key=lambda r: -r["score"])
        for rec in kept[cap:]:
            store.mark_seen(rec["id"])
        kept = kept[:cap]
        if hasattr(mod, "enrich"):
            for rec in sorted(kept, key=lambda r: -r["score"])[:4]:
                try:
                    mod.enrich(rec, ctx)
                except Exception as exc:
                    log.info("enrich %s failed: %s", rec["url"], exc)
                    continue
                if not scoring.assess(rec, settings)[0]:
                    kept.remove(rec)
                    store.mark_seen(rec["id"])
        for rec in kept:
            extra = rec.get("extra") or {}
            found = {} if contacts.on_platform(rec["url"]) else contacts.extract(
                rec.get("text"), apply_url=extra.get("apply_url"), channel=extra.get("channel"))
            if found:
                rec["contacts"] = found
            store.add(rec)
        info.update(state="ok", fetched=len(items), new=len(batch), kept=len(kept))
        store.state.setdefault("sources", {})[name] = {**info, "at": iso_time(settings.now)}
        report["kept"] += len(kept)
    oldest = (settings.now - timedelta(days=45)).strftime("%Y-%m-%d")
    store.state["title_keys"] = {k: v for k, v in titles.items() if v >= oldest}


def _meta(settings, store, llm, report) -> dict:
    counts = Counter(o.get("status") for o in store.opps.values())
    users = Counter(o.get("user_status") for o in store.opps.values() if o.get("user_status"))
    return {
        "updated": iso_time(settings.now),
        "repo": settings.github_repo,
        "site_url": settings.site_url,
        "mode": report["mode"],
        "llm_note": llm.disabled_reason if llm else "",
        "models": {"worker": settings.worker_model, "manager": settings.manager_model},
        "usage_month": store.usage(),
        "budget_usd": float(settings.agents.get("monthly_budget_usd", 5.0)),
        "counts": dict(counts),
        "user_counts": dict(users),
        "sources": store.state.get("sources", {}),
        "summary_ar": store.state.get("last_summary_ar", ""),
        "notice": (f"الذكاء الاصطناعي متوقف: {llm.disabled_reason}. الفريق يكمل بالقواعد المجانية."
                   if llm and llm.disabled_reason and settings.anthropic_key else ""),
        "person": {k: settings.person.get(k, "") for k in ("name", "github", "website", "email", "phone")},
    }


def deliver(settings, store, report: dict, max_picks: int) -> int:
    """Send approved picks that never reached Telegram: new ones, and ones approved before the bot was set up.

    A pick goes out once. Picks older than a week, or already marked by the user, are not sent.
    """
    now, week_ago = iso_time(settings.now), iso_time(settings.now - timedelta(days=7))
    pending = [r for r in store.items("approved") if not r.get("notified_at") and not r.get("user_status")
               and (r.get("manager") or {}).get("at", "") >= week_ago and r.get("notify_tries", 0) < 3]
    pending.sort(key=lambda r: (not (r.get("manager") or {}).get("ai"), (r.get("manager") or {}).get("rank", 9)))
    batch = pending[:max_picks]
    reviewed_now = any((r.get("manager") or {}).get("at") == now and (r.get("manager") or {}).get("ai") for r in batch)
    sent, failed = notify.announce(settings, store, batch, store.state.get("last_summary_ar", "") if reviewed_now else "")
    report["errors"] += [f"telegram: {e}" for e in failed]
    return sent


def run(settings, *, collect_only: bool = False, llm_client=None) -> dict:
    store = Store(settings).load()
    store.state.pop("_run_usage", None)
    llm = LLM(settings, store, client=llm_client)
    ctx = SimpleNamespace(settings=settings, store=store, llm=llm if settings.llm_enabled else None)
    report = {"at": iso_time(settings.now), "mode": "ai" if ctx.llm else "free", "sources": {}, "kept": 0, "errors": []}

    try:
        report["status_updates"] = status.sync_issues(settings, store)
    except Exception as exc:
        report["errors"].append(f"status: {exc}")
    telegram_updates = []
    try:
        telegram_updates = notify.poll(settings, store)  # replies like «قدمت» to earlier picks
        report["telegram_updates"] = len(telegram_updates)
    except Exception as exc:
        report["errors"].append(f"telegram: {exc}")

    refresh_days = float(settings.portfolio.get("refresh_days", 7))
    if settings.force_portfolio or not store.portfolio or store.due("portfolio", 24 * refresh_days):
        try:
            report["portfolio_reindexed"] = portfolio.refresh(settings, store, llm=ctx.llm)
        except Exception as exc:
            report["errors"].append(f"portfolio: {exc}")

    collect(ctx, report)

    if not collect_only:
        a = settings.agent_int
        fresh = sorted(store.items("new"), key=lambda r: -(r.get("score") or 0))[: a("max_scout", 12)]
        report["scouted_ai"] = scout.run(ctx, fresh)

        screened = sorted(store.items("screened"), key=lambda r: -(r.get("score") or 0))[: a("max_match", 6)]
        if store.portfolio:
            report["matched_ai"] = matcher.run(ctx, screened)
        min_fit = a("min_fit", 55)
        for rec in store.items("matched"):
            if (rec.get("match") or {}).get("fit", 0) < min_fit:
                store.set_status(rec, "rejected", reject_reason=f"weak match with your projects ({rec['match'].get('fit')})")

        matched = sorted(store.items("matched"), key=lambda r: -(r.get("match") or {}).get("fit", 0))[: a("max_drafts", 4)]
        report["drafted_ai"] = writer.run(ctx, matched)

        drafted = sorted(store.items("drafted"), key=lambda r: -(r.get("match") or {}).get("fit", 0))
        manager_due = store.due("manager", float(settings.agents.get("manager_every_hours", 12)))
        backlog = ctx.llm is not None and len(drafted) >= 2 * a("max_picks", 3)  # a full AI batch is worth a review now
        if drafted and (manager_due or backlog):  # free rules too: at most max_picks per review, a review every 12 hours
            approved = manager.review(ctx, drafted[:8])
            store.touch("manager")
            report["approved"] = len(approved)

        if ctx.llm is not None and store.due("ideas", 24 * 7):
            report["ideas"] = manager.ideas(ctx)

        report["notified"] = deliver(settings, store, report, a("max_picks", 3))

    try:
        notify.confirm(settings, telegram_updates)
    except Exception as exc:
        report["errors"].append(f"telegram: {exc}")

    report["pruned"] = store.prune()
    run_usage = store.state.pop("_run_usage", {})
    report["usd"] = round(run_usage.get("usd", 0.0), 4)
    report["tokens"] = {"in": run_usage.get("input_tokens", 0), "out": run_usage.get("output_tokens", 0)}
    store.runs.append({k: v for k, v in report.items() if k != "sources"} | {
        "sources": {k: v.get("state") for k, v in report["sources"].items()}
    })
    store.save(meta=_meta(settings, store, ctx.llm, report))
    return report
