"""Settings: profile.toml (edited by the user) plus environment variables (secrets)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .text import now_utc

ROOT = Path(__file__).resolve().parent.parent


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    root: Path
    profile: dict
    now: datetime = field(default_factory=now_utc)
    anthropic_key: str = ""
    github_token: str = ""
    github_repo: str = ""
    telegram_token: str = ""
    telegram_chat: str = ""
    reliefweb_appname: str = ""
    no_llm: bool = False
    force_portfolio: bool = False

    # sections of profile.toml
    @property
    def person(self) -> dict:
        return self.profile.get("person", {})

    @property
    def search(self) -> dict:
        return self.profile.get("search", {})

    @property
    def agents(self) -> dict:
        return self.profile.get("agents", {})

    @property
    def portfolio(self) -> dict:
        return self.profile.get("portfolio", {})

    def source_enabled(self, name: str) -> bool:
        return bool(self.profile.get("sources", {}).get(name, True))

    # paths
    @property
    def data_dir(self) -> Path:
        return self.root / "docs" / "data"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    # models
    @property
    def worker_model(self) -> str:
        return os.environ.get("FURSA_WORKER_MODEL") or self.agents.get("worker_model", "claude-haiku-5-5")

    @property
    def manager_model(self) -> str:
        return os.environ.get("FURSA_MANAGER_MODEL") or self.agents.get("manager_model", "claude-opus-5-5")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_key) and not self.no_llm

    @property
    def owner(self) -> str:
        return (self.github_repo.split("/")[0] if self.github_repo else "") or self.person.get("github", "")

    @property
    def site_url(self) -> str:
        url = self.profile.get("site", {}).get("url", "")
        if url:
            return url.rstrip("/") + "/"
        if self.github_repo:
            owner, repo = self.github_repo.split("/", 1)
            return f"https://{owner.lower()}.github.io/{repo}/"
        return ""

    def agent_int(self, key: str, default: int) -> int:
        try:
            return int(self.agents.get(key, default))
        except (TypeError, ValueError):
            return default


def load(root: Path | None = None, now: datetime | None = None) -> Settings:
    root = Path(os.environ.get("FURSA_ROOT") or root or ROOT)
    profile_path = root / "profile.toml"
    profile = tomllib.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    return Settings(
        root=root,
        profile=profile,
        now=now or now_utc(),
        anthropic_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        github_token=os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", ""),
        github_repo=os.environ.get("GITHUB_REPOSITORY", ""),
        telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat=os.environ.get("TELEGRAM_CHAT_ID", ""),
        reliefweb_appname=os.environ.get("RELIEFWEB_APPNAME", ""),
        no_llm=_flag("FURSA_NO_LLM"),
        force_portfolio=_flag("FURSA_FORCE_PORTFOLIO"),
    )
