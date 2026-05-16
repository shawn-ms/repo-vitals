"""POST /api/analyze endpoint."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from ..ai_scorer import score_repository
from ..analyzer import build_report_payload
from ..config import settings
from ..github_client import (
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubUpstreamError,
)
from ..schemas import AnalyzeRequest
from ..url_parser import InvalidGitHubUrlError, parse_repo

log = logging.getLogger("analyze")
router = APIRouter(prefix="/api", tags=["analyze"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/analyze")
async def analyze(payload: AnalyzeRequest) -> dict:
    try:
        owner, repo = parse_repo(payload.url)
    except InvalidGitHubUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    gh = GitHubClient(token=settings.github_token, cache_ttl=settings.cache_ttl)
    try:
        # Fan out 4 GitHub calls concurrently
        repo_data, langs, contribs, activity = await asyncio.gather(
            gh.get_repo(owner, repo),
            gh.get_languages(owner, repo),
            gh.get_contributors(owner, repo),
            gh.get_commit_activity(owner, repo),
        )
    except GitHubNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except GitHubUpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    report = build_report_payload(
        repo=repo_data,
        languages=langs,
        contributors=contribs,
        commit_activity=activity,
    )
    report["ai"] = await score_repository(report)
    return report
