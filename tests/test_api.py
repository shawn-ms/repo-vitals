"""End-to-end FastAPI tests using TestClient with mocked GitHub."""
import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app


def _mock_all_endpoints(owner, repo, repo_json, langs_json, contribs_json, activity_json):
    """Helper to register the 4 GitHub endpoints used by analyzer."""
    base = f"https://api.github.com/repos/{owner}/{repo}"
    respx.get(base).mock(return_value=httpx.Response(200, json=repo_json))
    respx.get(f"{base}/languages").mock(return_value=httpx.Response(200, json=langs_json))
    respx.get(f"{base}/contributors").mock(return_value=httpx.Response(200, json=contribs_json))
    respx.get(f"{base}/stats/commit_activity").mock(
        return_value=httpx.Response(200, json=activity_json)
    )


@respx.mock
def test_ac1_analyze_full_flow(
    monkeypatch, sample_repo_json, sample_languages_json,
    sample_contributors_json, sample_commit_activity_json,
):
    monkeypatch.setenv("AI_API_KEY", "")  # 强制 AI 降级
    _mock_all_endpoints(
        "fastapi", "fastapi", sample_repo_json, sample_languages_json,
        sample_contributors_json, sample_commit_activity_json,
    )
    app = create_app()
    client = TestClient(app)
    r = client.post("/api/analyze", json={"url": "https://github.com/fastapi/fastapi"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["repo"]["full_name"] == "fastapi/fastapi"
    assert body["metrics"]["stars"] == 70000
    assert len(body["languages"]) == 3
    assert body["ai"]["available"] is False  # AC-4


def test_ac2_invalid_url_returns_400():
    app = create_app()
    client = TestClient(app)
    r = client.post("/api/analyze", json={"url": "not-a-url"})
    assert r.status_code == 400
    assert "detail" in r.json()


@respx.mock
def test_ac3_repo_not_found_returns_404():
    respx.get("https://api.github.com/repos/ghost/ghost-xyz").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/api/analyze", json={"url": "https://github.com/ghost/ghost-xyz"}
    )
    assert r.status_code == 404


@respx.mock
def test_ac5_rate_limit_returns_429():
    respx.get("https://api.github.com/repos/x/y").mock(
        return_value=httpx.Response(
            403, json={"message": "API rate limit exceeded"},
            headers={"X-RateLimit-Remaining": "0"},
        )
    )
    app = create_app()
    client = TestClient(app)
    r = client.post("/api/analyze", json={"url": "https://github.com/x/y"})
    assert r.status_code == 429
    assert "GITHUB_TOKEN" in r.json()["detail"] or "限频" in r.json()["detail"]


def test_health_endpoint():
    app = create_app()
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok"}
