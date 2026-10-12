from urllib.parse import parse_qs, urlsplit

from fursa import contacts, notify
from fursa.writer import ensure_website

from .conftest import posting

PERSON = {"website": "https://make1it.pythonanywhere.com", "github": "Thanoon12k"}


def test_extract_reads_only_what_the_post_says():
    e = contacts.extract
    assert e("للتقديم واتساب 07700000000")["whatsapp"] == "9647700000000"
    assert e("contact +964 770 279 0915 please")["whatsapp"] == "9647702790915"
    assert e("apply: https://wa.me/9647801112222")["whatsapp"] == "9647801112222"
    assert e("WhatsApp: +44 7911 123456")["whatsapp"] == "447911123456"
    assert "whatsapp" not in e("Call our office +44 20 7946 0958")  # a foreign number without WhatsApp
    assert "whatsapp" not in e("الراتب 7500000 دينار")  # a salary is not a phone number
    assert e("send your CV to hr@acme.io today")["email"] == "hr@acme.io"
    assert "email" not in e("from noreply@acme.io")
    assert e("للتواصل @hr_acme")["telegram"] == "hr_acme"
    assert "telegram" not in e("تابعونا على @other_channel")  # promotion, not a contact
    assert "telegram" not in e("للتواصل @IQ_JOBS", channel="IQ_JOBS")
    assert e("x", apply_url="https://acme.io/apply") == {"apply_url": "https://acme.io/apply"}


def test_website_goes_into_every_message():
    ar = "السلام عليكم\nأعمالي:\nhttps://github.com/Thanoon12k/a\nhttps://github.com/Thanoon12k/b\nالتكلفة: [السعر]"
    out = ensure_website(ar, PERSON, "ar").split("\n")
    assert out[4] == "معرض أعمالي (كل المشاريع مع صور): https://make1it.pythonanywhere.com" and out[5] == "التكلفة: [السعر]"
    en = ensure_website("Hello, I can help.", PERSON, "en")
    assert en.endswith("Portfolio with screenshots of all my projects: https://make1it.pythonanywhere.com")
    same = "See https://make1it.pythonanywhere.com/ for more"
    assert ensure_website(same, PERSON, "en") == same


def test_telegram_buttons_open_apps_with_the_draft(settings):
    rec = posting()
    rec.update(id="abc123abc123", draft={"message": "مرحبا، هذا طلبي", "subject": "Flutter role"},
               contacts={"whatsapp": "9647700000000", "email": "hr@acme.io", "telegram": "hr_acme", "apply_url": "https://acme.io/apply"})
    rows = notify.buttons(settings, rec)
    labels = [[b["text"] for b in row] for row in rows]
    assert labels == [["📲 واتساب", "✉️ إيميل", "💬 تلگرام"], ["📝 رابط التقديم", "📤 إرسال المسودة"], ["🔗 الإعلان", "📄 التفاصيل"]]
    wa = urlsplit(rows[0][0]["url"])
    assert wa.netloc == "wa.me" and parse_qs(wa.query)["text"] == ["مرحبا، هذا طلبي"]
    mail = parse_qs(urlsplit(rows[0][1]["url"]).query)
    assert mail["to"] == ["hr@acme.io"] and "body" not in mail  # WhatsApp already carries the draft
    share = parse_qs(urlsplit(rows[1][1]["url"]).query)
    assert share["text"] == ["مرحبا، هذا طلبي"] and share["url"] == ["https://github.com/Thanoon12k"]

    platform = posting()
    platform.update(id="def456def456", draft={"message": "hi"})
    assert [[b["text"] for b in row] for row in notify.buttons(settings, platform)] == [["📤 إرسال المسودة"], ["🔗 الإعلان", "📄 التفاصيل"]]


def test_long_drafts_are_clipped_for_links():
    long = "سطر\n" * 1000
    assert len(contacts.clip_for_url(long)) <= 1800
