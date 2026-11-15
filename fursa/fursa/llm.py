"""The only door to the Claude API. Two roles:

  worker  -> cheap model (Claude Haiku 5.5): scout, matcher, writer, web search
  manager -> strong model (Claude Opus 5.5): final review, weekly ideas

Every call is metered; when the monthly budget is spent, `available()` turns
False and the team falls back to the zero-cost rules until next month.
"""

from __future__ import annotations

import json
import logging
import re

log = logging.getLogger("fursa.llm")

# USD per million tokens (input, output). Prompts under 100K tokens.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-1": (10.00, 50.00),
}
WEB_SEARCH_USD = 0.01  # per search (USD 10 per 1,000)


def _price(model: str) -> tuple[float, float]:
    return PRICES.get(model, PRICES["claude-opus-5-5"])  # unknown model: assume the expensive side


class LLM:
    def __init__(self, settings, store, client=None):
        self.s = settings
        self.store = store
        self.calls = {"worker": 0, "manager": 0}
        self.disabled_reason = ""
        self._client = client
        if not settings.llm_enabled:
            self.disabled_reason = "no ANTHROPIC_API_KEY" if not settings.anthropic_key else "switched off (FURSA_NO_LLM)"

    # ---------- budget ----------
    @property
    def budget(self) -> float:
        return float(self.s.agents.get("monthly_budget_usd", 5.0))

    def available(self, role: str = "worker") -> bool:
        if self.disabled_reason:
            return False
        if self.store.usage()["usd"] >= self.budget:
            self.disabled_reason = f"monthly budget of ${self.budget:g} reached"
            return False
        limit = {"worker": 40, "manager": 3}[role]
        return self.calls[role] < limit

    @property
    def client(self):
        if self._client is None:
            import anthropic  # imported lazily so the free mode works without the package

            self._client = anthropic.Anthropic(max_retries=3, timeout=180)
        return self._client

    def _meter(self, model: str, usage) -> float:
        tokens_in = (
            (getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        )
        tokens_out = getattr(usage, "output_tokens", 0) or 0
        searches = getattr(getattr(usage, "server_tool_use", None), "web_search_requests", 0) or 0
        p_in, p_out = _price(model)
        cost = tokens_in * p_in / 1e6 + tokens_out * p_out / 1e6 + searches * WEB_SEARCH_USD
        month = self.store.usage()
        month["usd"] = round(month["usd"] + cost, 6)
        month["input_tokens"] += tokens_in
        month["output_tokens"] += tokens_out
        month["calls"] += 1
        month["searches"] += searches
        run = self.store.state.setdefault("_run_usage", {"usd": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0})
        run["usd"] = round(run["usd"] + cost, 6)
        run["input_tokens"] += tokens_in
        run["output_tokens"] += tokens_out
        run["calls"] += 1
        return cost

    def _settings_for(self, role: str) -> tuple[str, str]:
        if role == "manager":
            return self.s.manager_model, self.s.agents.get("manager_effort", "medium")
        return self.s.worker_model, self.s.agents.get("worker_effort", "low")

    def _handle_error(self, exc: Exception) -> None:
        import anthropic

        if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
            self.disabled_reason = "the API key was refused"
        elif isinstance(exc, anthropic.NotFoundError):
            self.disabled_reason = f"model not found: {exc}"
        elif isinstance(exc, anthropic.RateLimitError):
            self.disabled_reason = "rate limited; trying again next run"
        elif isinstance(exc, anthropic.BadRequestError):
            log.warning("bad request: %s", exc)
        elif isinstance(exc, anthropic.APIStatusError):
            log.warning("API error %s: %s", exc.status_code, exc)
        elif isinstance(exc, anthropic.APIConnectionError):
            log.warning("network error talking to the API: %s", exc)
        else:
            log.warning("unexpected API error: %s", exc)

    # ---------- calls ----------
    def structured(self, role: str, system: str, payload, schema: dict, max_tokens: int = 4000) -> dict | None:
        """One structured call. Returns the parsed JSON object, or None (caller falls back to rules)."""
        if not self.available(role):
            return None
        import anthropic

        model, effort = self._settings_for(role)
        content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self.calls[role] += 1
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.APIError as exc:
            self._handle_error(exc)
            return None
        self._meter(model, response.usage)
        if response.stop_reason in ("refusal", "max_tokens"):
            log.warning("%s call stopped: %s", role, response.stop_reason)
            return None
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            log.warning("%s returned invalid JSON", role)
            return None

    def search(self, system: str, prompt: str, max_uses: int = 4) -> str | None:
        """Worker call with Claude's server-side web search. Returns the final text."""
        if not self.available("worker"):
            return None
        import anthropic

        model, effort = self._settings_for("worker")
        tool = {
            "type": self.s.agents.get("web_search_tool", "web_search_20250305"),
            "name": "web_search",
            "max_uses": max_uses,
            "user_location": {"type": "approximate", "city": "Mosul", "country": "IQ", "timezone": "Asia/Baghdad"},
        }
        self.calls["worker"] += 1
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=6000,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                tools=[tool],
                output_config={"effort": effort},
            )
        except anthropic.APIError as exc:
            self._handle_error(exc)
            return None
        self._meter(model, response.usage)
        if response.stop_reason == "refusal":
            return None
        return "\n".join(b.text for b in response.content if b.type == "text")


def extract_json_array(text: str | None) -> list:
    """Pull the first JSON array out of free text (web search answers carry citations, not schemas)."""
    if not text:
        return []
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    candidates = [fenced.group(1)] if fenced else []
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, list):
                return value
        except json.JSONDecodeError:
            continue
    return []
