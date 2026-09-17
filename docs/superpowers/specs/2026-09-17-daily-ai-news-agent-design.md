# 每日 AI 新闻助手 Agent — 设计规格

- 日期：2026-09-17
- 状态：设计已批准，待实现计划
- 技术栈：Python（FastAPI 后端）+ 独立前端目录（前后端分离，同仓）
- LLM：用户提供的 OpenAI 兼容 `API key` + `API 路径`（通过 `.env` 注入）
- 核心约束：**工具调用顺序由 LLM 决定**（ReAct / function-calling 循环），不得硬编码线性流程

## 1. 目标

实现一个 Agent，每天自动为用户整理一份 AI 新闻简报。用户可按自己的偏好
（关注话题、关键词）订阅，Agent 据此筛选内容，生成简报并可在前端查看历史。

## 2. 范围（初版）

包含：
- Agent 核心：function-calling 驱动的 ReAct 循环，LLM 自主决定工具顺序、次数、何时停止。
- 工具集（≥5，签名自定）：`list_dir`、`read_file`、`search_content`、`write_file`、`bash`，另加 Agent 专属工具。
- 新闻数据源：RSS 抓取（主力）+ Aas-ee/open-webSearch（免 key、免注册、本地运行的联网搜索 MCP server，补充"让模型自己搜索"）+ LLM 自身归纳。
- 前端：填身份、设置订阅偏好（话题、关键词）、查看历史简报、手动"立即生成"。
- 定时任务：后端内置 scheduler 每日定点运行，与手动触发共用同一 Agent 入口。
- 历史简报：存于后端（数据库或文件系统），前端按日期查看全文。

不含（YAGNI，后续再议）：
- 外部推送渠道（企业微信/飞书/Slack/邮件）。
- 多用户鉴权与权限体系（初版单用户/简单身份字段即可）。
- 简报的美观排版与可视化。

## 3. 项目结构（前后端分离，同仓）

```
每日AI新闻助手/
├─ backend/               # Python + FastAPI
│  ├─ app/
│  │  ├─ main.py          # 应用入口、CORS、启动时挂定时器
│  │  ├─ config.py        # 读取 .env：LLM key/base_url/模型、RSS 源、定时点、搜索 key
│  │  ├─ routes/          # 身份、订阅偏好、手动触发、历史简报
│  │  ├─ agent/
│  │  │  ├─ loop.py       # ReAct / function-calling 核心循环
│  │  │  ├─ tools/        # 各工具实现（list_dir/read_file/search_content/write_file/bash）
│  │  │  └─ llm.py        # OpenAI 兼容客户端封装（tool call 解析）
│  │  ├─ sources/
│  │  │  ├─ rss.py        # RSS 抓取与解析 → 落地为本地内容文件
│  │  │  └─ websearch.py  # 独立搜索接口（预留，key 可选）
│  │  ├─ scheduler.py     # APScheduler 每日定时任务
│  │  └─ storage.py       # 简报与元数据存取（SQLite 或 JSON/文件）
│  ├─ tests/
│  └─ requirements.txt
├─ frontend/             # 独立目录，纯静态页（不引入构建工具）
│  ├─ index.html
│  ├─ app.js
│  └─ style.css
├─ .env.example
└─ README.md
```

说明：前端为纯静态（fetch 调后端 API），开发期用 CORS 或简单代理对接，不做
独立构建管线（初版轻）。"前后端分离"指目录与职责分离，不引入额外构建工具。

环境依赖：Python（后端）+ Node/npm（本机，供 open-webSearch 的 MCP 搜索，已确认 v24 可用）。

## 4. 组件设计

### 4.1 Agent 核心循环（`agent/loop.py`）
- 输入：订阅偏好（话题列表、关键词列表）+ 任务提示"生成今日 AI 新闻简报"。
- 将工具 schema 注册给 LLM，进入 function-calling 循环：
  1. 调 LLM（messages + tools）；
  2. 若返回 `tool_calls`：按 LLM 给出的顺序与参数执行对应工具，把结果回写 messages；
  3. 若返回 `finish` 或纯文本：结束，产出简报；
  4. 记录每步（工具名、参数、摘要结果）到审计日志。
- 兜底：最大步数（如 20 步）与总超时；超限时安全终止并记录原因。
- **关键点：哪一步调什么工具、调几次，全部由 LLM 决定；代码只负责执行与回传。**

典型轨迹（示例，非强制）：
`list_dir(抓取目录)` → `search_content(关键词, 抓取目录)` → `read_file(某篇详情)`
→ `write_file(简报路径)` → `finish`。

### 4.2 工具集（`agent/tools/`）
按题目签名，均受路径与权限约束：
- `list_dir(path)`：列目录；`path` 限定在项目沙箱根内。
- `read_file(path)`：读文件；沙箱根内。
- `search_content(keyword, dir)`：在 `dir` 内按关键词全文检索，返回命中文件与行。
- `write_file(path, content)`：写文件；沙箱根内（简报输出、临时内容都落这里）。
- `bash(command)`：执行 shell；**白名单/沙箱限制**（仅允许预设安全命令，如 `grep`/`cat`/`ls`
  及只读操作，禁止写系统目录与危险命令）。初版用命令前缀白名单 + 子进程隔离。
