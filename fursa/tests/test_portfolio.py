import base64

from fursa import net, portfolio
from fursa.llm import LLM

from .conftest import PORTFOLIO, FakeClaude, posting

PUBSPEC = """name: clinic
dependencies:
  flutter:
    sdk: flutter

  supabase_flutter: ^2.0.0
  flutter_riverpod: ^2.4.0
  # charts
  fl_chart: ^0.66.0

dev_dependencies:
  flutter_test:
    sdk: flutter
"""

REPO = {"name": "clinic", "full_name": "Thanoon12k/clinic", "html_url": "https://github.com/Thanoon12k/clinic",
        "description": "Clinic app", "pushed_at": "2026-05-28T10:00:00Z", "stargazers_count": 2, "owner": {"login": "Thanoon12k"}}


def fake_api(calls):
    def get_json(url, params=None, headers=None, timeout=30):
        calls.append(url)
        if url.endswith("/users/Thanoon12k/repos"):
            return [REPO, {**REPO, "name": "fork", "full_name": "Thanoon12k/fork", "fork": True}]
        if url.endswith("/orgs/MetaluxTech/repos"):
            return []
        if url.endswith("/languages"):
            return {"Dart": 9000, "C++": 3000, "HTML": 200}
        if url.endswith("/contents"):
            return [{"name": n} for n in ("lib", "test", "pubspec.yaml", "android", "syringe_arduino")]
        if url.endswith("/contents/test"):
            return [{"name": "widget_test.dart"}, {"name": "unit"}]
        if url.endswith("/contents/pubspec.yaml"):
            return {"encoding": "base64", "content": base64.b64encode(PUBSPEC.encode()).decode()}
        if url.endswith("/contributors"):
            return [{"login": "Thanoon12k", "contributions": 8}, {"login": "friend", "contributions": 2}]
        raise AssertionError(url)
    return get_json


def test_refresh_reads_real_facts_and_caches(settings, store, monkeypatch):
    calls = []
    monkeypatch.setattr(net, "get_json", fake_api(calls))
    monkeypatch.setattr(net, "get_text", lambda url, **kw: "# Clinic\nA Flutter app for a pediatric clinic with Supabase. " * 3)
    settings.anthropic_key = "k"
    llm = LLM(settings, store, client=FakeClaude())
    assert portfolio.refresh(settings, store, llm=llm) == 1  # the fork is skipped
    facts = store.portfolio_cache["Thanoon12k/clinic"]
    assert facts["dependencies"] == ["supabase_flutter", "flutter_riverpod", "fl_chart"]
    assert {"flutter", "dart", "supabase", "riverpod", "charts", "iot"} <= set(facts["tags"])
    assert "c++" not in facts["tags"] and "html" not in facts["tags"]  # generated platform code is not a skill
    assert facts["has_tests"] is True and facts["own_share"] == 0.8 and facts["readme_template"] is False
    view = store.portfolio[0]
    assert view["summary_ar"] == "تطبيق." and view["quality"] > 0

    calls.clear()
    assert portfolio.refresh(settings, store, llm=llm) == 0  # unchanged repo: only the listing is read again
    assert all("/contents" not in c and "/languages" not in c for c in calls)


def test_preselect_prefers_matching_stack():
    job = posting(title="Django REST developer")
    job["tags"] = ["django", "api"]
    names = [r["name"] for r in portfolio.preselect(job, PORTFOLIO, k=2)]
    assert names[0] == "moalidaty"
    flutter_job = posting()
    flutter_job["tags"] = ["flutter"]
    assert portfolio.preselect(flutter_job, PORTFOLIO, k=1)[0]["name"] == "Pediatric-Clinic-manager"
