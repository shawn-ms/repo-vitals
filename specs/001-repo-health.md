# Spec 001 — GitHub Repo Health Check

> Spec-Driven Development: 本文档先于代码与测试存在。所有 API 契约、字段命名、错误码均以此规格为单一事实来源 (single source of truth)。

## 1. 用户故事

| ID  | As a    | I want to                                          | So that                              |
|-----|---------|----------------------------------------------------|--------------------------------------|
| US1 | 开发者  | 粘贴任意公开 GitHub 仓库 URL，一键得到健康度报告 | 评估是否值得引入 / 学习该项目        |
| US2 | 技术选型者 | 同时看到客观指标 + AI 主观评分 + 风险点          | 30 秒内拿到“能不能用”的结论          |
| US3 | 用户    | 即使我没有 GitHub Token 也能跑通                  | demo 体验不被鉴权打断                |

## 2. 验收标准 (Given / When / Then)

### AC-1：合法 URL 返回完整报告
- **Given** 用户输入 `https://github.com/fastapi/fastapi`
- **When** 点击「分析」
- **Then** 在 ≤ 10 s 内返回 200，响应体满足 §4 schema，且 `score ∈ [0, 100]`

### AC-2：非法 URL 友好报错
- **Given** 用户输入 `not-a-url` 或 `https://gitlab.com/x/y`
- **When** 提交
- **Then** 返回 400，`detail` 中文可读，前端展示红色提示而非崩溃

### AC-3：仓库不存在
- **Given** `https://github.com/this-user-does-not-exist-xyz/nope`
- **When** 提交
- **Then** 返回 404 + 中文 detail

### AC-4：AI 不可用降级
- **Given** `ANTHROPIC_API_KEY` 未配置 / AI 调用失败
- **When** 分析任意仓库
- **Then** 仍返回 200，`ai.available=false`，前端隐藏 AI 卡片但其它指标完整展示

### AC-5：限频自我保护
- **Given** GitHub 返回 403 (rate limit)
- **When** 后端转发
- **Then** 返回 429，detail 提示用户配置 `GITHUB_TOKEN`

## 3. URL 解析规则

支持以下输入（统一规范化为 `owner/repo`）：

```
https://github.com/owner/repo
https://github.com/owner/repo/
https://github.com/owner/repo.git
http://github.com/owner/repo
git@github.com:owner/repo.git
owner/repo
```

不支持：子路径（`/tree/main/...`）以外的协议、企业 GHE 域名 (out of scope)。

## 4. API 契约

### `POST /api/analyze`

请求：
```json
{ "url": "https://github.com/owner/repo" }
```

成功响应 (200)：
```json
{
  "repo": {
    "full_name": "owner/repo",
    "description": "...",
    "html_url": "...",
    "homepage": "...",
    "license": "MIT",
    "created_at": "2020-01-01T00:00:00Z",
    "pushed_at": "2024-05-01T00:00:00Z",
    "default_branch": "main",
    "topics": ["python", "api"],
    "archived": false
  },
  "metrics": {
    "stars": 1234,
    "forks": 56,
    "watchers": 78,
    "open_issues": 9,
    "size_kb": 4096,
    "age_days": 1400,
    "days_since_push": 5
  },
  "languages": [
    { "name": "Python", "bytes": 123456, "percent": 92.3 },
    { "name": "HTML",   "bytes":  10000, "percent":  7.7 }
  ],
  "commit_activity": [
    { "week_start": "2024-04-29", "commits": 12 }
  ],
  "top_contributors": [
    { "login": "octocat", "contributions": 321, "avatar_url": "..." }
  ],
  "ai": {
    "available": true,
    "score": 87,
    "dimensions": {
      "popularity": 95,
      "activity": 88,
      "community": 80,
      "maintainability": 82,
      "documentation": 90
    },
    "comment": "活跃的明星项目，文档与社区健康度均高。",
    "highlights": ["star 量级 1k+", "近 7 天内有提交", "MIT 许可证友好"],
    "risks":      ["open issues 偏多", "测试覆盖未知", "维护者依赖单点"]
  }
}
```

错误响应：
```json
{ "detail": "中文错误描述" }
```

| HTTP | 场景 |
|------|------|
| 400 | URL 解析失败 |
| 404 | 仓库不存在或为私有 |
| 429 | GitHub 限频 |
| 502 | GitHub 上游异常 |
| 500 | 内部异常 |

## 5. 评分维度定义（喂给 AI 的口径）

| 维度            | 主要参考输入                                      |
|----------------|--------------------------------------------------|
| popularity      | stars / forks / watchers                         |
| activity        | days_since_push / 近 12 周 commit 总数            |
| community       | contributors 数量 / 头部贡献者占比               |
| maintainability | open_issues 比例 / license 是否存在 / archived    |
| documentation   | description 是否存在 / homepage / topics 数量    |

整体 `score` 由 AI 综合裁定，不强制等于五维平均。

## 6. 非功能性需求

- **缓存**：同一 `owner/repo` 10 分钟内复用结果，进程内 TTL 字典即可。
- **超时**：单次 GitHub 请求 8s，AI 请求 15s，超时即返回降级数据。
- **可观测**：每个外部调用打印 `[client] GET ... -> status (Xms)`。
- **零密钥可跑**：未配置 token 时仍能完成 AC-1（仅限频更紧）。

## 7. Out of Scope (本期)

- GitHub Enterprise / 私有仓库
- 历史快照对比 / 趋势数据库
- 用户登录、收藏夹
- 移动端适配（桌面优先）
