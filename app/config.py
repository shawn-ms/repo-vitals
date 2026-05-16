"""Runtime configuration loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# override=True: .env 是本项目的 single source of truth，必须能覆盖宿主 shell 中
# 残留的同名变量（例如开发者已配的 OPENAI_API_KEY 指向官方 OpenAI）。
load_dotenv(override=True)


@dataclass(frozen=True)
class Settings:
    github_token: str | None
    ai_base_url: str
    ai_api_key: str | None
    ai_model: str
    cache_ttl: int

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key)


def load_settings() -> Settings:
    return Settings(
        github_token=os.getenv("GITHUB_TOKEN") or None,
        ai_base_url=os.getenv("AI_BASE_URL", "https://api.minimaxi.com/v1"),
        ai_api_key=os.getenv("AI_API_KEY") or None,
        ai_model=os.getenv("AI_MODEL", "MiniMax-M2"),
        cache_ttl=int(os.getenv("CACHE_TTL_SECONDS", "600")),
    )


settings = load_settings()
