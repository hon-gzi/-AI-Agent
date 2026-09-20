# 每日 AI 新闻助手 Agent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.1xx-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Agent-ReAct%20%2F%20function-calling-blue" alt="Agent">
  <img src="https://img.shields.io/badge/MCP-open-websearch-purple" alt="MCP">
</p>

一个可订阅、可生成、可回看的**每日 AI 新闻简报 Agent**。LLM 通过 function-calling（ReAct）自主决定调用哪些工具、调用几次、何时停止，据此从订阅话题中抓取并归纳当日 AI 新闻，产出简报供用户浏览。

> 核心：工具调用顺序**由 LLM 决定**，不是写死的线性流程。

## ✨ 功能

- **Agent 驱动**：`LLMClient` 的 function-calling 循环让模型自行规划轨迹（RSS 抓取 / 联网搜索 / 读沙箱 / 写简报 / 结束），哪一步调什么工具、几次、何时 `finish` 全由 LLM 定。
- **多数据源**：RSS（内置源 + 可配置）为主；open-webSearch MCP 联网搜索（免 key、免注册、本地 `npx` 起服务）为辅，出站受限时自动降级为仅 RSS；LLM 归纳。
- **可订阅**：前端设关注话题（topics）与关键词（keywords），生成时注入为偏好。
- **手动 + 定时**：前端「立即生成」或 APScheduler 每日定点，二者共用同一 Agent 入口 `run_agent_once`。
- **可回看**：历史简报按日期落盘沙箱，前端随时回看全文。
- **安全边界**：沙箱路径越界拦截、bash 白名单 + 注入拦截、date 路径穿越防护、真实 LLM key 仅存 `.env`。

## 🧰 工具集（8 个，签名自定）

| 工具 | 说明 |
|---|---|
| `list_dir(path)` | 列出沙箱目录内容 |
| `read_file(path)` | 读取沙箱内文件 |
| `search_content(keyword, dir)` | 沙箱内按关键词全文检索 |
| `write_file(path, content)` | 写入沙箱内文件（简报） |
| `bash(command)` | 沙箱 cwd 内执行白名单只读命令（拦截 shell 元字符 / 路径逃逸） |
| `search_rss(topic)` | 抓取并落地 RSS 新闻到沙箱 |
| `web_search(query)` | open-webSearch MCP 联网搜索（免 key，失败降级） |
| `finish(text)` | 结束并输出最终简报全文 |

> 满足图片规格「至少 5 个基础工具」，并额外提供搜索类工具让模型"自己搜索"。

## 🗂 目录结构

```
.
├─ backend/
│  ├─ app/
│  │  ├─ main.py        # FastAPI 工厂 + 启动入口 + 挂定时任务
│  │  ├─ config.py      # 读 .env（LLM / RSS / 定时 / 沙箱根）
│  │  ├─ scheduler.py   # APScheduler 每日任务（与手动触发共用 run_agent_once）
│  │  ├─ agent/
│  │  │  ├─ llm.py      # OpenAI 兼容 LLM 客户端 + function-calling 循环
│  │  │  ├─ loop.py     # ReAct 入口 run_agent_once（生成并落盘简报）
│  │  │  ├─ sandbox.py  # 沙箱越界校验 + bash 白名单 + 路径逃逸拦截
│  │  │  └─ tools/      # 8 个工具 + 注册表 + OpenAI schema
│  │  ├─ sources/
│  │  │  ├─ rss.py      # RSS 抓取解析 → 落地沙箱（httpx 带超时）
│  │  │  └─ websearch.py# open-webSearch MCP stdio（免 key）
│  │  └─ routes/api.py   # 偏好 / 触发 / 历史简报 路由
│  ├─ data/sandbox/      # 抓取内容 + 生成简报 落盘（gitignore）
│  └─ tests/            # 全量单测（68 通过，全程 mock 不触网）
├─ frontend/            # 纯静态页（index.html + app.js + style.css）
├─ docs/superpowers/     # 设计规格 + 实现计划
├─ .env.example          # 配置模板（复制为 .env）
└─ .env                  # 真实配置（gitignore，勿提交）
```

