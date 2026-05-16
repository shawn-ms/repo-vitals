"""Aggregation / derived metrics. Pure functions for easy testing."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    # GitHub returns "...Z"
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def compute_metrics(repo: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    created = _parse_iso(repo.get("created_at"))
    pushed = _parse_iso(repo.get("pushed_at"))
    return {
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "watchers": repo.get("subscribers_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "size_kb": repo.get("size", 0),
        "age_days": (now - created).days if created else None,
        "days_since_push": (now - pushed).days if pushed else None,
    }


def aggregate_languages(langs: dict[str, int]) -> list[dict]:
    total = sum(langs.values())
    if total <= 0:
        return []
    items = [
        {"name": name, "bytes": b, "percent": round(b * 100 / total, 2)}
        for name, b in langs.items()
    ]
    items.sort(key=lambda x: x["bytes"], reverse=True)
    return items


def top_contributors(contribs: list[dict], n: int = 10) -> list[dict]:
    sorted_ = sorted(contribs, key=lambda c: c.get("contributions", 0), reverse=True)
    return [
        {
            "login": c.get("login", ""),
            "contributions": c.get("contributions", 0),
            "avatar_url": c.get("avatar_url", ""),
        }
        for c in sorted_[:n]
    ]


def _normalize_commit_activity(activity: list[dict]) -> list[dict]:
    out: list[dict] = []
    for w in activity:
        ts = w.get("week")
        if ts is None:
            continue
        d = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        out.append({"week_start": d, "commits": w.get("total", 0)})
    return out


def _license_id(repo: dict) -> str | None:
    lic = repo.get("license")
    if isinstance(lic, dict):
        return lic.get("spdx_id") or lic.get("name")
    return None


def build_report_payload(
    *,
    repo: dict,
    languages: dict[str, int],
    contributors: list[dict],
    commit_activity: list[dict],
) -> dict[str, Any]:
    """Assemble the response body matching spec §4 schema (sans `ai` field)."""
    return {
        "repo": {
            "full_name": repo.get("full_name", ""),
            "description": repo.get("description"),
            "html_url": repo.get("html_url", ""),
            "homepage": repo.get("homepage"),
            "license": _license_id(repo),
            "created_at": repo.get("created_at"),
            "pushed_at": repo.get("pushed_at"),
            "default_branch": repo.get("default_branch"),
            "topics": repo.get("topics", []) or [],
            "archived": bool(repo.get("archived", False)),
        },
        "metrics": compute_metrics(repo),
        "languages": aggregate_languages(languages),
        "commit_activity": _normalize_commit_activity(commit_activity),
        "top_contributors": top_contributors(contributors),
    }
