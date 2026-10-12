"""Parsers against small hand-written samples shaped like each real feed."""

from types import SimpleNamespace

from fursa import net
from fursa.sources import freelancer, guess_lang, himalayas, hn, khamsat, mostaql, remoteok, remotive, websearch, wwr

WWR_RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Acme: Senior Python Developer</title><region>Anywhere in the World</region><country></country>
<skills>Python, Django, and AWS</skills><type>Full-Time</type><description>&lt;p&gt;Django APIs&lt;/p&gt;</description>
<pubDate>Thu, 08 Oct 2026 10:51:23 +0000</pubDate><expires_at>Sat, 07 Nov 2026 10:51:23 +0000</expires_at>
<link>https://weworkremotely.com/remote-jobs/acme-senior-python-developer</link></item>
<item><title>Beta: Backend Engineer</title><region>Anywhere in the World</region>
<country>🇩🇪 Germany, 🇫🇷 France, 🇪🇸 Spain</country><skills>Go</skills><description>Go</description>
<pubDate>Thu, 08 Oct 2026 10:51:23 +0000</pubDate><link>https://weworkremotely.com/remote-jobs/beta-backend</link></item>
</channel></rss>"""

MOSTAQL_HTML = """<table><tbody>
<tr class="project-row"><td><h2 class="mrg--bt-reset">
<a href="https://mostaql.com/project/1285017-slug-here" class="">مبرمج Flutter لتطوير تطبيق</a></h2>
<ul><li><time datetime="2026-10-12 18:47:36" title="2026-10-12 18:47:36">منذ 6 دقائق</time></li>
<li class="text-muted">8 عروض</li></ul>
<p class="project__brief"><a href="https://mostaql.com/project/1285017-slug-here" class="details-url">نحتاج تطبيق فلاتر مع لوحة تحكم</a></p>
</td></tr>
<tr class="project-row"><td>broken row without a link</td></tr>
</tbody></table>"""

MOSTAQL_DETAIL = """<div class="meta-value"><bdi class="label label-prj-open">مفتوح</bdi></div>
<div class="meta-value" data-type= project-budget_range ><span dir="rtl">$250.00 - $500.00</span></div>
<div class="text-wrapper-div carda__content " ><p>تفاصيل كاملة للمشروع</p></div>"""

KHAMSAT_HTML = """<tr id="forum_post-798754" class="forum_post"><td class="details-td">
<h3 class="details-head"><a class="ajaxbtn" href="/community/requests/798754-slug">برمجة سكربت بايثون</a></h3>
<span dir="ltr" title="11&#x2F;10&#x2F;2026 21:59:02 GMT">منذ 20 ساعة</span></td></tr>"""


def ctx(**search):
    settings = SimpleNamespace(search={"queries": ["flutter"], **search}, now=None)
    return SimpleNamespace(settings=settings, llm=None, store=None)


def test_wwr_reads_region_and_country_allow_list():
    jobs = wwr.parse(WWR_RSS)
    assert [j["title"] for j in jobs] == ["Senior Python Developer", "Backend Engineer"]
    assert jobs[0]["company"] == "Acme" and jobs[0]["location"] == "Anywhere in the World"
    assert jobs[0]["expires"] == "2026-11-07" and "django" in jobs[0]["tags"]
    assert jobs[1]["location"].startswith("Only: Germany")


def test_mostaql_listing_and_detail():
    rows = mostaql.parse_listing(MOSTAQL_HTML)
    assert len(rows) == 1
    r = rows[0]
    assert r["url"] == "https://mostaql.com/project/1285017" and r["kind"] == "freelance" and r["lang"] == "ar"
    assert r["posted"] == "2026-10-12" and r["extra"]["bids"] == 8 and "فلاتر" in r["text"]
    detail = mostaql.parse_detail(MOSTAQL_DETAIL)
    assert detail == {"pay": "$250.00 - $500.00", "open": True, "text": "تفاصيل كاملة للمشروع"}


def test_khamsat_listing():
    rows = khamsat.parse_listing(KHAMSAT_HTML)
    assert rows[0]["url"] == "https://khamsat.com/community/requests/798754"
    assert rows[0]["posted"] == "2026-10-11" and rows[0]["kind"] == "gig"


def test_freelancer_project_filters_language_and_status():
    base = {"id": 1, "title": "Flutter app", "seo_url": "flutter/Flutter-app-1", "status": "active",
            "frontend_project_status": "open", "type": "fixed", "budget": {"minimum": 250, "maximum": 750},
            "currency": {"code": "USD", "exchange_rate": 1.0}, "time_submitted": 1791820317, "description": "Build it",
            "jobs": [{"name": "Flutter"}], "language": "en", "bid_stats": {"bid_count": 12}}
    rec = freelancer.from_project(base)
    assert rec["pay"] == "$250–$750 (fixed)" and rec["extra"]["budget_usd_max"] == 750.0 and rec["kind"] == "freelance"
    assert freelancer.from_project({**base, "language": "id"}) is None
    assert freelancer.from_project({**base, "status": "closed"}) is None


def test_hn_only_top_level_and_remote_segment():
    hit = {"objectID": "5", "parent_id": 100, "created_at": "2026-10-02T10:00:00Z",
           "comment_text": "Acme | Flutter Engineer | REMOTE (Worldwide) | $120k<p>We build apps."}
    rec = hn.from_comment(hit, "100")
    assert rec["company"] == "Acme" and rec["location"] == "REMOTE (Worldwide)"
    assert hn.from_comment({**hit, "parent_id": 7}, "100") is None


def test_json_feeds(monkeypatch):
    def fake_get_json(url, params=None, headers=None, timeout=30):
        if "remotive" in url:
            return {"jobs": [{"url": "https://remotive.com/remote-jobs/x-1", "title": "Django Dev", "company_name": "R",
                              "publication_date": "2026-10-08T21:47:32", "candidate_required_location": "Worldwide",
                              "salary": "", "description": "<p>Django</p>", "tags": ["django"]}]}
        if "remoteok" in url:
            return [{"legal": "notice"}, {"id": "9", "url": "https://remoteOK.com/remote-jobs/9", "position": "Flutter",
                                          "company": "O", "date": "2026-10-11T16:00:03+00:00", "location": "", "tags": ["flutter"],
                                          "description": "x", "salary_min": 0, "salary_max": 0}]
        if "himalayas" in url:
            return {"jobs": [{"guid": "https://himalayas.app/companies/a/jobs/b", "title": "Python Dev", "companyName": "H",
                              "locationRestrictions": [], "pubDate": 1791816405, "expiryDate": 1797000405,
                              "minSalary": 40000, "maxSalary": 60000, "currency": "USD", "salaryPeriod": "annual",
                              "description": "<p>Python</p>", "categories": ["Python"]}]}
        raise AssertionError(url)

    monkeypatch.setattr(net, "get_json", fake_get_json)
    assert remotive.fetch(ctx())[0]["location"] == "Worldwide"
    ok = remoteok.fetch(ctx())
    assert len(ok) == 1 and ok[0]["pay"] is None
    him = himalayas.fetch(ctx())[0]
    assert him["location"] == "Worldwide" and him["pay"] == "$40k–$60k/annual" and him["expires"]


def test_websearch_records_keep_only_real_urls():
    recs = websearch.to_records([{"title": "A", "url": "https://x.example/1", "platform": "LinkedIn", "kind": "weird"},
                                 {"title": "B", "url": "not-a-url"}, "junk"])
    assert len(recs) == 1 and recs[0]["kind"] == "job" and recs[0]["source_label"] == "LinkedIn (web search)"


def test_guess_lang():
    assert guess_lang("مطلوب مبرمج Flutter") == "ar"
    assert guess_lang("Flutter developer") == "en"
