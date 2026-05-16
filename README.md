# GitHub 仓库体检 · Repo Health Check

> 输入任意公开 GitHub 仓库 URL，30 秒内拿到客观指标 + AI 评分 + 风险提示。
>
> 技术栈：**FastAPI · httpx · Pydantic · Vue 3 (CDN) · Element Plus · Chart.js · MiniMax-M2 (via Anthropic-compatible API)**
>
> 开发方法论：**SDD (Spec-Driven Development) + TDD (Test-Driven Development)**

---

## ✨ 功能一览

| 模块 | 说明 |
|---|---|
| **核心指标** | Stars / Forks / Watchers / Open Issues / 仓库年龄 / 距上次 push 天数 |
| **语言分布** | 调 `GET /repos/{o}/{r}/languages`，按字节数饼图 |
| **提交活动** | 调 `stats/commit_activity` 渲染近 52 周折线图 |
| **Top 贡献者** | 横向 bar 图展示前 10 名 |
| **🤖 AI 评分（加分项）** | MiniMax-M2 综合裁定 0-100 总分 + 5 维度雷达 + 一句话总评 + 优势 / 风险三件套 |
| **容错** | URL 不合法 / 仓库不存在 / GitHub 限频 / AI 不可用 — 全部按 spec §AC 中文降级 |

界面截图（输入 → 报告）：将 `web/index.html` 用浏览器访问 `http://127.0.0.1:8000/` 即可看到。

---

## 🏗 开发方法论

### SDD — 先有规格，再有代码

所有 API 字段、错误码、URL 解析规则、降级策略都先在 **[`specs/001-repo-health.md`](./specs/001-repo-health.md)** 里写死，作为 single source of truth。代码只是规格的实现。

```
specs/001-repo-health.md
  ├── §1 用户故事 (As / I want / So that)
  ├── §2 验收标准 AC-1 ~ AC-5 (Given / When / Then)
  ├── §3 URL 解析规则（穷举支持/拒绝列表）
  ├── §4 API 契约（请求 + 完整响应 schema + 错误码表）
  ├── §5 评分维度定义（喂给 AI 的口径）
  ├── §6 非功能性需求（缓存 / 超时 / 可观测）
  └── §7 Out of Scope
```

### TDD — 红 → 绿 → 重构

测试文件与 spec AC 一一对应：

| AC 编号 | 测试文件 / 函数 |
|---|---|
| AC-1 合法 URL 完整报告 | `tests/test_api.py::test_ac1_analyze_full_flow` |
| AC-2 非法 URL 400 | `tests/test_url_parser.py::test_ac2_invalid_urls_raise` + `test_api.py::test_ac2_invalid_url_returns_400` |
| AC-3 仓库不存在 404 | `tests/test_github_client.py::test_ac3_not_found_raises` + `test_api.py::test_ac3_repo_not_found_returns_404` |
| AC-4 AI 不可用降级 | `tests/test_api.py::test_ac1_analyze_full_flow` 中断言 `ai.available is False` |
| AC-5 限频 429 | `tests/test_github_client.py::test_ac5_rate_limit_raises` + `test_api.py::test_ac5_rate_limit_returns_429` |
| §6 202 重试 | `tests/test_github_client.py::test_commit_activity_202_retries_once` |
| §6 TTL 缓存 | `tests/test_github_client.py::test_cache_hit_avoids_second_request` |

所有外部 HTTP (GitHub / Anthropic) 均通过 **respx** 桩化，测试完全离线、可重入。

#### 当前测试结果

```
$ pytest --cov=app
................................                          [100%]
32 passed in 5.22s

Coverage:
app\__init__.py               0      0  100%
app\ai_scorer.py             49     27   45%   (AI 路径主体仅在集成场景跑)
app\analyzer.py              38      2   95%
app\config.py                18      0  100%
app\github_client.py         84      4   95%
app\routers\__init__.py       0      0  100%
app\routers\analyze.py       33      2   94%
app\schemas.py                4      0  100%
app\url_parser.py            19      2   89%
TOTAL                       245     37   85%
```

---

## 🚀 运行方式

### 0. 前置要求

- Python **3.10+**（仓库内验证用 3.11；3.9 会被 pyproject 拒绝）
- Windows / macOS / Linux 均可

### 1. 克隆 + 装依赖

```bash
git clone <this-repo>
cd github-scan

# 创建虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# 安装依赖 (含 dev 依赖以便跑测试)
# 中国大陆推荐加镜像: -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -e ".[dev]"
```

### 2. 配置 `.env`（**可选**）

```bash
cp .env.example .env
```

打开 `.env` 填两项（**都不是必需的**，留空也能跑核心功能）：

