"""Agent 2's memory: an honest index of the user's PUBLIC GitHub repositories.

Facts come from the GitHub API (languages, manifests, file list, contributors),
not from repository names. Repos are re-read only when they change (pushed_at),
and the optional AI summary is cached the same way, so a weekly refresh costs
almost nothing. Private repositories are never listed.
"""

from __future__ import annotations

import base64
import logging
import re

from . import net
from .scoring import normalize
from .text import age_days, clip

log = logging.getLogger("fursa.portfolio")
API = "https://api.github.com"

# file or dependency -> technology tag
MANIFEST_TAGS = {
    "pubspec.yaml": "flutter", "manage.py": "django", "requirements.txt": "python", "pyproject.toml": "python",
    "package.json": "javascript", "Dockerfile": "docker", "docker-compose.yml": "docker", ".github": "ci",
    "supabase": "supabase", "firebase.json": "firebase", "platformio.ini": "iot",
}
DEPENDENCY_TAGS = {
    "flutter_bloc": "bloc", "bloc": "bloc", "flutter_riverpod": "riverpod", "riverpod": "riverpod", "get": "getx",
    "provider": "provider", "supabase_flutter": "supabase", "firebase_core": "firebase", "cloud_firestore": "firebase",
    "dio": "rest-api", "http": "rest-api", "sqflite": "sqlite", "go_router": "flutter", "fl_chart": "charts",
    "djangorestframework": "django-rest", "django": "django", "channels": "websockets", "celery": "celery",
    "flask": "flask", "fastapi": "fastapi", "playwright": "automation", "selenium": "automation",
    "opencv-python": "opencv", "opencv": "opencv", "tensorflow": "ai", "torch": "ai", "openai": "ai", "anthropic": "ai",
    "pandas": "data", "numpy": "data", "requests": "rest-api", "psycopg2": "postgres", "psycopg2-binary": "postgres",
    "redis": "redis", "gunicorn": "deployment", "streamlit": "data",
}
LANGUAGE_TAGS = {"Dart": "dart", "Python": "python", "JavaScript": "javascript", "TypeScript": "typescript",
                 "C++": "c++", "HTML": "html", "Kotlin": "kotlin", "Java": "java", "PHP": "php"}
TEMPLATE_README = ("a new flutter project", "this project is a starting point for a flutter application")


def _headers(settings) -> dict:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def _get(settings, path: str, **params):
    return net.get_json(f"{API}{path}", params=params or None, headers=_headers(settings))


def list_repos(settings) -> list[dict]:
    """Public, non-fork repos of the user plus org repos (contribution checked later)."""
    user = settings.person.get("github") or settings.owner
    repos, page = [], 1
    while True:
        batch = _get(settings, f"/users/{user}/repos", per_page=100, page=page, type="owner", sort="pushed")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    for org in settings.portfolio.get("extra_orgs", []):
        try:
            repos.extend(_get(settings, f"/orgs/{org}/repos", per_page=100, type="public"))
        except Exception as exc:  # an org we cannot list should not stop the index
            log.warning("cannot list org %s: %s", org, exc)
    exclude = {e.lower() for e in settings.portfolio.get("exclude", [])}
    return [
        r for r in repos
        if not r.get("private") and not r.get("fork") and not r.get("archived")
        and r["name"].lower() not in exclude and r["full_name"].lower() not in exclude
    ]


def _file(settings, full_name: str, path: str) -> str:
    try:
        data = _get(settings, f"/repos/{full_name}/contents/{path}")
    except Exception:
        return ""
    if isinstance(data, dict) and data.get("encoding") == "base64":
        return base64.b64decode(data.get("content", "")).decode("utf-8", "replace")
    return ""


def _dependencies(manifest: str, kind: str) -> list[str]:
    if kind == "pubspec.yaml":
        block = re.search(r"^dependencies:[ \t]*\n(.*?)(?=^\S|\Z)", manifest, re.M | re.S)
        names = re.findall(r"^[ \t]{2}([a-z_][a-z0-9_]*)\s*:", block.group(1) if block else "", re.M)
        return [n for n in names if n != "flutter"]
    return [re.split(r"[<>=!~\[; ]", line.strip(), 1)[0].lower() for line in manifest.splitlines()
            if line.strip() and not line.startswith(("#", "-"))]


