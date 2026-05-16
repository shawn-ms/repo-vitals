"""Tests for app.github_client.

External HTTP fully mocked via respx so tests are hermetic & offline-safe.
Covers spec §6 (202 retry, caching) and AC-1/3/5.
"""
import httpx
import pytest
import respx

from app.github_client import (
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubUpstreamError,
)


@pytest.fixture
def client():
    c = GitHubClient(token=None, cache_ttl=0)  # cache off for most tests
    yield c


@pytest.mark.asyncio
@respx.mock
async def test_ac1_fetch_repo_ok(client, sample_repo_json):
    respx.get("https://api.github.com/repos/fastapi/fastapi").mock(
        return_value=httpx.Response(200, json=sample_repo_json)
    )
    data = await client.get_repo("fastapi", "fastapi")
    assert data["full_name"] == "fastapi/fastapi"


@pytest.mark.asyncio
@respx.mock
async def test_ac3_not_found_raises(client):
    respx.get("https://api.github.com/repos/nope/nope").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    with pytest.raises(GitHubNotFoundError):
        await client.get_repo("nope", "nope")


@pytest.mark.asyncio
@respx.mock
async def test_ac5_rate_limit_raises(client):
    respx.get("https://api.github.com/repos/x/y").mock(
        return_value=httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={"X-RateLimit-Remaining": "0"},
        )
    )
    with pytest.raises(GitHubRateLimitError):
        await client.get_repo("x", "y")


@pytest.mark.asyncio
@respx.mock
async def test_upstream_5xx_raises(client):
    respx.get("https://api.github.com/repos/x/y").mock(
        return_value=httpx.Response(503, text="bad gateway")
    )
    with pytest.raises(GitHubUpstreamError):
        await client.get_repo("x", "y")


@pytest.mark.asyncio
@respx.mock
async def test_commit_activity_202_retries_once(client, sample_commit_activity_json):
    route = respx.get(
        "https://api.github.com/repos/x/y/stats/commit_activity"
    ).mock(
        side_effect=[
            httpx.Response(202, json={}),
            httpx.Response(200, json=sample_commit_activity_json),
        ]
    )
    data = await client.get_commit_activity("x", "y")
    assert route.call_count == 2, "202 时必须自动重试一次"
    assert len(data) == 52


@pytest.mark.asyncio
@respx.mock
async def test_commit_activity_falls_back_to_commits_when_stats_unavailable(client):
    """连续两次 202 后，fallback 到 /commits 聚合按周提交数。"""
    respx.get(
        "https://api.github.com/repos/x/y/stats/commit_activity"
    ).mock(return_value=httpx.Response(202, json={}))
    # /commits fallback：3 个 commit 落在两个不同周
    respx.get(url__regex=r"https://api\.github\.com/repos/x/y/commits.*").mock(
        return_value=httpx.Response(200, json=[
            {"commit": {"author": {"date": "2024-05-06T10:00:00Z"}}},  # 周一
            {"commit": {"author": {"date": "2024-05-08T10:00:00Z"}}},  # 周三 (同一周)
            {"commit": {"author": {"date": "2024-04-29T10:00:00Z"}}},  # 上周一
        ])
    )
    data = await client.get_commit_activity("x", "y")
    assert len(data) == 2, f"应聚合成 2 个周, 实际 {data}"
    # 总数 = 3
    assert sum(w["total"] for w in data) == 3


@pytest.mark.asyncio
@respx.mock
async def test_commit_activity_fallback_empty_when_no_commits(client):
    """stats 不可用 + commits 也空时，返回 []。"""
    respx.get(
        "https://api.github.com/repos/x/y/stats/commit_activity"
    ).mock(return_value=httpx.Response(202, json={}))
    respx.get(url__regex=r"https://api\.github\.com/repos/x/y/commits.*").mock(
        return_value=httpx.Response(200, json=[])
    )
    data = await client.get_commit_activity("x", "y")
    assert data == []


@pytest.mark.asyncio
@respx.mock
async def test_cache_hit_avoids_second_request(sample_repo_json):
    cached_client = GitHubClient(token=None, cache_ttl=60)
    route = respx.get("https://api.github.com/repos/a/b").mock(
        return_value=httpx.Response(200, json=sample_repo_json)
    )
    await cached_client.get_repo("a", "b")
    await cached_client.get_repo("a", "b")
    assert route.call_count == 1, "10 分钟 TTL 内同一 URL 应复用结果"


@pytest.mark.asyncio
@respx.mock
async def test_token_sent_as_authorization_header(sample_repo_json):
    tokened = GitHubClient(token="ghp_dummy", cache_ttl=0)
    route = respx.get("https://api.github.com/repos/a/b").mock(
        return_value=httpx.Response(200, json=sample_repo_json)
    )
    await tokened.get_repo("a", "b")
    sent = route.calls[0].request.headers.get("authorization", "")
    assert sent.lower().startswith("bearer "), "应使用 Bearer 鉴权"
