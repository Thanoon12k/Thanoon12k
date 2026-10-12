import json

import pytest

from fursa import notify, pipeline, portfolio, sources, status
from fursa.sources import websearch
from fursa.store import Store

from .conftest import PORTFOLIO, FakeClaude, fake_source, posting

JOBS = [
    posting(url="https://jobs.example.com/1", title="Senior Flutter Developer", company="Acme",
            text="Flutter, Dart, Firebase, REST APIs. Remote worldwide. Send CV to jobs@acme.example"),
    posting(url="https://jobs.example.com/2", title="Django Backend Developer", company="Beta",
            text="Python, Django, Django REST framework, PostgreSQL. Remote (EMEA).", location="EMEA"),
    posting(url="https://jobs.example.com/3", title="PHP Developer", company="Gamma", text="PHP, Laravel, WordPress"),
    posting(url="https://jobs.example.com/4", title="Flutter Developer", company="Delta", location="USA Only"),
]


@pytest.fixture
def wired(monkeypatch):
    sent = []
    monkeypatch.setattr(sources, "registry", lambda: [fake_source(JOBS)])
    monkeypatch.setattr(portfolio, "refresh", lambda settings, store, llm=None, repos=None: setattr(store, "portfolio", [dict(r) for r in PORTFOLIO]) or 0)
    monkeypatch.setattr(notify, "send", lambda settings, text: sent.append(text) or True)
    return sent


def load(settings):
    return Store(settings).load()


def test_free_mode_runs_without_any_ai(settings, wired):
    report = pipeline.run(settings)
    assert report["mode"] == "free" and report["usd"] == 0
    st = load(settings)
    by_title = {o["title"]: o for o in st.opps.values()}
    assert "PHP Developer" not in by_title and "Flutter Developer" not in by_title  # dropped for free by the rules
    assert by_title["Senior Flutter Developer"]["status"] in ("approved", "drafted", "rejected", "matched")
    draft = by_title["Senior Flutter Developer"].get("draft") or {}
    assert "{NAME}" not in json.dumps(draft) and "Thanoon Younis Mohammed" in draft.get("message", "")
    meta = json.loads((settings.data_dir / "meta.json").read_text())
    assert meta["mode"] == "free" and meta["usage_month"]["usd"] == 0
    runs = json.loads((settings.data_dir / "runs.json").read_text())
    assert len(runs) == 1


def test_ai_mode_full_team(settings, wired):
    settings.anthropic_key = "test-key"
    claude = FakeClaude()
    report = pipeline.run(settings, llm_client=claude)
    assert report["mode"] == "ai" and report["scouted_ai"] == 2 and report["approved"] == 2
    models = [c["model"] for c in claude.calls]
    assert models.count("claude-opus-5-5") == 2  # one review + weekly ideas
    assert all(m == "claude-haiku-5-5" for m in models if m != "claude-opus-5-5")

    st = load(settings)
    approved = sorted((o for o in st.opps.values() if o["status"] == "approved"), key=lambda o: o["manager"]["rank"])
    first = approved[0]
    assert first["scout"]["contact"] is None  # invented contact removed
    assert [r["name"] for r in first["match"]["repos"]] == ["Pediatric-Clinic-manager", "My-Work"] or \
        all(r["name"] != "ghost-repo" for r in first["match"]["repos"])
    assert first["draft"]["message"] == "Fixed by manager, Thanoon Younis Mohammed." and first["draft"]["edited_by_manager"]
    assert "Thanoon Younis Mohammed" in approved[1]["draft"]["message"]
    assert len(wired) == 1 and "فرصة" in wired[0]  # one Telegram digest
    assert st.ideas["ideas"] and st.usage()["usd"] > 0

    # second run: nothing new -> no message, nothing re-announced, no repeated AI work
    claude.calls.clear()
    pipeline.run(settings, llm_client=claude)
    assert len(wired) == 1
    assert not any(c["model"] == "claude-haiku-5-5" for c in claude.calls)


def test_manager_can_reject_everything_and_no_empty_update_is_sent(settings, wired):
    settings.anthropic_key = "test-key"
    pipeline.run(settings, llm_client=FakeClaude(approve=False))
    st = load(settings)
    assert not st.items("approved") and wired == []


def test_budget_cap_switches_to_free_mode(settings, wired):
    settings.anthropic_key = "test-key"
    settings.profile["agents"]["monthly_budget_usd"] = 0.0002  # one Haiku call costs 0.0002
    claude = FakeClaude()
    pipeline.run(settings, llm_client=claude)
    assert len(claude.calls) == 1
    meta = json.loads((settings.data_dir / "meta.json").read_text())
    assert "budget" in meta["llm_note"]


def test_websearch_source(settings):
    from types import SimpleNamespace

    from fursa.llm import LLM

    settings.anthropic_key = "test-key"
    st = load(settings)
    ctx = SimpleNamespace(settings=settings, store=st, llm=LLM(settings, st, client=FakeClaude()))
    assert websearch.available(ctx) == (True, "")
    recs = websearch.fetch(ctx)
    assert len(recs) == 1 and recs[0]["company"] == "Zain Iraq" and recs[0]["extra"]["verified"] == "search result only"
    assert st.usage()["searches"] == 4 and st.state["websearch_turn"] == 1


def test_status_titles_and_apply(settings):
    assert status.parse("[fursa] a1b2c3d4e5f6 applied") == ("a1b2c3d4e5f6", "applied")
    assert status.parse("[FURSA] A1B2C3D4E5F6 Interview please") == ("a1b2c3d4e5f6", "interview")
    assert status.parse("[fursa] a1b2 applied") is None and status.parse("hello") is None
    st = load(settings)
    rec = posting()
    st.add(rec)
    assert status.apply(st, rec["id"], "applied", "sent on Monday")
    assert st.opps[rec["id"]]["user_status"] == "applied" and not status.apply(st, "000000000000", "applied")


def test_digest_is_safe_html(settings):
    rec = posting(title="Flutter <script> dev & co")
    rec.update(id="abc123abc123", elig="yes", match={"repos": [{"name": "moalidaty"}]}, manager={"note_ar": "زين"})
    text = notify.digest(settings, [rec], "ملخص")
    assert "&lt;script&gt;" in text and "<script>" not in text
    assert "https://thanoon12k.github.io/fursa/#abc123abc123" in text and len(text) < 4096


def test_store_prune_and_roundtrip(settings):
    st = load(settings)
    keep = posting(url="https://x.example/keep")
    gone = posting(url="https://x.example/gone")
    st.add(keep), st.add(gone)
    st.set_status(gone, "rejected")
    gone["updated"] = "2026-09-01T00:00:00Z"
    assert st.prune() == 1 and st.known(gone["id"])  # forgotten, but never re-processed
    st.save(meta={"ok": True})
    again = load(settings)
    assert keep["id"] in again.opps and gone["id"] in again.seen
