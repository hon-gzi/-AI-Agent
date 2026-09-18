# 每日 AI 新闻助手

一个可订阅、可生成、可回看的**每日 AI 新闻简报生成器**。LLM 通过 function-calling（ReAct）自主决定调用哪些工具、调用几次、何时停止，据此从订阅话题中抓取并归纳当日 AI 新闻，产出简报供用户浏览。

核心特征：

- **Agent 驱动**：不写死线性流程，LLM 按订阅偏好自行规划工具调用顺序（RSS 抓取 / 联网搜索 / 读沙箱 / 写简报 / 结束）。
- **多数据源**：RSS（内置源 + 自定义）为主，open-webSearch MCP 联网搜索为辅（免 key、免注册，本地 npx 起服务），LLM 归纳。
- **可订阅**：前端设置关注话题（topics）与关键词（keywords），生成时作为偏好注入。
- **手动 + 定时**：前端可“立即生成”，APScheduler 每日定点自动生成，二者共用同一 Agent 入口。
- **可回看**：历史简报按日期保存于沙箱，前端随时回看全文。

## 目录结构

```
.
├─ backend/            # Python + FastAPI
│  ├─ app/
│  │  ├─ main.py        # FastAPI 应用工厂 + 启动入口 + 挂载定时任务
│  │  ├─ config.py      # 读取 .env（LLM / RSS / 定时 / 沙箱根）
│  │  ├─ scheduler.py   # APScheduler 每日任务（与手动触发共用 run_agent_once）
│  │  ├─ agent/
│  │  │  ├─ llm.py      # OpenAI 兼容 LLM 客户端 + function-calling 循环
│  │  │  ├─ loop.py     # ReAct 入口 run_agent_once（生成简报并落盘）
│  │  │  ├─ sandbox.py  # 沙箱根解析 + 越界校验 + bash 白名单
│  │  │  ├─ prompts.py  # 系统提示与工具说明
│  │  │  └─ tools/      # 8 个工具：list_dir/read_file/search_content/write_file/bash/finish/search_rss/web_search
│  │  ├─ sources/
│  │  │  ├─ rss.py      # RSS 抓取解析 → 落地沙箱
│  │  │  └─ websearch.py# open-webSearch MCP stdio 联网搜索（免 key）
│  │  └─ routes/api.py  # 身份/偏好/手动触发/历史简报 路由
│  ├─ data/sandbox/     # 抓取内容 + 生成简报 落盘目录（gitignore）
│  ├─ tests/
│  └─ requirements.txt
├─ frontend/           # 纯静态页（index.html + app.js + style.css）
├─ docs/superpowers/   # 设计规格 + 实现计划
├─ .env.example        # 配置模板（复制为 .env）
└─ .env                # 真实配置（gitignore，勿提交）
```

## 配置

1. 复制 `.env.example` 为 `.env`（仓库根目录）：
   ```bash
   cp .env.example .env
   ```
2. 填入你的 LLM 信息（OpenAI 兼容协议）：
   - `LLM_API_KEY` — 你的 API key（**真实密钥，勿提交**）
   - `LLM_BASE_URL` — 指向 `/v1` 结尾的 OpenAI 兼容端点
   - `LLM_MODEL` — 模型名（如 `agnes-3.0-flash`）
3. 可选：
   - `RSS_FEEDS` — 逗号分隔的 RSS URL；留空用内置默认 AI 新闻源清单。
   - `DAILY_RUN_HOUR` / `DAILY_RUN_MINUTE` — 每日定时触发点（默认 08:00，系统本地时区）。
   - `SANDBOX_ROOT` — 沙箱根（默认 `backend/data/sandbox`）。
   - `WEBSEARCH_ENGINE` — 联网搜索引擎（默认 `duckduckgo`）。

> 联网搜索（open-webSearch）通过本地 `npx -y open-websearch@latest` 起 MCP server，需本机安装 Node/npm。若出站网络受限，`web_search` 会**按设计降级为仅 RSS**，不中断生成。

## 运行

### 后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows；Linux/mac 用 .venv/bin/pip
.venv/Scripts/python -m app.main
```

`python -m app.main` 会 `create_app` + **start 每日定时任务**（按 `.env` 的 `DAILY_RUN_*`）+ 以 uvicorn 起在 `0.0.0.0:8000`。

> 若只想起后端（**不跑定时任务**，例如手动控制触发节奏）：
> ```bash
> .venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
> ```
> `uvicorn app.main:app` 走模块级 `app`，**不会**自动 `start_scheduler`——定时任务需另行 start。


### 前端

`frontend/` 为纯静态页。任选其一：

- 直接双击/浏览器打开 `frontend/index.html`（CORS 已 `allow_origins=["*"]`，可跨源调 `http://127.0.0.1:8000`）；或
- 用静态服务器起，更稳：
  ```bash
  cd frontend
  python -m http.server 8080
  # 浏览器打开 http://127.0.0.1:8080/index.html
  ```

前端功能区：**订阅偏好**（保存 topics/keywords）→ **立即生成**（调 `POST /api/trigger`）→ **历史简报**（按日期回看全文）。

## 测试

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

全量单测覆盖：沙箱/工具/LLM 循环/ReAct 入口/RSS/联网搜索/定时/路由。测试全程 mock LLM 与网络，不触网、不读真实 `.env`。

## 安全边界

- **沙箱**：所有文件工具路径相对 `backend/data/sandbox` 解析，`../` 越界即拒绝。
- **bash 白名单**：仅允许只读命令（grep/cat/ls/…），且拒绝 shell 元字符（`;` `|` `&` 换行等）与路径逃逸（`..`、绝对路径、`$` 变量扩展），防止 LLM 提示注入下越权。
- **date 注入**：`GET /api/briefings/{date}` 强制 `YYYY-MM-DD` 格式，拒绝 `../` 等路径穿越。
- **密钥**：真实 LLM key 只存于 `.env`（已 gitignore），绝不进入任何被 commit 的文件或 `.env.example`。

## 架构说明（Agent 循环）

`run_agent_once`（`app/agent/loop.py`）是手动触发与定时任务**共用**的唯一 Agent 入口：

1. 按订阅偏好 + 日期组装系统提示；
2. 驱动 `LLMClient` 的 function-calling 循环——**哪一步调什么工具、调几次、何时 `finish`，全部由 LLM 决定**（代码只负责把 LLM 的 `tool_calls` 分发给对应 handler、把结果回写消息、直到 LLM 不再调工具或调 `finish`）；
3. 循环结束后，若 LLM 用 `write_file` 已产出简报则信任之，否则把 `finish` 的 `final_text` 落盘到 `briefings/<date>.md`（经沙箱校验）；
4. 返回 `{"status": "ok"|"no_output", "date", "briefing_path", "content"}`。

典型轨迹（非强制，LLM 自决）：
`search_rss(话题)` → `list_dir`/`search_content`/`read_file`（挑取条目）→ `write_file(briefings/<date>.md)` → `finish(全文)`。
