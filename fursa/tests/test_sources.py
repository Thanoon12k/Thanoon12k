"""Parsers against small hand-written samples shaped like each real feed."""

from types import SimpleNamespace

from fursa import net
from fursa.sources import freelancer, guess_lang, himalayas, hn, khamsat, mostaql, remoteok, remotive, telegram, websearch, wwr

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


TELEGRAM_HTML = """
<div class="tgme_widget_message_wrap js-widget_message_wrap"><div class="tgme_widget_message" data-post="remote_python_jobs/1434">
<div class="tgme_widget_message_text js-message_text" dir="auto">Published time : 2026-10-11<br/>Company name : Upwork client<br/>
Title : Python Developer for Personal Project<br/>Location : Worldwide<br/>Anywhere : Yes<br/>Remote : Yes</div>
<a class="tgme_widget_message_date" href="https://t.me/remote_python_jobs/1434"><time datetime="2026-10-12T08:00:00+00:00">08:00</time></a>
</div></div>
<div class="tgme_widget_message_wrap js-widget_message_wrap"><div class="tgme_widget_message" data-post="IQ_JOBS/13862">
<div class="tgme_widget_message_text js-message_text" dir="auto">📢 مطلوب مبرمج Flutter لشركة برمجيات<br/>📍 الموقع: بغداد - الكرادة<br/>للتقديم واتساب 07700000000</div>
<time datetime="2026-10-10T09:00:00+00:00">09:00</time></div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="IQ_JOBS/13863"><div class="tgme_widget_message_text">short</div></div></div>
"""


def test_telegram_channel_preview():
    remote = telegram.parse(TELEGRAM_HTML, "remote_python_jobs")
    assert len(remote) == 2  # the 'short' post is skipped
    first = remote[0]
    assert first["url"] == "https://t.me/remote_python_jobs/1434" and first["posted"] == "2026-10-12"
    assert first["title"] == "Python Developer for Personal Project" and first["company"] == "Upwork client"
    assert first["location"] == "Worldwide" and first["kind"] == "job"  # "Anywhere : Yes" means worldwide
    iraq = telegram.parse(TELEGRAM_HTML, "IQ_JOBS", in_iraq=True)[1]
    assert iraq["title"] == "مطلوب مبرمج Flutter لشركة برمجيات" and iraq["location"] == "Iraq - بغداد - الكرادة"
    assert iraq["lang"] == "ar" and iraq["kind"] == "job"


NAFEZLY_HTML = """
<div class="tgme_widget_message_wrap js-widget_message_wrap"><div class="tgme_widget_message" data-post="nafezly/36760">
<div class="tgme_widget_message_text js-message_text" dir="auto">تم إضافة مشروع جديد على منصة نفذلي<br/>عنوان المشروع : تطوير تطبيق Flutter لمتجر إلكتروني<br/>
تفاصيل المشروع : مطلوب مبرمج فلاتر لربط التطبيق مع REST API وFirebase.<br/>الميزانية : 250 - 500 دولار<br/>
رابط المشروع : <a href="https://nafezly.com/project/56270" target="_blank">https://nafezly.com/project/56270</a></div>
<time datetime="2026-10-12T09:00:00+00:00">09:00</time></div></div>
<div class="tgme_widget_message_wrap js-widget_message_wrap"><div class="tgme_widget_message" data-post="nafezly/36761">
<div class="tgme_widget_message_text js-message_text" dir="auto">تم إضافة مشروع جديد على منصة نفذلي<br/>عنوان المشروع : تطوير تطبيق Flutter لمتجر إلكتروني<br/>
تفاصيل المشروع : مطلوب مبرمج فلاتر لربط التطبيق مع REST API وFirebase.<br/>الميزانية : 250 - 500 دولار<br/>
رابط المشروع : <a href="https://nafezly.com/project/56270" target="_blank">https://nafezly.com/project/56270</a></div>
<time datetime="2026-10-12T09:03:00+00:00">09:03</time></div></div>
"""


def test_telegram_platform_channel_points_to_the_project_page():
    rows = telegram.parse(NAFEZLY_HTML, "nafezly")
    first = rows[0]
    assert first["url"] == "https://nafezly.com/project/56270" and rows[1]["id"] == first["id"]  # a re-post is the same project
    assert first["title"] == "تطوير تطبيق Flutter لمتجر إلكتروني" and first["pay"] == "250 - 500 دولار"
    assert first["kind"] == "freelance" and first["remote"] is True
    assert first["extra"]["telegram_post"] == "https://t.me/nafezly/36760"
    assert first["text"].count("https://nafezly.com/project/56270") == 1  # the link is not appended twice


def test_mostaql_falls_back_to_rss_when_pages_are_refused(monkeypatch):
    import requests

    def fake_get_text(url, **kwargs):
        if url == mostaql.RSS:
            return ('<rss><channel><item><title>تطبيق Flutter</title><link>https://mostaql.com/project/1300000-x</link>'
                    '<description>تطبيق فلاتر</description><pubDate>Mon, 12 Oct 2026 08:00:00 GMT</pubDate></item></channel></rss>')
        response = requests.Response()
        response.status_code = 403
        raise requests.HTTPError("403 Forbidden", response=response)

    monkeypatch.setattr(net, "get_text", fake_get_text)
    rows = mostaql.fetch(None)
    assert [r["url"] for r in rows] == ["https://mostaql.com/project/1300000"]
