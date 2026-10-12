from datetime import datetime, timezone

from fursa import scoring
from fursa.text import clip, html_to_text, make_id, money, norm_url, parse_date

from .conftest import posting


def test_parse_date_shapes():
    utc = timezone.utc
    assert parse_date(1791734403) == datetime(2026, 10, 11, 16, 0, 3, tzinfo=utc)
    assert parse_date("2026-10-08T21:47:32").tzinfo is not None
    assert parse_date("2026-10-11T16:00:03+00:00").day == 11
    assert parse_date("Thu, 17 Sep 2026 10:51:23 +0000").month == 9
    assert parse_date("11/10/2026 21:59:02") == datetime(2026, 10, 11, 21, 59, 2, tzinfo=utc)  # Khamsat: day first
    assert parse_date("2026-10-12 18:47:36").hour == 18
    assert parse_date("not a date") is None and parse_date(None) is None


def test_urls_and_ids_ignore_tracking():
    a = "https://Example.com/jobs/1/?utm_source=x&ref=abc&id=7#top"
    assert norm_url(a) == "https://example.com/jobs/1?id=7"
    assert make_id(a) == make_id("https://example.com/jobs/1?id=7")


def test_text_helpers():
    assert html_to_text("<p>Hello&amp;bye</p><ul><li>one</li></ul><script>x()</script>") == "Hello&bye\none"
    assert clip("word " * 50, 30).endswith("…") and len(clip("word " * 50, 30)) <= 30
    assert money(0, 0) is None
    assert money(2000, 3000, "USD", "month") == "$2k–$3k/month"
    assert money(25, None, "EUR") == "25 EUR"


def test_relevance_title_counts_double_and_arabic_is_normalized():
    kw = {"flutter": 10, "django": 10, "فلاتر": 10}
    score, tags = scoring.relevance("Flutter Developer", "uses django", kw, {"php": -4})
    assert score == 30 and tags == ["flutter", "django"]
    assert scoring.relevance("مطلوب مبرمج فلاتر", "", kw)[0] == 20
    assert scoring.relevance("Java + JavaScript", "", {"java": 5})[0] == 10  # 'java' does not match 'javascript' twice
    assert scoring.relevance("PHP dev", "php laravel", {}, {"php": -4})[0] == -8


def test_eligibility():
    e = scoring.eligibility
    assert e("Worldwide", "", "job", "x")[0] == "yes"
    assert e("Baghdad, Iraq", "", "job", "x")[0] == "yes"
    assert e("EMEA", "", "job", "x")[0] == "likely"
    assert e("USA Only", "", "job", "x")[0] == "no"
    assert e("Poland", "", "job", "x")[0] == "no"
    assert e("Remote", "You must be authorized to work in the US.", "job", "x")[0] == "no"
    assert e(None, "", "freelance", "x")[0] == "likely"
    assert e(None, "", "bounty", "x")[0] == "unclear"
    assert e(None, "", "job", "x")[0] == "unclear"
    # 'status only' must not look like 'us only'
    assert e("Remote", "check the status only via email", "job", "x")[0] == "unclear"


def test_assess_drops_what_the_ai_should_never_see(settings):
    ok = posting()
    assert scoring.assess(ok, settings) == (True, "")
    assert "flutter" in ok["tags"] and ok["elig"] == "yes"

    old = posting(posted="2026-08-01")
    assert scoring.assess(old, settings)[1].startswith("too old")

    fee = posting(text="Flutter job. A registration fee of $20 is required.")
    assert scoring.assess(fee, settings)[1] == "asks the applicant to pay"

    us_only = posting(location="USA Only")
    assert scoring.assess(us_only, settings)[0] is False

    off_topic = posting(title="Sales Manager", text="Sell things", location="Worldwide")
    assert scoring.assess(off_topic, settings)[1].startswith("low relevance")

    tiny = posting(kind="freelance", location=None, pay="$10–$30 (fixed)", posted="2026-10-11")
    assert scoring.assess(tiny, settings)[1].startswith("budget too small")

    hourly = posting(kind="freelance", location=None, pay="$2–$6/hour", posted="2026-10-11")
    assert scoring.assess(hourly, settings)[1].startswith("budget too small")

    fair = posting(kind="freelance", location=None, pay="$250–$750 (fixed)", posted="2026-10-11")
    assert scoring.assess(fair, settings)[0] is True
