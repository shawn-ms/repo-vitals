"""Tests for app.url_parser. Covers spec §3 URL forms and AC-2."""
import pytest

from app.url_parser import InvalidGitHubUrlError, parse_repo


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/fastapi/fastapi",
        "https://github.com/fastapi/fastapi/",
        "https://github.com/fastapi/fastapi.git",
        "http://github.com/fastapi/fastapi",
        "git@github.com:fastapi/fastapi.git",
        "fastapi/fastapi",
    ],
)
def test_parse_accepts_all_spec_forms(url):
    assert parse_repo(url) == ("fastapi", "fastapi"), f"应解析为 fastapi/fastapi, 输入: {url}"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "not-a-url",
        "https://gitlab.com/foo/bar",
        "https://github.com/onlyowner",
        "https://github.com/",
    ],
)
def test_ac2_invalid_urls_raise(url):
    with pytest.raises(InvalidGitHubUrlError):
        parse_repo(url)


def test_parse_strips_whitespace():
    assert parse_repo("  fastapi/fastapi  ") == ("fastapi", "fastapi")