## 🚀 快速开始

### 1. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 LLM（OpenAI 兼容协议）：

```ini
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://your-llm-endpoint/v1
LLM_MODEL=your-model-name
```

可选：

| 变量 | 说明 |
|---|---|
| `RSS_FEEDS` | 逗号分隔的 RSS URL；留空用内置默认 AI 新闻源清单 |
| `DAILY_RUN_HOUR` / `DAILY_RUN_MINUTE` | 每日定时触发点（默认 08:00，系统本地时区） |
| `SANDBOX_ROOT` | 沙箱根（默认 `backend/data/sandbox`） |
| `WEBSEARCH_ENGINE` | 联网搜索引擎（默认 `duckduckgo`） |

> 联网搜索（open-webSearch）通过本地 `npx` 起 MCP server，需安装 Node/npm；出站受限时 `web_search` 会**按设计降级为仅 RSS**，不中断生成。

### 2. 运行后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows；Linux/mac 用 .venv/bin/pip
.venv/Scripts/python -m app.main
```

`python -m app.main` 会 `create_app` + **start 每日定时任务** + uvicorn 起在 `0.0.0.0:8000`。

> 若只起后端、不跑定时任务：
> ```bash
> .venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
> ```

### 3. 打开前端

`frontend/` 为纯静态页。浏览器打开 `frontend/index.html`（CORS 已 `allow_origins=["*"]`，可跨源调 `http://127.0.0.1:8000`），或：

```bash
cd frontend
python -m http.server 8080
# 浏览器开 http://127.0.0.1:8080
```

前端功能区：**订阅偏好**（保存 topics/keywords）→ **立即生成**（`POST /api/trigger`）→ **历史简报**（按日期回看全文）。

## 🧪 测试

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

全量单测覆盖：沙箱 / 工具 / LLM 循环 / ReAct 入口 / RSS / 联网搜索 / 定时 / 路由。测试全程 mock LLM 与网络，**不触网、不读真实 `.env`**。

## 🔄 Agent 循环（架构）

`run_agent_once`（`app/agent/loop.py`）是手动触发与定时任务**共用**的唯一 Agent 入口：

```
组装系统提示(订阅偏好 + 日期 + 工具说明)
   │
   ▼
LLMClient.run()  ◄─────────────────┐
   │ function-calling 循环          │ tool 结果回写
   │ 哪步调哪个工具/几次/何时停由 LLM 定 │
   ├─ search_rss(话题) ──► 沙箱 rss/ 落地
   ├─ list_dir / search_content / read_file ──► 挑取条目
   ├─ web_search(query) ──► 联网结果(或降级)
   ├─ write_file(briefings/<date>.md) ──► 沙箱 briefings/
   └─ finish(全文) ──► 结束
   │
   ▼
落盘 briefings/<date>.md(经沙箱校验)
   │
   ▼
GET /api/briefings、GET /api/briefings/<date>、前端历史区 回看
```

典型轨迹（非强制，LLM 自决）：`search_rss` → `list_dir`/`search_content`/`read_file` → `write_file` → `finish`。

## 🔒 安全

- **沙箱**：所有文件工具路径相对 `backend/data/sandbox` 解析，`../` 越界即拒绝。
- **bash 白名单**：仅只读命令（grep/cat/ls/…），且拒绝 shell 元字符（`;` `|` `&` 换行等）与路径逃逸（`..`、绝对路径、`$` 变量扩展），防 LLM 提示注入下越权。
- **date 注入**：`GET /api/briefings/{date}` 强制 `YYYY-MM-DD`，拒绝 `../` 等穿越；列表 API 只认规范命名的简报文件。
- **密钥**：真实 LLM key 只存 `.env`（gitignore），不进任何被 commit 的文件。

## 📄 License

MIT（可自行替换）
