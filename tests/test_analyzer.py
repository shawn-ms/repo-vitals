"""Tests for app.analyzer — pure aggregation logic, no I/O."""
from datetime import datetime, timezone

from app.analyzer import (
    aggregate_languages,
    build_report_payload,
    compute_metrics,
    top_contributors,
)


def test_aggregate_languages_percent_sums_to_100(sample_languages_json):
    out = aggregate_languages(sample_languages_json)
    assert len(out) == 3
    total = sum(item["percent"] for item in out)
    assert abs(total - 100.0) < 0.01, f"百分比之和应≈100, 实际={total}"
    # 降序
    assert out[0]["bytes"] >= out[1]["bytes"] >= out[2]["bytes"]


def test_aggregate_languages_empty():
    assert aggregate_languages({}) == []


def test_top_contributors_keeps_top_n(sample_contributors_json):
    out = top_contributors(sample_contributors_json, n=10)
    assert len(out) == 10
    assert out[0]["login"] == "user0"
    assert all({"login", "contributions", "avatar_url"} <= set(c) for c in out)


def test_compute_metrics_age_and_freshness(sample_repo_json):
    m = compute_metrics(sample_repo_json, now=datetime(2024, 5, 8, tzinfo=timezone.utc))
    assert m["stars"] == 70000
    assert m["forks"] == 6000
    assert m["watchers"] == 800
    assert m["open_issues"] == 200
    assert m["age_days"] > 0
    assert m["days_since_push"] == 6  # 2024-05-08 00:00Z - 2024-05-01 10:00Z = 6d14h → 截断 6


def test_build_report_payload_has_all_sections(
    sample_repo_json, sample_languages_json, sample_contributors_json, sample_commit_activity_json
):
    payload = build_report_payload(
        repo=sample_repo_json,
        languages=sample_languages_json,
        contributors=sample_contributors_json,
        commit_activity=sample_commit_activity_json,
    )
    # 契约对齐 spec §4
    for key in ("repo", "metrics", "languages", "commit_activity", "top_contributors"):
        assert key in payload, f"响应缺少字段 {key}"
    assert payload["repo"]["license"] == "MIT"
    assert payload["repo"]["full_name"] == "fastapi/fastapi"
    assert len(payload["top_contributors"]) <= 10
    assert len(payload["commit_activity"]) == 52


def test_build_report_handles_missing_license():
    repo = {
        "full_name": "a/b",
        "description": None,
        "html_url": "",
        "homepage": None,
        "license": None,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": "2020-01-02T00:00:00Z",
        "default_branch": "main",
        "topics": [],
        "archived": True,
        "stargazers_count": 0,
        "forks_count": 0,
        "subscribers_count": 0,
        "open_issues_count": 0,
        "size": 0,
    }
    payload = build_report_payload(repo=repo, languages={}, contributors=[], commit_activity=[])
    assert payload["repo"]["license"] is None
    assert payload["repo"]["archived"] is True
