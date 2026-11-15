"""Remotive public API (remote jobs, delayed 24h). Terms: credit Remotive and link back."""

from .. import net
from ..text import html_to_text
from . import opportunity

NAME, LABEL, EVERY_HOURS = "remotive", "Remotive", 12
API = "https://remotive.com/api/remote-jobs"


def fetch(ctx) -> list[dict]:
    data = net.get_json(API, params={"category": "software-dev"})
    out = []
    for job in data.get("jobs", []):
        if not job.get("url"):
            continue
        out.append(
            opportunity(
                NAME, LABEL, job["url"], job.get("title"), job.get("company_name"),
                html_to_text(job.get("description")),
                posted=job.get("publication_date"),
                location=job.get("candidate_required_location"),
                remote=True,
                pay=job.get("salary") or None,
                tags=job.get("tags") or [],
                extra={"job_type": job.get("job_type")},
            )
        )
    return out
