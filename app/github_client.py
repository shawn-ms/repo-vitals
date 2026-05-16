"""GitHub REST API client. See spec §6 for caching / retry behavior."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

log = logging.getLogger("github_client")

GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 8.0


class GitHubError(Exception):
    """Base."""


class GitHubNotFoundError(GitHubError):
    pass


class GitHubRateLimitError(GitHubError):
    pass


class GitHubUpstreamError(GitHubError):
    pass


class GitHubClient:
    """Thin async wrapper with in-process TTL cache + 202 retry."""

    def __init__(self, token: str | None = None, cache_ttl: int = 600) -> None:
        self._token = token
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}

    # ------------------------------------------------------------------ #
    # Internal HTTP
    # ------------------------------------------------------------------ #
    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-scan/0.1",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _cache_get(self, key: str) -> Any | None:
        if self._cache_ttl <= 0:
            return None
        item = self._cache.get(key)
        if not item:
            return None
        ts, value = item
        if time.time() - ts > self._cache_ttl:
            self._cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: str, value: Any) -> None:
        if self._cache_ttl > 0:
            self._cache[key] = (time.time(), value)

    async def _get(self, path: str, *, allow_202: bool = False) -> tuple[int, Any]:
        cached = self._cache_get(path)
        if cached is not None:
            return 200, cached

        url = f"{GITHUB_API}{path}"
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(url, headers=self._headers())
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log.info("[github] GET %s -> %s (%dms)", path, resp.status_code, elapsed_ms)

        if resp.status_code == 200:
            data = resp.json()
            self._cache_set(path, data)
            return 200, data
        if resp.status_code == 202 and allow_202:
            return 202, None
        if resp.status_code == 404:
            raise GitHubNotFoundError(f"仓库不存在或为私有: {path}")
        if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubRateLimitError("GitHub 限频，请配置 GITHUB_TOKEN 后重试")
        if resp.status_code >= 500 or resp.status_code == 502:
            raise GitHubUpstreamError(f"GitHub 上游异常: {resp.status_code}")
        # Other 4xx
        raise GitHubUpstreamError(f"GitHub 返回非预期状态码: {resp.status_code}")

    # ------------------------------------------------------------------ #
    # Public methods
    # ------------------------------------------------------------------ #
    async def get_repo(self, owner: str, repo: str) -> dict:
        _, data = await self._get(f"/repos/{owner}/{repo}")
        return data

    async def get_languages(self, owner: str, repo: str) -> dict[str, int]:
        _, data = await self._get(f"/repos/{owner}/{repo}/languages")
        return data or {}

    async def get_contributors(self, owner: str, repo: str) -> list[dict]:
        try:
            _, data = await self._get(f"/repos/{owner}/{repo}/contributors")
            return data or []
        except GitHubUpstreamError:
            return []  # 一些空仓库 contributors 会 204；降级返回空

    async def get_commit_activity(self, owner: str, repo: str) -> list[dict]:
        """Per spec §6: GitHub 首次请求会返回 202，重试一次。
        若 stats 接口持续不可用（异步统计未就绪），自动 fallback 到 /commits 聚合。
        """
        path = f"/repos/{owner}/{repo}/stats/commit_activity"
        status, data = await self._get(path, allow_202=True)
        if status == 202:
            await asyncio.sleep(1.0)
            status, data = await self._get(path, allow_202=True)
        if status == 200 and data:
            return data
        # Fallback：stats 不可用，改拉最近 12 周提交并按周聚合
        log.info("[github] stats/commit_activity unavailable, fallback to /commits")
        return await self._commits_by_week_fallback(owner, repo, weeks=12)

    async def _commits_by_week_fallback(
        self, owner: str, repo: str, weeks: int = 12
    ) -> list[dict]:
        """拉最近 N 周提交（最多 100 条）并按 UTC 周聚合。
        返回结构与 stats/commit_activity 一致：[{week: <unix ts>, total: <count>}, ...]
        """
        from collections import Counter
        from datetime import datetime, timedelta, timezone

        since = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        path = f"/repos/{owner}/{repo}/commits?per_page=100&since={since}"
        try:
            _, commits = await self._get(path)
        except (GitHubNotFoundError, GitHubUpstreamError):
            return []
        if not isinstance(commits, list):
            return []

        buckets: Counter[int] = Counter()
        for c in commits:
            try:
                ts_str = c["commit"]["author"]["date"]
                d = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                # Snap to Sunday 00:00 UTC (GitHub stats 也是按周日切分)
                sunday = d - timedelta(days=(d.weekday() + 1) % 7)
                sunday = sunday.replace(hour=0, minute=0, second=0, microsecond=0)
                buckets[int(sunday.timestamp())] += 1
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(
            [{"week": ts, "total": n} for ts, n in buckets.items()],
            key=lambda x: x["week"],
        )