def inspect(settings, repo: dict) -> dict:
    """Read one repository's facts. About five API calls."""
    full = repo["full_name"]
    languages = _get(settings, f"/repos/{full}/languages")
    files = [f.get("name", "") for f in _get(settings, f"/repos/{full}/contents") or [] if isinstance(f, dict)]
    readme = ""
    try:
        readme = net.get_text(f"{API}/repos/{full}/readme", headers={**_headers(settings), "Accept": "application/vnd.github.raw"})
    except Exception:
        pass
    manifest_name = next((m for m in ("pubspec.yaml", "requirements.txt") if m in files), "")
    has_tests = any(f in files for f in ("tests", "pytest.ini"))
    if "test" in files:  # Flutter's default test/widget_test.dart alone does not count
        try:
            names = [f.get("name") for f in _get(settings, f"/repos/{full}/contents/test") if isinstance(f, dict)]
            has_tests = has_tests or names != ["widget_test.dart"]
        except Exception:
            pass
    deps = _dependencies(_file(settings, full, manifest_name), manifest_name) if manifest_name else []
    contributors = []
    try:
        contributors = _get(settings, f"/repos/{full}/contributors", per_page=10) or []
    except Exception:
        pass
    me = (settings.person.get("github") or "").lower()
    total = sum(c.get("contributions", 0) for c in contributors) or 0
    mine = sum(c.get("contributions", 0) for c in contributors if (c.get("login") or "").lower() == me)

    total_bytes = sum(languages.values()) or 1
    tags = {LANGUAGE_TAGS[lang] for lang, size in languages.items() if lang in LANGUAGE_TAGS and size / total_bytes >= 0.1}
    if "pubspec.yaml" in files:  # platform folders of a Flutter app are generated code, not skills
        tags -= {"c++", "kotlin", "html", "java"}
    tags.discard("html")
    if any(word in name.lower() for name in files for word in ("arduino", "esp32", "esp8266", ".ino")):
        tags.add("iot")
    tags |= {tag for name, tag in MANIFEST_TAGS.items() if name in files}
    tags |= {DEPENDENCY_TAGS[d] for d in deps if d in DEPENDENCY_TAGS}
    tags |= {normalize(t) for t in repo.get("topics") or []}
    text = normalize(readme[:3000])
    template = any(t in text for t in TEMPLATE_README) or len(readme.strip()) < 120
    return {
        "name": repo["name"],
        "full_name": full,
        "url": repo["html_url"],
        "description": repo.get("description") or "",
        "homepage": repo.get("homepage") or "",
        "stars": repo.get("stargazers_count", 0),
        "pushed_at": repo.get("pushed_at"),
        "created_at": repo.get("created_at"),
        "languages": list(languages)[:6],
        "dependencies": deps[:25],
        "files": files[:40],
        "tags": sorted(t for t in tags if t),
        "readme_excerpt": clip(re.sub(r"[#>*`|\-\[\]()!]+", " ", readme), 700),
        "readme_template": template,
        "has_tests": has_tests,
        "has_ci": ".github" in files,
        "own_share": round(mine / total, 2) if total else (1.0 if repo.get("owner", {}).get("login", "").lower() == me else 0.0),
        "commits": total,
    }


def quality(facts: dict, now) -> float:
    """Deterministic 'how much does this repo prove' score."""
    score = 0.0
    score += 0 if facts.get("readme_template") else 2
    score += 2 if facts.get("homepage") else 0
    score += 1 if facts.get("has_tests") else 0
    score += 1 if facts.get("has_ci") else 0
    score += min(facts.get("stars", 0), 10) / 5
    score += min(facts.get("commits", 0), 40) / 20
    score += min(len(facts.get("dependencies") or []), 15) / 5
    days = age_days(facts.get("pushed_at"), now)
    score += 1.5 if days is not None and days < 365 else 0
    share = facts.get("own_share", 0)
    score *= 1.0 if share >= 0.6 else 0.6 if share >= 0.2 else 0.25
    return round(score, 2)


SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "repos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "summary_en": {"type": "string"},
                    "summary_ar": {"type": "string"},
                    "kind": {"type": "string", "enum": ["app", "backend", "full-stack", "tool", "library", "course", "experiment", "plan-only"]},
                    "maturity": {"type": "string", "enum": ["prototype", "working app", "feature-rich", "unclear"]},
                    "caveat": {"type": "string"},
                },
                "required": ["name", "summary_en", "summary_ar", "kind", "maturity", "caveat"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["repos"],
    "additionalProperties": False,
}

SUMMARY_KEYS = ("summary_en", "summary_ar", "kind", "maturity", "caveat")

SUMMARY_SYSTEM = (
    "You describe a developer's GitHub repositories for recruiters. Use only the facts given (languages, "
    "dependencies, file list, README excerpt). Do not claim production use, users or results that the facts do "
    "not show. A README that is a template says nothing about the app. One factual sentence each: summary_en in "
    "English (max 25 words), summary_ar in Iraqi-friendly Modern Standard Arabic (max 25 words). caveat: what an "
    "employer should know (e.g. template README, no tests, planning only, shared work), max 15 words, or empty."
)


