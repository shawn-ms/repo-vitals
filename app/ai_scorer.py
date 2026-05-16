"""AI-based project scoring via MiniMax-M2 (OpenAI-compatible API).

Spec AC-4: 任意失败均降级，不影响主流程。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from .config import settings

log = logging.getLogger("ai_scorer")

SYSTEM_PROMPT = """你是开源项目健康度评估专家。基于用户提供的 GitHub 仓库指标 JSON 给出评分。

严格按以下 JSON 结构返回，不要包裹 markdown，不要任何额外解释：
{
  "score": <0-100 整数>,
  "dimensions": {
    "popularity": <0-100>,
    "activity": <0-100>,
    "community": <0-100>,
    "maintainability": <0-100>,
    "documentation": <0-100>
  },
  "comment": "<不超过 50 字的一句话中文总评>",
  "highlights": ["<优势 1>", "<优势 2>", "<优势 3>"],
  "risks": ["<风险 1>", "<风险 2>", "<风险 3>"]
}

打分参考口径：
- popularity: 看 stars/forks/watchers 数量级（百级 50，千级 70，万级 85+）。
- activity: 看 days_since_push 与近 52 周提交总数；半年无提交则 ≤ 40。
- community: 看贡献者数量与头部集中度；单点维护 ≤ 50。
- maintainability: 看 archived/license/open_issues 比例；archived ≤ 30。
- documentation: 看 description/homepage/topics 是否齐全。
"""


def _fallback_payload(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _build_user_prompt(report: dict) -> str:
    slim = {
        "repo": report["repo"],
        "metrics": report["metrics"],
        "languages_top": report["languages"][:5],
        "contributors_count": len(report["top_contributors"]),
        "top_contributor_share": (
            report["top_contributors"][0]["contributions"]
            / max(sum(c["contributions"] for c in report["top_contributors"]), 1)
            if report["top_contributors"]
            else 0
        ),
        "commits_52w_total": sum(w["commits"] for w in report["commit_activity"]),
    }
    return "请根据以下指标为该仓库打分:\n\n" + json.dumps(slim, ensure_ascii=False, indent=2)


def _coerce_response(text: str) -> dict[str, Any]:
    """Tolerant JSON extraction — model may wrap in fences despite instruction."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        # drop optional leading 'json\n'
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    # find first { ... last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 返回中未找到 JSON: {text[:200]}")
    return json.loads(raw[start : end + 1])


async def score_repository(report: dict) -> dict[str, Any]:
    """Return either {available: True, score, dimensions, ...} or {available: False}."""
    if not settings.ai_enabled:
        return _fallback_payload("AI_API_KEY 未配置")

    client = AsyncOpenAI(
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.ai_model,
            max_tokens=4096,  # MiniMax-M2 推理模型，思考过程可能占用不少 token
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(report)},
            ],
            timeout=30.0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("[ai] 调用失败: %s", e)
        return _fallback_payload(f"AI 调用失败: {type(e).__name__}")

    try:
        content = resp.choices[0].message.content or ""
        parsed = _coerce_response(content)
        # 防御性裁剪：保证字段存在 & 范围合法
        parsed["score"] = max(0, min(100, int(parsed.get("score", 0))))
        dims = parsed.get("dimensions", {})
        for k in ("popularity", "activity", "community", "maintainability", "documentation"):
            dims[k] = max(0, min(100, int(dims.get(k, 0))))
        parsed["dimensions"] = dims
        parsed["highlights"] = list(parsed.get("highlights", []))[:5]
        parsed["risks"] = list(parsed.get("risks", []))[:5]
        parsed["available"] = True
        return parsed
    except Exception as e:  # noqa: BLE001
        log.warning("[ai] 响应解析失败: %s", e)
        return _fallback_payload(f"AI 响应解析失败: {type(e).__name__}")
