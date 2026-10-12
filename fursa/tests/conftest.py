import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from fursa import config
from fursa.store import Store

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def root(tmp_path):
    shutil.copy(ROOT / "profile.toml", tmp_path / "profile.toml")
    return tmp_path


@pytest.fixture
def settings(root, monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "FURSA_NO_LLM", "FURSA_ROOT", "RELIEFWEB_APPNAME", "FURSA_FORCE_PORTFOLIO"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "Thanoon12k/fursa")
    return config.load(root=root, now=NOW)


@pytest.fixture
def store(settings):
    return Store(settings).load()


PORTFOLIO = [
    {"name": "Pediatric-Clinic-manager", "url": "https://github.com/Thanoon12k/Pediatric-Clinic-manager",
     "summary_en": "Flutter + Supabase clinic app with admin, doctor and patient roles.", "summary_ar": "تطبيق عيادة Flutter مع Supabase.",
     "kind": "app", "maturity": "feature-rich", "tags": ["dart", "flutter", "riverpod", "supabase"], "own_share": 1.0,
     "readme_template": False, "has_tests": True, "stars": 0, "homepage": "", "pushed": "2026-05-28", "quality": 7.9},
    {"name": "moalidaty", "url": "https://github.com/Thanoon12k/moalidaty",
     "summary_en": "Django REST API with JWT for generator subscriptions.", "summary_ar": "واجهة Django REST لإدارة اشتراكات المولدات.",
     "kind": "backend", "maturity": "feature-rich", "tags": ["django", "django-rest", "python"], "own_share": 1.0,
     "readme_template": True, "has_tests": False, "stars": 0, "homepage": "", "pushed": "2026-04-10", "quality": 4.2},
    {"name": "My-Work", "url": "https://github.com/Thanoon12k/My-Work",
     "summary_en": "Python + Playwright pipeline that runs and screenshots 65 projects.", "summary_ar": "",
     "kind": "tool", "maturity": "feature-rich", "tags": ["python", "automation"], "own_share": 1.0,
     "readme_template": False, "has_tests": False, "stars": 0, "homepage": "https://make1it.pythonanywhere.com",
     "pushed": "2026-09-25", "quality": 5.0},
]


def posting(source="fake", url="https://jobs.example.com/1", title="Flutter Developer", company="Acme",
            text="We need a Flutter developer with Dart and Firebase. Remote, worldwide. Apply: jobs@acme.example",
            posted="2026-10-10", location="Worldwide", kind="job", pay=None):
    from fursa.sources import opportunity

    return opportunity(source, "Fake board", url, title, company, text, posted=posted, location=location,
                       kind=kind, remote=True, pay=pay)


def fake_source(items, name="fake", every=1):
    return SimpleNamespace(NAME=name, LABEL="Fake board", EVERY_HOURS=every, fetch=lambda ctx: [dict(i) for i in items])


def _strict(schema, path="$"):
    """Structured outputs need additionalProperties false and every property required."""
    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False, path
        assert set(schema.get("required", [])) == set(schema.get("properties", {})), path
        for key, sub in schema["properties"].items():
            _strict(sub, f"{path}.{key}")
    if schema.get("type") == "array":
        _strict(schema["items"], f"{path}[]")
    for sub in schema.get("anyOf", []):
        _strict(sub, path)
    for banned in ("minimum", "maximum", "minLength", "maxLength"):
        assert banned not in schema, f"{path} uses unsupported {banned}"


class FakeClaude:
    """Stands in for anthropic.Anthropic(): checks request shapes, returns canned agent answers."""

    def __init__(self, approve=True, invent_contact=True):
        self.calls = []
        self.approve = approve
        self.invent_contact = invent_contact
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append(kw)
        assert kw["model"] in ("claude-haiku-5-5", "claude-opus-5-5"), kw["model"]
        assert isinstance(kw["max_tokens"], int) and kw["max_tokens"] <= 16000
        for banned in ("temperature", "top_p", "top_k", "thinking"):
            assert banned not in kw
        assert kw["output_config"]["effort"] in ("low", "medium", "high", "xhigh", "max")
        user = kw["messages"][0]["content"]
        searches = 0
        if kw.get("tools"):
            assert kw["tools"][0]["name"] == "web_search" and kw["tools"][0]["max_uses"] >= 1
            assert "format" not in kw["output_config"]
            searches = kw["tools"][0]["max_uses"]
            text = 'Found these:\n```json\n[{"title": "Flutter Developer", "company": "Zain Iraq", "url": "https://www.linkedin.com/jobs/view/123", "platform": "LinkedIn", "posted": "2026-10-09", "location": "Baghdad, Iraq", "pay": null, "kind": "job", "language": "en", "snippet": "Flutter developer, Baghdad, hybrid."}, {"title": "no url"}]\n```'
        else:
            schema = kw["output_config"]["format"]["schema"]
            _strict(schema)
            payload = json.loads(user)
            props = schema["properties"]
            if "items" in props:  # scout
                items = []
                for p in payload["postings"]:
                    items.append({
                        "i": p["i"], "keep": True, "reason": "fits", "eligibility": "yes", "eligibility_note": "worldwide",
                        "open": "yes", "pay": None, "work_type": "full-time", "channel": "email",
                        "contact": "invented@nowhere.example" if self.invent_contact and p["i"] == 0 else None,
                        "lang": "en", "red_flags": [], "brief": "Build Flutter apps.", "skills": ["flutter", "dart"],
                    })
                text = json.dumps({"items": items})
            elif "fit" in props:  # matcher
                names = [r["name"] for r in payload["repos"]]
                text = json.dumps({"repos": [{"name": n, "why": f"proves {n}"} for n in names[:2]] + [{"name": "ghost-repo", "why": "x"}],
                                   "fit": 88, "fit_reason_ar": "يناسبك لأنك سويت تطبيقات فلاتر."})
            elif "cv_bullets" in props:  # writer
                text = json.dumps({"cv_bullets": ["Built a Flutter clinic app ({GITHUB})."], "subject": "Flutter Developer — {NAME}",
                                   "message": "Hello, I am {NAME}. See https://github.com/Thanoon12k/Pediatric-Clinic-manager. Email {EMAIL}."})
            elif "picks" in props:  # manager
                picks = [{"id": p["id"], "decision": "approve" if self.approve else "reject", "rank": n + 1,
                          "note_ar": "زين إلك.", "fixed_message": "Fixed by manager, {NAME}." if n == 0 else None}
                         for n, p in enumerate(payload["postings"])]
                text = json.dumps({"picks": picks, "summary_ar": "دفعة زينة."})
            elif "ideas" in props:
                text = json.dumps({"ideas": [{"title_ar": f"فكرة {i}", "why_ar": "لأن", "steps_ar": ["1", "2", "3"], "effort": "low", "where": "Mostaql"} for i in range(3)]})
            elif "repos" in props:  # portfolio summaries
                text = json.dumps({"repos": [{"name": r["name"], "summary_en": "An app.", "summary_ar": "تطبيق.", "kind": "app", "maturity": "working app"} for r in payload["repos"]]})
            else:
                raise AssertionError(f"unknown schema {list(props)}")
        usage = SimpleNamespace(input_tokens=1000, output_tokens=200, cache_creation_input_tokens=0, cache_read_input_tokens=0,
                                server_tool_use=SimpleNamespace(web_search_requests=searches))
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=usage, stop_reason="end_turn")
