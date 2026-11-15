"""Command line.

  python -m fursa run              one full run (what GitHub Actions does)
  python -m fursa run --free       same, without any AI calls (zero cost)
  python -m fursa collect          only fetch and score postings
  python -m fursa portfolio        re-index your public GitHub repos now
  python -m fursa status           apply status issues opened from the dashboard
  python -m fursa telegram-setup   find your Telegram chat id and send a test message
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
    sub.add_parser("telegram-setup")
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

    if args.cmd == "telegram-setup":
        if not settings.telegram_token:
            print("1) Create a bot with @BotFather and save its token as the TELEGRAM_BOT_TOKEN secret.")
            return 1
        print(f"Bot: @{notify.bot_name(settings)}")
        if not settings.telegram_chat:
            chats = notify.chat_ids(settings)
            if not chats:
                print("2) Send any message to the bot in Telegram, then run this again.")
                return 1
            for chat_id, name in chats:
                print(f"Chat id {chat_id} ({name}): save it as the TELEGRAM_CHAT_ID secret, then run this again.")
            return 0
        notify.send(settings, "✅ <b>فرصة</b>: تلگرام مربوط. الفرص الجديدة توصل هنا، والرد على أي فرصة بكلمة «قدمت» يحفظ الحالة.")
        print("Test message sent. Telegram is ready.")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
