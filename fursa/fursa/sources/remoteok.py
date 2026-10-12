"""Remote OK public API (latest ~100 remote jobs). Terms: mention Remote OK and link back."""

from .. import net
from ..text import html_to_text, money
from . import opportunity

NAME, LABEL, EVERY_HOURS = "remoteok", "Remote OK", 6
API = "https://remoteok.com/api"


def fetch(ctx) -> list[dict]:
    data = net.get_json(API)
    out = []
    for job in data if isinstance(data, list) else []:
        if not isinstance(job, dict) or not job.get("id") or not job.get("url"):
            continue  # the first element is the legal notice
        out.append(
            opportunity(
                NAME, LABEL, job["url"], job.get("position"), job.get("company"),
                html_to_text(job.get("description")),
                posted=job.get("date") or job.get("epoch"),
                location=job.get("location") or None,
                remote=True,
                pay=money(job.get("salary_min"), job.get("salary_max"), "USD", "year"),
                tags=job.get("tags") or [],
            )
        )
    return out