| 变量 | 缺省值 | 不填的后果 |
|---|---|---|
| `GITHUB_TOKEN` | 空 | 匿名访问 GitHub，限频 60 次/小时；高频测试会触发 AC-5 中文降级提示 |
| `ANTHROPIC_API_KEY` | 空 | AI 评分卡片自动隐藏，前端显示 *"AI 评分不可用，已自动降级"*，其余指标完整可用 |
| `ANTHROPIC_BASE_URL` | `https://api.minimaxi.com/anthropic` | 默认走 MiniMax-M2 的 Anthropic 兼容网关；可改 Anthropic 官方 / 其它兼容网关 |
| `AI_MODEL` | `MiniMax-M2` | 模型名 |
| `CACHE_TTL_SECONDS` | `600` | 同一仓库 10 分钟内复用结果，避免反复消耗 GitHub 配额 |

> **MiniMax-M2 是推理模型**，响应中第一个 block 是 `ThinkingBlock`，第二个才是 `TextBlock`。`app/ai_scorer.py` 已设置 `max_tokens=4096` 给 thinking 留出空间，并通过 `getattr(b,"type","")=="text"` 精确提取最终 JSON。

### 3. 跑测试（TDD 验证）

```bash
pytest -v                       # 32 passed
pytest --cov=app                # 覆盖率报告
```

### 4. 启动应用

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

浏览器打开 **http://127.0.0.1:8000/** ，输入：

- `fastapi/fastapi`
- `https://github.com/vuejs/vue`
- `git@github.com:torvalds/linux.git`

任意一种格式都被识别。

### 5. 直接调 API（curl）

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/fastapi/fastapi"}'
```

OpenAPI 文档：http://127.0.0.1:8000/docs

---

## 🗂 目录结构

```
github-scan/
├── README.md                      ← 本文件（SDD/TDD + 运行说明）
├── specs/
│   └── 001-repo-health.md         ← 规格文档（spec-first）
├── prompts/
│   └── README.md                  ← Vibe Coding 提示词存档（加分项 #4）
├── pyproject.toml                 ← 依赖 + pytest + coverage 配置
├── .env.example                   ← 环境变量模板
├── app/
│   ├── main.py                    ← FastAPI 入口 + 静态托管 web/
│   ├── config.py                  ← dotenv(override=True) 加载
│   ├── url_parser.py              ← spec §3 URL 形式归一化
│   ├── github_client.py           ← httpx + TTL 缓存 + 202 重试
│   ├── analyzer.py                ← 指标聚合（纯函数）
│   ├── ai_scorer.py               ← MiniMax-M2 via anthropic SDK
│   ├── schemas.py                 ← Pydantic
│   └── routers/analyze.py         ← POST /api/analyze
├── tests/                         ← 32 个 pytest 用例 (respx 桩)
│   ├── conftest.py
│   ├── test_url_parser.py
│   ├── test_github_client.py
│   ├── test_analyzer.py
│   └── test_api.py
└── web/                           ← 零构建前端，FastAPI 直接托管
    ├── index.html                 ← Vue 3 CDN + Element Plus
    ├── app.js                     ← fetch + Chart.js 渲染
    └── style.css
```

---

## 🤖 AI 评分提示词

详见 [`prompts/README.md`](./prompts/README.md)。核心 system prompt 摘要：

```
你是开源项目健康度评估专家。基于指标 JSON 给出 0-100 整体分 +
5 维度子分（popularity/activity/community/maintainability/documentation）+
中文一句话总评 + 3 条优势 + 3 条风险。
严格返回 JSON，不要 markdown 包裹。
```

实测对 fastapi/fastapi（70000 stars / 1 day since push / 仅 2 贡献者样本数据）的输出：

```json
{
  "score": 75,
  "dimensions": {
    "popularity": 95, "activity": 95, "community": 25,
    "maintainability": 80, "documentation": 85
  },
  "comment": "流行度高且活跃，但严重依赖单一维护者，社区力量薄弱",
  "highlights": ["7万 stars 极高人气", "昨日更新", "官方文档完善"],
  "risks":      ["仅 2 位贡献者", "97% 代码由一人贡献", "社区参与度低"]
}
```

---

## 🛡 容错矩阵（与 spec §4 错误码表对应）

| 触发条件 | HTTP | 前端表现 |
|---|---|---|
| URL 解析失败 | 400 | ElMessage 红色提示具体原因 |
| 仓库不存在 / 私有 | 404 | "仓库不存在或为私有" |
| GitHub 限频 | 429 | "GitHub 限频，请配置 GITHUB_TOKEN 后重试" |
| GitHub 5xx | 502 | "GitHub 上游异常" |
| AI key 缺失 / 调用失败 / JSON 解析失败 | 200（业务正常） | AI 卡片自动隐藏，顶部 info 条说明降级原因 |

---

## 📌 已知约束 / Out of Scope

- 仅支持 **公开仓库**（私有/企业 GHE 域名不在本期范围）
- 不做历史趋势数据库（每次请求都是当下快照）
- 桌面端优先，移动端仅做了基本响应式（kpi 行 2 列、图表纵向堆叠）

---

## 🧰 一行起跑（已装好依赖时）

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
# 然后浏览器打开 http://127.0.0.1:8000/
```
