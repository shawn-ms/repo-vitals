"""URL parsing utilities. Per spec §3."""
from __future__ import annotations

import re

_PATTERNS = [
    # https://github.com/owner/repo(.git)(/)
    re.compile(r"^https?://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+?)(?:\.git)?/?$"),
    # git@github.com:owner/repo(.git)
    re.compile(r"^git@github\.com:(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+?)(?:\.git)?$"),
    # owner/repo shorthand
    re.compile(r"^(?P<owner>[A-Za-z0-9][A-Za-z0-9._-]*)/(?P<repo>[A-Za-z0-9][A-Za-z0-9._-]*)$"),
]


class InvalidGitHubUrlError(ValueError):
    """Raised when input cannot be parsed into owner/repo."""


def parse_repo(url: str) -> tuple[str, str]:
    """Normalize various GitHub URL forms into (owner, repo).

    Raises InvalidGitHubUrlError on unsupported inputs (per spec AC-2).
    """
    if not isinstance(url, str):
        raise InvalidGitHubUrlError("URL 必须是字符串")
    raw = url.strip()
    if not raw:
        raise InvalidGitHubUrlError("URL 不能为空")
    for pat in _PATTERNS:
        m = pat.match(raw)
        if m:
            owner = m.group("owner")
            repo = m.group("repo")
            if repo.endswith(".git"):
                repo = repo[:-4]
            return owner, repo
    raise InvalidGitHubUrlError(f"无法解析 GitHub 仓库地址: {url!r}")
