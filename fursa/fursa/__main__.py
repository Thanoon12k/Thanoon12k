"""Command line.

  python -m fursa run              one full run (what GitHub Actions does)
  python -m fursa run --free       same, without any AI calls (zero cost)
  python -m fursa collect          only fetch and score postings
  python -m fursa portfolio        re-index your public GitHub repos now
  python -m fursa status           apply status issues opened from the dashboard
  python -m fursa telegram-test    send a test message to your Telegram
  python -m fursa chat-id          show the chat id(s) that messaged your bot
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from . import config, notify, pipeline, portfolio, status
from .llm import LLM
from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fursa", description="Fursa job-hunting agents")
    sub = parser.add_subparsers(dest="cmd")
    run_p = sub.add_parser("run")
    run_p.add_argument("--free", action="store_true", help="no AI calls")
    sub.add_parser("collect")
    port_p = sub.add_parser("portfolio")
    port_p.add_argument("--repos", help="comma-separated owner/name list instead of listing your account")
    sub.add_parser("status")
    sub.add_parser("telegram-test")
    sub.add_parser("chat-id")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if getattr(args, "free", False):
        os.environ["FURSA_NO_LLM"] = "1"
    settings = config.load()

    if args.cmd in (None, "run", "collect"):
        report = pipeline.run(settings, collect_only=args.cmd == "collect")
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0

    if args.cmd == "portfolio":
        store = Store(settings).load()
        repos = None
        if args.repos:
            repos = [portfolio._get(settings, f"/repos/{name.strip()}") for name in args.repos.split(",") if name.strip()]
        llm = LLM(settings, store) if settings.llm_enabled else None
        changed = portfolio.refresh(settings, store, llm=llm, repos=repos)
        store.save()
        print(f"re-read {changed} repos; {len(store.portfolio)} in the index")
        return 0

    if args.cmd == "status":
        store = Store(settings).load()
        applied = status.sync_issues(settings, store)
        store.save()
        print(f"applied {applied} status update(s)")
        return 0

    if args.cmd == "telegram-test":
        ok = notify.send(settings, "✅ <b>فرصة</b>: Telegram is connected. The agents will message you here.")
        print("sent" if ok else "not sent: check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return 0 if ok else 1

    if args.cmd == "chat-id":
        if not settings.telegram_token:
            print("set TELEGRAM_BOT_TOKEN first")
            return 1
        for chat_id, name in notify.chat_ids(settings):
            print(chat_id, name)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