def _summarize(llm, facts: list[dict]) -> dict:
    out = {}
    for start in range(0, len(facts), 8):
        batch = facts[start : start + 8]
        payload = [
            {"name": f["name"], "description": f["description"], "languages": f["languages"], "deps": f["dependencies"][:15],
             "files": f["files"][:20], "readme_template": f["readme_template"], "readme": f["readme_excerpt"][:500]}
            for f in batch
        ]
        result = llm.structured("worker", SUMMARY_SYSTEM, {"repos": payload}, SUMMARY_SCHEMA, max_tokens=4000) if llm else None
        for item in (result or {}).get("repos", []):
            out[item["name"]] = item
    return out


def refresh(settings, store, llm=None, repos: list[dict] | None = None) -> int:
    """Re-index changed repos; rebuild the public portfolio view. Returns repos re-read."""
    cache = store.portfolio_cache
    listed = repos if repos is not None else list_repos(settings)
    changed = []
    for repo in listed:
        cached = cache.get(repo["full_name"])
        if cached and cached.get("pushed_at") == repo.get("pushed_at"):
            continue
        try:
            facts = inspect(settings, repo)
        except Exception as exc:
            log.warning("skip %s: %s", repo["full_name"], exc)
            continue
        cache[repo["full_name"]] = facts  # changed since last time: its summary is written again
        changed.append(facts)

    me = (settings.person.get("github") or "").lower()
    names = {r["full_name"] for r in listed}
    for full in list(cache):  # drop repos that disappeared, and org repos without our commits
        gone = repos is None and full not in names
        if gone or (not full.lower().startswith(me + "/") and cache[full].get("own_share", 0) == 0):
            del cache[full]

    need_summary = [f for f in cache.values() if not f.get("summary_en")]
    if llm is not None and need_summary:
        for name, summary in _summarize(llm, need_summary).items():
            for facts in cache.values():
                if facts["name"] == name:
                    facts.update({k: summary.get(k, "") for k in SUMMARY_KEYS})

    build_view(settings, store)
    store.touch("portfolio")
    return len(changed)


def build_view(settings, store) -> None:
    """The public, compact portfolio the dashboard and the matcher read."""
    view = []
    for facts in store.portfolio_cache.values():
        view.append({
            "name": facts["name"],
            "url": facts["url"],
            "summary_en": facts.get("summary_en") or facts.get("description", ""),
            "summary_ar": facts.get("summary_ar") or "",
            "kind": facts.get("kind") or "",
            "maturity": facts.get("maturity") or "",
            "caveat": facts.get("caveat") or "",
            "tags": facts.get("tags", []),
            "own_share": facts.get("own_share", 0),
            "readme_template": facts.get("readme_template", False),
            "has_tests": facts.get("has_tests", False),
            "stars": facts.get("stars", 0),
            "homepage": facts.get("homepage", ""),
            "pushed": (facts.get("pushed_at") or "")[:10],
            "quality": quality(facts, settings.now),
        })
    store.portfolio = sorted(view, key=lambda r: -r["quality"])


SKILL_TAGS = {
    "flutter": {"flutter", "dart", "bloc", "riverpod", "getx", "provider"},
    "mobile": {"flutter", "dart", "kotlin"},
    "dart": {"dart", "flutter"},
    "django": {"django", "django-rest", "python"},
    "python": {"python", "django", "flask", "fastapi", "automation", "data"},
    "fastapi": {"fastapi", "python"},
    "flask": {"flask", "python"},
    "api": {"rest-api", "django-rest", "fastapi"},
    "backend": {"django", "django-rest", "flask", "fastapi", "postgres", "redis"},
    "firebase": {"firebase"},
    "supabase": {"supabase"},
    "automation": {"automation", "python"},
    "ai": {"ai", "opencv", "data"},
    "opencv": {"opencv"},
    "iot": {"iot", "c++"},
    "dashboard": {"charts", "django", "flutter"},
}


def preselect(rec: dict, portfolio: list[dict], k: int = 6) -> list[dict]:
    """Deterministically shortlist the repos most likely to convince this employer."""
    wanted = set()
    for tag in (rec.get("tags") or []) + [s.lower() for s in (rec.get("scout") or {}).get("skills", [])]:
        wanted |= SKILL_TAGS.get(tag, {tag})
    scored = []
    for repo in portfolio:
        if repo.get("kind") == "plan-only":
            continue
        overlap = len(wanted & set(repo.get("tags") or []))
        if overlap:
            scored.append((overlap * 3 + repo.get("quality", 0), repo))
    scored.sort(key=lambda pair: -pair[0])
    return [repo for _, repo in scored[:k]]