- Agent 专属工具（额外）：`search_rss(topic)`（抓取并落地 RSS 内容）、`web_search(query)`
  （经 `mcp` SDK 调 open-webSearch 的 `search` 工具，免 key；失败时返回降级提示）、
  `finish(text)`（结束并输出最终简报）。

沙箱根：`backend/data/sandbox/`（抓取内容、生成简报都写这里），所有文件工具路径相对它解析并校验。

### 4.3 LLM 客户端（`agent/llm.py`）
- OpenAI 兼容协议（用户 `base_url` + `api_key` + 模型名），支持 tool calls。
- 用 `openai` Python SDK 或裸 HTTP；解析 `tool_calls` 与 usage。
- 从 `.env` 注入：`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。

### 4.4 数据源（`sources/`）
- `rss.py`：维护一份 RSS 源清单（Hacker News、ArXiv、主流 AI 博客等，可配置于 `.env`/配置），
  定时抓取并解析为结构化条目，落地为沙箱内文本文件供 `read_file`/`search_content` 使用。
- `websearch.py`：用 Python 官方 `mcp` 客户端 SDK 接 open-webSearch（本地免 key 搜索 MCP server，
  npm 包 `open-websearch`）。两种连接方式（初版选 stdio，可扩展）：
  - **stdio**：`stdio_client` 起子进程 `npx -y open-websearch@latest`，env 设 `MODE=stdio`、
    `DEFAULT_SEARCH_ENGINE=duckduckgo`；**Windows 用 `cmd /c npx -y open-websearch@latest` 并在
    env 加 `SYSTEMROOT=C:/Windows`**（npx 实为 npx.cmd）。
  - **http**（可选扩展）：起 `open-websearch serve` 本地 daemon 后，用 `streamablehttp_client`
    连 `http://127.0.0.1:3000/mcp`。
  连上后 `list_tools()` 取 `search`、`fetchWebContent`，`call_tool("search", {"query": q, "limit": n})`
  调用。它免 key、免注册、本地运行（需本机 Node/npm，已确认有 v24）。
  搜索调用失败时 `web_search` 工具返回"搜索不可用，已降级为仅 RSS"提示，Agent 自动改用 RSS/归纳，
  不中断整体流程。主力数据源：RSS + 此搜索补充 + LLM 归纳。

### 4.5 前端（`frontend/`）
- 表单：身份信息（昵称/标识，简单字段）+ 订阅偏好（关注话题、关键词，逗号分隔）。
- 操作：保存偏好、"立即生成"按钮（POST 手动触发）。
- 展示：历史简报列表（按日期），点击展开全文。
- 纯静态 fetch 调后端 API；开发期 CORS。不追求美观。

### 4.6 存储（`storage.py`）
- 简报 + 元数据（日期、订阅快照、生成时间、审计摘要）存 SQLite（初版够用，零外部依赖）。
- 简报全文亦可落沙箱文件，SQLite 记路径与索引。

### 4.7 定时任务（`scheduler.py`）
- APScheduler：每日定点（可配置 `DAILY_RUN_HOUR`/`MINUTE`）跑一次 Agent。
- 与手动"立即生成"共用 `run_agent_once()` 入口，避免重复逻辑。
- 启动时若今日已生成则跳过（幂等，按日期去重）。

## 5. 数据流

定时/手动触发 → `run_agent_once(订阅偏好)` →（先按需 `search_rss` 抓取落地）→
LLM ReAct 循环调工具（list/search/read/write/bash/web_search）→ `write_file` 简报 +
`finish` → 存储（SQLite 索引 + 沙箱文件）→ 前端历史页可查。

## 6. 配置（`.env` / `.env.example`）
- `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`
- `RSS_FEEDS`（逗号分隔 URL 或指向配置文件）
- 无搜索相关 key（DuckDuckGo 免 key，零成本、无需注册）
- `DAILY_RUN_HOUR`、`DAILY_RUN_MINUTE`
- 沙箱根路径

## 7. 错误处理
- 工具执行异常：捕获并作为工具结果回传给 LLM（不中断循环），让 LLM 自行决定下一步。
- LLM 调用失败/超时：重试有限次数，仍失败则本次生成标记失败并记录原因。
- 沙箱越界路径：工具层直接拒绝并返回错误信息。
- 抓取失败：记录、跳过该源，不影响整体（可用已有内容生成）。

## 8. 测试
- 工具单测：list/read/search/write 的读写与沙箱校验；`bash` 白名单放行/拒绝。
- Agent 循环 mock 单测：给定 LLM 工具轨迹（固定 tool_calls 序列），验证按序执行与 `finish` 停止、步数上限。
- 端到端：mock RSS/搜索 + mock LLM，跑通一次"生成简报→落盘→可查"。

## 9. 交付（初版）
- 后端可运行（`uvicorn` 起 FastAPI，含定时器）。
- 前端可打开使用（身份/偏好/历史/立即生成）。
- 通过上述测试；README 说明如何填 `.env` 与运行。
