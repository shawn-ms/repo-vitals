"""Pydantic request/response schemas. See spec §4."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    url: str = Field(..., min_length=1, description="GitHub 仓库 URL 或 owner/repo")
