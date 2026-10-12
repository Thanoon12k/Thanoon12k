"""One polite HTTP session for every collector (retries, timeouts, a clear User-Agent)."""

from __future__ import annotations

import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import __version__

_session: requests.Session | None = None


class SourceError(RuntimeError):
    """A source answered, but not with what we expected (blocked, changed format...)."""


def user_agent() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "Thanoon12k/fursa-agents")
    return f"Mozilla/5.0 (compatible; fursa/{__version__}; +https://github.com/{repo})"


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": user_agent(), "Accept-Language": "en,ar;q=0.8"})
        retry = Retry(
            total=2,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
        )
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _session = s
    return _session


def get(url: str, *, params=None, headers=None, timeout: float = 30) -> requests.Response:
    response = session().get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response


def get_json(url: str, *, params=None, headers=None, timeout: float = 30):
    response = get(url, params=params, headers=headers, timeout=timeout)
    try:
        return response.json()
    except ValueError as exc:
        snippet = response.text[:80].replace("\n", " ")
        raise SourceError(f"expected JSON from {url}, got: {snippet!r}") from exc


def get_text(url: str, *, params=None, headers=None, timeout: float = 30) -> str:
    response = get(url, params=params, headers=headers, timeout=timeout)
    response.encoding = response.encoding or "utf-8"
    return response.text
