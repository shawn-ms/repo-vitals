# Vibe Coding Prompts Log

记录本项目使用 AI Coding 工具（Claude Code + MiniMax-M2）的关键提示词，便于复盘。

## 阶段 0 — 需求澄清

**用户原始需求**（节选）：
> 在 48 小时内完成 Github 仓库"体检"工具……用 fastapi，readme 上体现 sdd 和 tdd。这个获取 github 应该有接口吧，还是实时 fetch?

**Claude 回应要点**：
1. GitHub 官方 REST API 完全够用，匿名 60/h，带 PAT 5000/h，推荐实时 fetch + 10 分钟 TTL 缓存。
2. 提出 SDD（先写 `specs/001-*.md`） + TDD（先写 `tests/`） 双流程。
3. 前端建议 Vue 3 CDN + Element Plus + Chart.js，零构建。

**用户回应**：
1. AI 评分使用 MiniMax-M2 via Anthropic-compatible endpoint。
2. 同意记录 prompts。
3. 询问前端是否要 Vue。

## 阶段 1 — 规格驱动 (SDD)

提示词模板：

```
基于以下需求写 specs/001-*.md，包含：
- 用户故事 (As/I want/So that)
- 验收标准 (Given/When/Then)
- API 契约（请求 + 完整响应 schema + 错误码表）
- 非功能性需求（缓存、超时、降级）
- Out of Scope

需求：<贴用户需求>
约束：必须能在 48h 内完成 + 无 GITHUB_TOKEN 也能跑通核心路径。
```

## 阶段 2 — 测试先行 (TDD)

提示词模板：

```
基于 specs/001-repo-health.md 的 AC-1 ~ AC-5，为以下模块写 pytest 测试。
要求：
- 外部 HTTP 调用全部用 respx / monkeypatch 桩，不打真实网络。
- 每个 AC 至少一个测试用例，函数名以 test_ac1_xxx 形式映射。
- 失败时 assert message 中文，便于排查。

模块：app/github_client.py
```

## 阶段 3 — 实现

提示词模板：

```
让 tests/test_github_client.py 全部变绿，最少代码原则。
约束：
- httpx.AsyncClient，超时 8s
- 202 Accepted 自动重试一次（commit_activity 接口特性）
- 进程内 TTL 缓存装饰器，key=(method, url)，ttl=600s
```

## 阶段 4 — AI 评分

调 MiniMax-M2 的关键提示（system prompt 见 `app/ai_scorer.py`）：

```
你是开源项目健康度评估专家。基于指标 JSON 给出：
- score: 0-100 整体分
- dimensions: 5 维度子分（popularity/activity/community/maintainability/documentation）
- comment: ≤ 50 字中文一句话总评
- highlights: 3 条优势
- risks: 3 条风险
严格返回 JSON，禁止 markdown 包裹。
```

## 阶段 5 — 前端 Vibe

```
单文件 web/index.html，基于 Vue 3 CDN + Element Plus CDN + Chart.js CDN：
- 顶部输入框 + 按钮（按 Enter 也触发）
- KPI 卡片行（stars/forks/watchers/open_issues）
- 语言饼图 + 提交活动折线 + 贡献者横条 + AI 雷达
- 错误用 ElMessage，loading 用骨架屏
- 不引入 npm/构建工具，FastAPI 静态托管即可
```

## 教训 & 复盘

- **先写 spec 真的能省后期返工**：URL 解析规则在 spec 里穷举后，测试用例自然就出来了。
- **GitHub `stats/commit_activity` 202 重试**这种细节，是写 spec §6 时主动加进去的，不靠后期 debug。
- **AI 降级路径要在 spec AC-4 写死**：否则联调时 key 没生效会让整个 demo 崩。

### 实战踩到的三个坑（值得记下来）

1. **MiniMax-M2 是推理模型**，响应第一个 content block 是 `ThinkingBlock` 而不是 `TextBlock`。最初设 `max_tokens=1024` 时 thinking 直接吃光配额，`stop_reason=max_tokens` 没产出 JSON。
   修复：`max_tokens=4096` + 用 `getattr(b,"type","")=="text"` 过滤。

2. **`load_dotenv()` 默认 `override=False`**，宿主 shell 里残留的 `ANTHROPIC_BASE_URL`（Claude Code 自己的网关）会盖掉项目 `.env` 中的 MiniMax 地址，造成 401 假象。
   修复：`load_dotenv(override=True)` —— 把项目 `.env` 视为唯一可信源。

3. **`pyproject.toml` 声明 `requires-python = ">=3.10"` 但 venv 用了 3.9** 时，pip 会陷入 30+ 分钟的版本回溯，输出还被 `| tail` 缓冲完全看不到进度。
   修复：建 venv 显式 `py -3.11 -m venv .venv`；pip 命令避免 `| tail`，让进度实时可见。
