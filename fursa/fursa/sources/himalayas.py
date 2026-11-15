"""Himalayas public job search API. Gives explicit location restrictions and expiry dates."""

from .. import net
from ..text import html_to_text, money
from . import opportunity

NAME, LABEL, EVERY_HOURS = "himalayas", "Himalayas", 12
API = "https://himalayas.app/jobs/api/search"


def fetch(ctx) -> list[dict]:
    out = []
    for query in ctx.settings.search.get("queries", ["flutter", "django", "python"]):
        data = net.get_json(API, params={"q": query})
        for job in data.get("jobs", []):
            url = job.get("guid") or job.get("applicationLink")
            if not url:
                continue
            restrictions = job.get("locationRestrictions") or []
            out.append(
                opportunity(
                    NAME, LABEL, url, job.get("title"), job.get("companyName"),
                    html_to_text(job.get("description") or job.get("excerpt")),
                    posted=job.get("pubDate"),
                    expires=job.get("expiryDate"),
                    location=", ".join(restrictions) if restrictions else "Worldwide",
                    remote=True,
                    pay=money(job.get("minSalary"), job.get("maxSalary"), job.get("currency"), job.get("salaryPeriod")),
                    tags=(job.get("categories") or [])[:6],
                    extra={"employment": job.get("employmentType"), "seniority": job.get("seniority")},
                )
            )
    return out
