"""Jobicy public API (remote jobs). Terms: credit Jobicy with a direct link to the job."""

from .. import net
from ..text import html_to_text, money
from . import opportunity

NAME, LABEL, EVERY_HOURS = "jobicy", "Jobicy", 12
API = "https://jobicy.com/api/v2/remote-jobs"


def fetch(ctx) -> list[dict]:
    out = []
    for query in ctx.settings.search.get("queries", ["flutter", "django", "python"]):
        data = net.get_json(API, params={"count": 50, "tag": query})
        for job in data.get("jobs", []):
            if not job.get("url"):
                continue
            out.append(
                opportunity(
                    NAME, LABEL, job["url"], job.get("jobTitle"), job.get("companyName"),
                    html_to_text(job.get("jobDescription") or job.get("jobExcerpt")),
                    posted=job.get("pubDate"),
                    location=job.get("jobGeo") or None,
                    remote=True,
                    pay=money(job.get("salaryMin"), job.get("salaryMax"), job.get("salaryCurrency"), job.get("salaryPeriod")),
                    tags=list(job.get("jobIndustry") or []),
                    extra={"type": job.get("jobType"), "level": job.get("jobLevel")},
                )
            )
    return out
