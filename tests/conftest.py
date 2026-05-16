"""Shared pytest fixtures.

We never hit the real GitHub API in tests; respx stubs httpx transports.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def sample_repo_json() -> dict:
    return {
        "full_name": "fastapi/fastapi",
        "description": "FastAPI framework",
        "html_url": "https://github.com/fastapi/fastapi",
        "homepage": "https://fastapi.tiangolo.com",
        "license": {"spdx_id": "MIT"},
        "created_at": "2018-12-08T08:21:47Z",
        "pushed_at": "2024-05-01T10:00:00Z",
        "default_branch": "master",
        "topics": ["python", "api", "async"],
        "archived": False,
        "stargazers_count": 70000,
        "forks_count": 6000,
        "subscribers_count": 800,
        "open_issues_count": 200,
        "size": 50000,
    }


@pytest.fixture
def sample_languages_json() -> dict:
    return {"Python": 800000, "HTML": 50000, "CSS": 30000}


@pytest.fixture
def sample_contributors_json() -> list[dict]:
    return [
        {"login": f"user{i}", "contributions": 200 - i * 10, "avatar_url": f"https://x/{i}"}
        for i in range(15)
    ]


@pytest.fixture
def sample_commit_activity_json() -> list[dict]:
    return [
        {"week": 1714060800 + i * 7 * 86400, "total": 5 + (i % 4)}
        for i in range(52)
    ]
