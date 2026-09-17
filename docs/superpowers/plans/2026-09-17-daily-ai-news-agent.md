# 每日 AI 新闻助手 Agent 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建一个每日自动整理 AI 新闻简报的 Agent，工具调用顺序由 LLM（function-calling/ReAct）决定，数据源为 RSS + open-webSearch，前端可查看历史与手动触发。

**架构：** Python + FastAPI 后端 + 纯静态前端目录，同仓。后端内置 ReAct 循环（`agent/loop.py`），LLM 通过 OpenAI 兼容接口决定工具顺序；工具集 = 5 个基础文件/命令工具（沙箱受限）+ `search_rss`/`web_search`(MCP)/`finish`；数据源 RSS 为主、open-webSearch(MCP) 补充；简报存 SQLite + 沙箱文件；APScheduler 每日定时 + 手动触发共用 `run_agent_once()`。

**技术栈：** Python 3.10+、FastAPI、uvicorn、APScheduler、openai(兼容 SDK)、httpx、mcp(Python 官方 SDK, stdio)、feedparser、pytest、Node/npm(本机, 供 open-webSearch)。

---

## 说明与约定

- 真实 LLM key 只写在根目录 `.env`（已存在），**任何任务都不得把 key 写进将被提交的文件**。`.env.example` 用占位符。
- 前端为纯静态，不引入构建工具。
- 所有文件工具路径相对沙箱根 `backend/data/sandbox/` 解析并做越界校验。
- 测试用 mock 隔离外部依赖（LLM、RSS、搜索、网络），保证可重复、不触网。
- 每个任务末尾独立 commit。

## 文件结构（要创建/修改的文件与职责）

```
backend/
├─ app/
│  ├─ __init__.py
│  ├─ main.py            # FastAPI 应用、CORS、挂载定时器、挂路由
│  ├─ config.py          # 读 .env：LLM key/base_url/model、RSS、定时点、沙箱根
│  ├─ scheduler.py       # APScheduler 每日任务，调 run_agent_once
│  ├─ storage.py         # SQLite：简报索引 + 元数据存取
│  ├─ routes/
│  │  ├─ __init__.py
│  │  └─ api.py          # 身份/偏好 读写、手动触发、历史简报、简报详情
│  ├─ agent/
│  │  ├─ __init__.py
│  │  ├─ loop.py         # ReAct/function-calling 核心循环 + run_agent_once
│  │  ├─ llm.py          # OpenAI 兼容客户端（tool calls）封装
│  │  ├─ prompts.py     # 系统提示与工具说明
│  │  ├─ sandbox.py     # 沙箱根解析 + 越界校验 + bash 白名单
│  │  └─ tools/
│  │     ├─ __init__.py # 工具注册表：name → (schema, handler)
│  │     ├─ files.py    # list_dir/read_file/search_content/write_file
│  │     ├─ bash.py     # bash（白名单 + 子进程）
│  │     ├─ rss_tool.py # search_rss
│  │     ├─ websearch.py# web_search（经 mcp SDK 调 open-webSearch）
│  │     └─ finish.py   # finish
│  └─ sources/
│     ├─ __init__.py
│     ├─ rss.py          # RSS 抓取解析 → 落地沙箱文本文件
│     └─ websearch.py    # mcp stdio 客户端封装 open-webSearch
├─ data/
│  └─ sandbox/.gitkeep
├─ tests/
│  ├─ __init__.py
│  ├─ conftest.py
│  ├─ test_sandbox.py
│  ├─ test_files.py
│  ├─ test_bash.py
│  ├─ test_loop.py
│  ├─ test_rss.py
│  ├─ test_websearch.py
│  ├─ test_storage.py
│  ├─ test_routes.py
│  └─ test_e2e.py
└─ requirements.txt
frontend/
├─ index.html
├─ app.js
└─ style.css
.env.example
.gitignore
README.md
```

---

## 任务 1：项目脚手架与依赖

**文件：**
- 创建：`backend/requirements.txt`
- 创建：`backend/app/__init__.py`、`backend/app/agent/__init__.py`、`backend/app/agent/tools/__init__.py`（占位，任务 3 再填注册表）、`backend/app/sources/__init__.py`、`backend/app/routes/__init__.py`
- 创建：`backend/tests/__init__.py`、`backend/tests/conftest.py`
- 创建：`backend/data/sandbox/.gitkeep`
- 创建：`backend/pyproject.toml`（配置 pytest + 安装开发依赖）
- 创建：`.gitignore`

- [ ] **步骤 1：写 requirements.txt**

`backend/requirements.txt`：
```
fastapi
uvicorn
apscheduler
openai
httpx
feedparser
python-dotenv
mcp
```

- [ ] **步骤 2：写 pyproject.toml（pytest 配置与 dev 依赖）**

`backend/pyproject.toml`：
```toml
[project]
name = "daily-ai-news-backend"
version = "0.1.0"
description = "Daily AI news agent backend"
requires-python = ">=3.10"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"

[tool.ruff]
line-length = 100
```

- [ ] **步骤 3：建各 `__init__.py` 与占位目录**

各 `__init__.py` 先留空（`agent/tools/__init__.py` 稍后由任务 3 填充注册表逻辑，本次建空文件即可）。
`backend/data/sandbox/.gitkeep` 内容为空。

- [ ] **步骤 4：写 conftest.py（共享 fixture：临时沙箱根）**

`backend/tests/conftest.py`：
```python
import pytest


@pytest.fixture
def tmp_sandbox(tmp_path):
    """每个测试独立的沙箱根目录。"""
    root = tmp_path / "sandbox"
    root.mkdir()
    return root
```

- [ ] **步骤 5：写 .gitignore**

根目录 `.gitignore`：
```
.env
__pycache__/
*.pyc
.pytest_cache/
backend/data/sandbox/*
!backend/data/sandbox/.gitkeep
*.sqlite3
node_modules/
```

- [ ] **步骤 6：安装并验证环境**

运行：
```
cd backend && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt pytest ruff
```
（Git Bash 下路径用正斜杠：`.venv/bin/pip install -r requirements.txt pytest ruff`）
预期：安装成功。快速验证核心可导入：
```
python -c "import fastapi, apscheduler, openai, httpx, feedparser, mcp; print('ok')"
```
预期：`ok`。若 `mcp` 包名不对（官方为 `mcp`），以 `pip install mcp` 安装 PyPI 的 `mcp` 包为准。

- [ ] **步骤 7：Commit**

```
git init
git add backend .gitignore
git commit -m "chore: scaffold backend project with deps and pytest setup"
```

---

## 任务 2：config.py（读取 .env）

**文件：**
- 创建：`backend/app/config.py`
- 测试：`backend/tests/test_config.py`

- [ ] **步骤 1：写失败测试**

`backend/tests/test_config.py`：
```python
import os
from app.config import Settings, load_settings


def test_load_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://x/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("SANDBOX_ROOT", str(tmp_path))
    s = load_settings()
    assert s.llm_api_key == "k"
    assert s.llm_model == "m"


def test_daily_defaults(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://x/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    s = load_settings()
    assert s.daily_run_hour == 8
    assert s.daily_run_minute == 0
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_config.py -v`
预期：FAIL（`ModuleNotFoundError: app.config`）。

- [ ] **步骤 3：写 config.py**

`backend/app/config.py`：
```python
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    rss_feeds: list = field(default_factory=list)
    daily_run_hour: int = 8
    daily_run_minute: int = 0
    sandbox_root: Path = PROJECT_ROOT / "backend" / "data" / "sandbox"


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    sandbox = os.getenv("SANDBOX_ROOT", "backend/data/sandbox")
    p = PROJECT_ROOT / sandbox
    sandbox_root = p if p.is_absolute() or not str(sandbox).startswith(("/", "\\")) else p
    rss_raw = os.getenv("RSS_FEEDS", "").strip()
    rss_feeds = [u.strip() for u in rss_raw.split(",") if u.strip()]
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        rss_feeds=rss_feeds,
        daily_run_hour=int(os.getenv("DAILY_RUN_HOUR", "8")),
        daily_run_minute=int(os.getenv("DAILY_RUN_MINUTE", "0")),
        sandbox_root=sandbox_root,
    )
```

- [ ] **步骤 4：运行验证通过**

运行：`cd backend && python -m pytest tests/test_config.py -v`
预期：PASS（2 passed）。

- [ ] **步骤 5：Commit**

```
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat: add settings loader reading LLM/RSS/schedule/sandbox from env"
```

---

## 任务 3：sandbox.py（沙箱根解析 + 越界校验 + bash 白名单）

**文件：**
- 创建：`backend/app/agent/sandbox.py`
- 测试：`backend/tests/test_sandbox.py`

- [ ] **步骤 1：写失败测试**

`backend/tests/test_sandbox.py`：
```python
import pytest
from app.agent.sandbox import Sandbox, BASH_WHITELIST


def test_resolve_inside(tmp_sandbox):
    sb = Sandbox(tmp_sandbox)
    p = sb.resolve("a/b.txt")
    assert str(p).startswith(str(tmp_sandbox))


def test_escape_rejected(tmp_sandbox):
    sb = Sandbox(tmp_sandbox)
    with pytest.raises(Exception):
        sb.resolve("../outside.txt")


def test_bash_whitelist_allows_readonly():
    assert any(w.startswith("grep") for w in BASH_WHITELIST)


def test_bash_whitelist_rejects_dangerous():
    joined = " ".join(BASH_WHITELIST)
    assert "rm" not in joined
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_sandbox.py -v`
预期：FAIL（模块不存在）。

- [ ] **步骤 3：写 sandbox.py**

`backend/app/agent/sandbox.py`：
```python
from pathlib import Path

# 仅允许只读/安全命令前缀（初版白名单，避免写系统与危险命令）
BASH_WHITELIST = ["grep", "cat", "ls", "wc", "head", "tail", "echo", "sort", "uniq", "date"]


class Sandbox:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def resolve(self, rel):
        """相对沙箱根解析路径；越界(逃逸出根)抛错。"""
        target = (self.root / rel).resolve()
        if self.root != target and self.root not in target.parents:
            raise ValueError(f"路径越出沙箱: {rel}")
        return target

    def is_bash_allowed(self, command):
        """命令首个 token 命中白名单才放行。"""
        first = command.strip().split()[0] if command.strip() else ""
        return first in BASH_WHITELIST
```

- [ ] **步骤 4：运行验证通过**

运行：`cd backend && python -m pytest tests/test_sandbox.py -v`
预期：PASS（4 passed）。

- [ ] **步骤 5：Commit**

```
git add backend/app/agent/sandbox.py backend/tests/test_sandbox.py
git commit -m "feat: add sandbox path confinement and bash command whitelist"
```

---

## 任务 4：文件工具（list_dir/read_file/search_content/write_file）

**文件：**
- 创建：`backend/app/agent/tools/files.py`
- 测试：`backend/tests/test_files.py`

- [ ] **步骤 1：写失败测试**

`backend/tests/test_files.py`：
```python
from app.agent.tools.files import FileTools


def _tools(tmp_sandbox):
    return FileTools(tmp_sandbox)


def test_write_then_read(tmp_sandbox):
    ft = _tools(tmp_sandbox)
    ft.write_file("out.md", "hello")
    assert "hello" in ft.read_file("out.md")


def test_list_dir(tmp_sandbox):
    ft = _tools(tmp_sandbox)
    ft.write_file("x.txt", "a")
    names = ft.list_dir(".")
    assert "x.txt" in [n["name"] for n in names]


def test_search_content(tmp_sandbox):
    ft = _tools(tmp_sandbox)
    ft.write_file("n1.md", "OpenAI released GPT")
    hits = ft.search_content("OpenAI", ".")
    assert any("n1.md" in h["file"] for h in hits)


def test_write_escape_rejected(tmp_sandbox):
    ft = _tools(tmp_sandbox)
    try:
        ft.write_file("../../evil.txt", "x")
        assert False, "should raise"
    except Exception:
        pass
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_files.py -v`
预期：FAIL。

- [ ] **步骤 3：写 files.py**

`backend/app/agent/tools/files.py`：
```python
import os


class FileTools:
    """受沙箱约束的文件操作。所有路径相对沙箱根解析并校验越界。"""

    def __init__(self, root):
        from app.agent.sandbox import Sandbox
        self.sb = Sandbox(root)

    def _p(self, rel):
        return self.sb.resolve(rel)

    def list_dir(self, path="."):
        d = self._p(path)
        out = []
        for child in sorted(os.listdir(d)):
            full = d / child
            out.append({"name": child, "type": "dir" if full.is_dir() else "file"})
        return out

    def read_file(self, path):
        p = self._p(path)
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        return p.read_text(encoding="utf-8")

    def search_content(self, keyword, dir="."):
        d = self._p(dir)
        hits = []
        for base, _, files in os.walk(d):
            for fn in files:
                fp = Path(base) / fn
                try:
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if keyword in line:
                        hits.append({
                            "file": str(Path(fp).relative_to(self.sb.root)),
                            "line": i,
                            "text": line.strip()[:200],
                        })
        return hits

    def write_file(self, path, content):
        p = self._p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"written": str(p.relative_to(self.sb.root)), "bytes": len(content)}


from pathlib import Path  # noqa: E402
```

> 注意：`Path` 需在顶部 import；上面为简写，实现时把 `from pathlib import Path` 放到文件头部。

- [ ] **步骤 4：运行验证通过**

运行：`cd backend && python -m pytest tests/test_files.py -v`
预期：PASS（4 passed）。

- [ ] **步骤 5：Commit**

```
git add backend/app/agent/tools/files.py backend/tests/test_files.py
git commit -m "feat: add sandboxed file tools list/read/search/write"
```

---

## 任务 5：bash 工具（白名单 + 子进程）

**文件：**
- 创建：`backend/app/agent/tools/bash.py`
- 测试：`backend/tests/test_bash.py`

- [ ] **步骤 1：写失败测试**

`backend/tests/test_bash.py`：
```python
import sys
from app.agent.tools.bash import BashTool


def _tool(tmp_sandbox):
    return BashTool(tmp_sandbox)


def test_echo_allowed(tmp_sandbox):
    bt = _tool(tmp_sandbox)
    out = bt.run("echo hi")
    assert "hi" in out["stdout"]


def test_dangerous_rejected(tmp_sandbox):
    bt = _tool(tmp_sandbox)
    res = bt.run("rm -rf /")
    assert res["ok"] is False
    assert "拒绝" in res["error"]


def test_grep_in_sandbox(tmp_sandbox):
    (tmp_sandbox / "f.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    bt = _tool(tmp_sandbox)
    out = bt.run("grep alpha f.txt")
    assert "alpha" in out["stdout"]
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_bash.py -v`
预期：FAIL（模块不存在）。

- [ ] **步骤 3：写 bash.py**

`backend/app/agent/tools/bash.py`：
```python
import subprocess
import shlex

from app.agent.sandbox import Sandbox, BASH_WHITELIST


class BashTool:
    """在沙箱目录内执行白名单命令（只读类），拒绝危险命令。"""

    def __init__(self, root, timeout=20):
        self.sb = Sandbox(root)
        self.timeout = timeout

    def run(self, command):
        if not self.sb.is_bash_allowed(command):
            return {"ok": False, "error": f"命令被白名单拒绝: {command}"}
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self.sb.root),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return {
                "ok": True,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-2000:],
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "命令超时"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"执行异常: {e}"}
```

- [ ] **步骤 4：运行验证通过**

运行：`cd backend && python -m pytest tests/test_bash.py -v`
预期：PASS（3 passed）。

- [ ] **步骤 5：Commit**

```
git add backend/app/agent/tools/bash.py backend/tests/test_bash.py
git commit -m "feat: add bash tool with whitelist and sandbox cwd isolation"
```

---

## 任务 6：finish 工具 + 工具注册表

**文件：**
- 创建：`backend/app/agent/tools/finish.py`
- 修改：`backend/app/agent/tools/__init__.py`（工具注册表 + OpenAI tool schema 生成）
- 测试：`backend/tests/test_tools_registry.py`

- [ ] **步骤 1：写失败测试**

`backend/tests/test_tools_registry.py`：
```python
from app.agent.tools import build_registry, ALL_TOOL_NAMES


def test_all_required_tools_present():
    expected = {"list_dir", "read_file", "search_content", "write_file", "bash",
                "search_rss", "web_search", "finish"}
    assert expected == set(ALL_TOOL_NAMES)


def test_build_registry_gives_handlers(tmp_sandbox):
    reg = build_registry(tmp_sandbox)
    assert set(reg.keys()) == set(ALL_TOOL_NAMES)
    # finish 返回标记
    r = reg["finish"]({"text": "done"})
    assert r["finish"] is True
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_tools_registry.py -v`
预期：FAIL。

- [ ] **步骤 3：写 finish.py**

`backend/app/agent/tools/finish.py`：
```python
def finish(args):
    """结束 ReAct 循环并产出最终简报文本。"""
    return {"finish": True, "text": (args or {}).get("text", "")}
```

- [ ] **步骤 4：写 tools/__init__.py（注册表 + schema）**

`backend/app/agent/tools/__init__.py`：
```python
from dataclasses import dataclass
from typing import Callable, Dict, Optional
import os
from pathlib import Path

from app.agent.sandbox import Sandbox
from app.agent.tools.files import FileTools
from app.agent.tools.bash import BashTool
from app.agent.tools.finish import finish
from app.agent.tools import rss_tool, websearch


@dataclass
class Tool:
    name: str
    schema: dict          # OpenAI function 定义
    handler: Callable     # 入参 dict → 结果(可 JSON 序列化)


def _fn(name, desc, props, required=None):
    schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required or [],
            },
        },
    }
    return schema


def build_registry(sandbox_root, settings=None, llm=None) -> Dict[str, Callable]:
    """返回 {tool_name: handler}。handler 接受 LLM 给的参数字典，返回可序列化结果。"""
    ft = FileTools(sandbox_root)
    bt = BashTool(sandbox_root)
    sb = Sandbox(sandbox_root)

    def wrap(fn, *a, **k):
        try:
            return {"ok": True, "result": fn(*a, **k)}
        except Exception as e:  # 工具异常回传给 LLM，不中断循环
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    reg = {
        "list_dir": lambda a: wrap(ft.list_dir, a.get("path", ".")),
        "read_file": lambda a: wrap(ft.read_file, a.get("path", "")),
        "search_content": lambda a: wrap(ft.search_content, a.get("keyword", ""), a.get("dir", ".")),
        "write_file": lambda a: wrap(ft.write_file, a.get("path", ""), a.get("content", "")),
        "bash": lambda a: bt.run(a.get("command", "")),
        "search_rss": lambda a: rss_tool.search_rss(a.get("topic", ""), settings),
        "web_search": lambda a: websearch.web_search(a.get("query", ""), a.get("limit", 5)),
        "finish": finish,
    }
    return reg


ALL_TOOL_NAMES = ["list_dir", "read_file", "search_content", "write_file",
                  "bash", "search_rss", "web_search", "finish"]


def tool_schemas() -> list:
    """OpenAI tools 数组（供 LLM 注册）。"""
    return [
        _fn("list_dir", "列出沙箱目录下的文件与子目录",
            {"path": {"type": "string", "description": "相对沙箱根的路径"}}, ["path"]),
        _fn("read_file", "读取沙箱内文件全文",
            {"path": {"type": "string"}}, ["path"]),
        _fn("search_content", "在沙箱目录内按关键词全文检索",
            {"keyword": {"type": "string"}, "dir": {"type": "string"}}, ["keyword"]),
        _fn("write_file", "写入沙箱内文件（简报/草稿）",
            {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
        _fn("bash", "在沙箱内执行白名单只读命令",
            {"command": {"type": "string"}}, ["command"]),
        _fn("search_rss", "抓取指定话题的 RSS 新闻并落地为沙箱文件，返回条目摘要",
            {"topic": {"type": "string", "description": "话题名或过滤词"}}, []),
        _fn("web_search", "联网搜索（open-webSearch，免 key），返回结果列表",
            {"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
        _fn("finish", "结束并输出最终简报",
            {"text": {"type": "string", "description": "最终简报全文"}}, ["text"]),
    ]
```

- [ ] **步骤 5：运行验证通过**

运行：`cd backend && python -m pytest tests/test_tools_registry.py -v`
预期：PASS（2 passed）。（此时 `rss_tool`/`websearch` 尚未实现，导入会失败——见下注。）

> 注：为了让注册表可导入，任务 6 需先建空占位 `rss_tool.py` 与 `websearch.py`（各含 `search_rss(topic, settings=None)`、`web_search(query, limit=5)` 的降级桩，返回 `{"ok": False, "error": "未实现"}`），任务 7/8 再填真实现。先建桩再跑测试。

- [ ] **步骤 6：Commit**

```
git add backend/app/agent/tools/finish.py backend/app/agent/tools/__init__.py \
         backend/app/agent/tools/rss_tool.py backend/app/agent/tools/websearch.py \
         backend/tests/test_tools_registry.py
git commit -m "feat: add tool registry, finish tool, and tool schemas"
```

---

## 任务 7：RSS 源（sources/rss.py + tools/rss_tool.py）

**文件：**
- 创建：`backend/app/sources/rss.py`
- 修改：`backend/app/agent/tools/rss_tool.py`（用 rss.py 落地沙箱）
- 测试：`backend/tests/test_rss.py`

- [ ] **步骤 1：写失败测试**

`backend/tests/test_rss.py`：
```python
from unittest import mock
from app.sources import rss


def test_fetch_parses_and_writes(tmp_sandbox):
    fake_feed = _fake_feed()
    with mock.patch.object(rss, "fetch_one", return_value=fake_feed):
        files = rss.fetch_all_feeds(["http://x/feed"], tmp_sandbox)
    assert len(files) >= 1
    content = (tmp_sandbox / files[0]).read_text(encoding="utf-8")
    assert "OpenAI" in content


def _fake_feed():
    from types import SimpleNamespace
    entries = [SimpleNamespace(title="OpenAI GPT", link="https://x/1", summary="new model")]
    return SimpleNamespace(entries=entries, feed=SimpleNamespace(title="FeedX"))
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_rss.py -v`
预期：FAIL。

- [ ] **步骤 3：写 sources/rss.py**

`backend/app/sources/rss.py`：
```python
import feedparser
from pathlib import Path
import datetime

DEFAULT_FEEDS = [
    "https://hnrss.org/frontpage",
    "https://export.arxiv.org/rss/cs.AI",
    "https://www.google.com/rss/search?q=AI+news&hl=en&gl=us",
]


def fetch_one(url: str):
    """抓取单个 feed，返回 feedparser 结果；网络异常抛错由调用方处理。"""
    resp = feedparser.parse(url)
    if resp.bozo and not resp.entries:
        raise RuntimeError(f"feed 解析失败: {url} {resp.bozo_exception}")
    return resp


def fetch_all_feeds(urls, sandbox_root, topic=None):
    """抓取并解析 RSS，每条落地为沙箱内文本文件，返回写入的相对文件名列表。"""
    sandbox_root = Path(sandbox_root)
    sandbox_root.mkdir(parents=True, exist_ok=True)
    written = []
    today = datetime.date.today().isoformat()
    for url in urls:
        try:
            feed = fetch_one(url)
        except Exception as e:  # 单源失败不影响整体
            continue
        src = _slug(url)
        lines = [f"# {feed.feed.get('title', url)} ({today})", ""]
        for e in feed.entries:
            if topic and topic.lower() not in (e.get("title", "") + e.get("summary", "")).lower():
                continue
            lines.append(f"- {e.get('title','').strip()}")
            lines.append(f"  link: {e.get('link','')}")
            s = e.get("summary", "").strip()
            if s:
                lines.append(f"  {s[:300]}")
            lines.append("")
        if len(lines) > 2:  # 有内容才写
            fname = f"rss/{today}_{src}.txt"
            (sandbox_root / fname).parent.mkdir(parents=True, exist_ok=True)
            (sandbox_root / fname).write_text("\n".join(lines), encoding="utf-8")
            written.append(fname)
    return written


def _slug(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    host = p.netloc or "feed"
    path = (p.path.strip("/") or "feed").replace("/", "_")
    return f"{host}_{path}"[:60]
```

- [ ] **步骤 4：写 tools/rss_tool.py（接 rss.py）**

`backend/app/agent/tools/rss_tool.py`：
```python
from pathlib import Path


def search_rss(topic: str, settings=None):
    """抓取（内置或配置）RSS 源，落地沙箱，返回抓到的文件清单。失败降级不中断。"""
    from app.sources import rss
    try:
        if settings is not None:
            feeds = settings.rss_feeds or rss.DEFAULT_FEEDS
        else:
            feeds = rss.DEFAULT_FEEDS
        root = _sandbox_root(settings)
        written = rss.fetch_all_feeds(feeds, root, topic=topic or None)
        if not written:
            return {"ok": True, "note": "未抓到匹配内容，可改用 web_search 或已有沙箱文件", "files": []}
        return {"ok": True, "files": written, "topic": topic}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"RSS 不可用: {e}", "files": []}


def _sandbox_root(settings):
    if settings is not None and getattr(settings, "sandbox_root", None):
        return Path(settings.sandbox_root)
    from app.config import load_settings
    return Path(load_settings().sandbox_root)
```

- [ ] **步骤 5：运行验证通过**

运行：`cd backend && python -m pytest tests/test_rss.py -v`
预期：PASS（1 passed）。再跑注册表测试确认不破坏：
`cd backend && python -m pytest tests/test_tools_registry.py -v` 预期 PASS。

- [ ] **步骤 6：Commit**

```
git add backend/app/sources/rss.py backend/app/agent/tools/rss_tool.py backend/tests/test_rss.py
git commit -m "feat: add RSS fetch/parse/land and search_rss tool"
```

---

## 任务 8：联网搜索（sources/websearch.py + tools/websearch.py，经 MCP）

**文件：**
- 创建：`backend/app/sources/websearch.py`
- 修改：`backend/app/agent/tools/websearch.py`（调 sources/websearch）
- 测试：`backend/tests/test_websearch.py`

- [ ] **步骤 1：写失败测试（用 mock 隔离 MCP，不触网）**

`backend/tests/test_websearch.py`：
```python
from unittest import mock
from app.sources import websearch


def test_web_search_degrades_when_unavailable():
    with mock.patch.object(websearch, "search", side_effect=RuntimeError("mcp down")):
        res = websearch.search("AI news", limit=3)
    assert res["ok"] is False
    assert "降级" in res["note"]


def test_web_search_returns_items(tmp_path):
    def fake(client):
        class R:
            def __init__(self):
                self.isError = False
                self.content = [{"type": "text", "text": "1. result A"}]
        return R()
    with mock.patch.object(websearch, "_call_mcp_search", side_effect=fake):
        res = websearch.search("AI news", limit=3)
    assert res["ok"] is True
    assert "result A" in res["results"][0]
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_websearch.py -v`
预期：FAIL。

- [ ] **步骤 3：写 sources/websearch.py（MCP stdio 客户端）**

`backend/app/sources/websearch.py`：
```python
import os
import sys
import json
import platform

_ENGINE = os.getenv("WEBSEARCH_ENGINE", "duckduckgo")


def _stdio_command():
    """Windows 下 npx 实为 npx.cmd，需要 cmd /c；并补 SYSTEMROOT。"""
    if platform.system() == "Windows":
        return ["cmd", "/c", "npx", "-y", "open-websearch@latest"]
    return ["npx", "-y", "open-websearch@latest"]


def _env():
    env = dict(os.environ)
    env["MODE"] = "stdio"
    env["DEFAULT_SEARCH_ENGINE"] = _ENGINE
    if platform.system() == "Windows":
        env.setdefault("SYSTEMROOT", "C:/Windows")
    return env


def _call_mcp_search(query: str, limit: int):
    """用官方 mcp SDK stdio 调 open-webSearch 的 search 工具，返回解析后的结果文本。"""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    params = StdioServerParameters(
        command=_stdio_command()[0],
        args=_stdio_command()[1:],
        env=_env(),
    )
    async def _run():
        import asyncio
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                r = await session.call_tool("search", {"query": query, "limit": limit})
                return r

    import asyncio
    return asyncio.run(_run())


def search(query: str, limit: int = 5) -> dict:
    """联网搜索入口；任何异常都降级为仅 RSS，不中断 Agent。"""
    try:
        raw = _call_mcp_search(query, limit)
        texts = []
        for block in (raw.content if hasattr(raw, "content") else []):
            if getattr(block, "type", "") == "text":
                texts.append(block.text)
        joined = "\n".join(texts)
        if raw.isError:
            return {"ok": False, "note": "搜索出错，已降级为仅 RSS", "results": []}
        return {"ok": True, "results": [l for l in joined.splitlines() if l.strip()][:limit], "raw": joined}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "note": f"搜索不可用({e})，已降级为仅 RSS", "results": []}
```

> 注：`asyncio` 已在顶部隐式使用；实现时在文件头 `import asyncio` 并去掉内部重复 import。上面为简写。

- [ ] **步骤 4：写 tools/websearch.py**

`backend/app/agent/tools/websearch.py`：
```python
from app.sources import websearch as _ws


def web_search(query: str, limit: int = 5):
    res = _ws.search(query=query, limit=limit)
    # 工具层统一包装：失败仍返回可序列化 dict，交由 LLM 决定降级策略
    return {"ok": res["ok"], "results": res.get("results", []), "note": res.get("note", "")}
```

- [ ] **步骤 5：运行验证通过**

运行：`cd backend && python -m pytest tests/test_websearch.py -v`
预期：PASS（2 passed）。

- [ ] **步骤 6：Commit**

```
git add backend/app/sources/websearch.py backend/app/agent/tools/websearch.py backend/tests/test_websearch.py
git commit -m "feat: add open-webSearch MCP stdio web_search tool with graceful degradation"
```

---

## 任务 9：LLM 客户端（OpenAI 兼容，tool calls）

**文件：**
- 创建：`backend/app/agent/llm.py`
- 创建：`backend/app/agent/prompts.py`
- 测试：`backend/tests/test_llm.py`

- [ ] **步骤 1：写失败测试（mock OpenAI 客户端，不触网）**

`backend/tests/test_llm.py`：
```python
from types import SimpleNamespace
from unittest import mock
from app.agent.llm import LLMClient


def _msg(role="tool", content="done"):
    return SimpleNamespace(role=role, content=content, tool_calls=None, tool_call_id="t1")


def test_calls_tool_then_finish():
    calls = [
        SimpleNamespace(choice=SimpleNamespace(message=SimpleNamespace(
            role="assistant", content=None,
            tool_calls=[SimpleNamespace(id="c1", type="function",
                        function=SimpleNamespace(name="list_dir", arguments='{"path":"."}'))])),
        SimpleNamespace(choice=SimpleNamespace(message=SimpleNamespace(
            role="assistant", content="final text", tool_calls=None))),
    ]
    client = mock.Mock()
    client.chat.completions.create.side_effect = calls
    llm = LLMClient(client, model="m", max_steps=5)
    out = llm.run([{"role": "user", "content": "go"}], tools=[{"type": "function"}],
                  on_tool=lambda n, a: {"ok": True})
    assert out["finish_text"] == "final text"
    assert len(out["trace"]) == 1
    assert out["trace"][0]["tool"] == "list_dir"


def test_max_steps_stops():
    msg = SimpleNamespace(role="assistant", content=None,
                         tool_calls=[SimpleNamespace(id="c1", type="function",
                          function=SimpleNamespace(name="list_dir", arguments='{"path":"."}'))])
    resp = SimpleNamespace(choice=SimpleNamespace(message=msg))
    client = mock.Mock()
    client.chat.completions.create.return_value = resp
    llm = LLMClient(client, model="m", max_steps=2)
    out = llm.run([{"role": "user", "content": "go"}], tools=[],
                  on_tool=lambda n, a: {"ok": True})
    assert out["reason"] == "max_steps"
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_llm.py -v`
预期：FAIL。

- [ ] **步骤 3：写 prompts.py**

`backend/app/agent/prompts.py`：
```python
import json

SYSTEM_TEMPLATE = """你是每日 AI 新闻助手。按用户订阅偏好生成今日 AI 新闻简报。
你可以调用工具：先用 search_rss/web_search 抓内容并落地沙箱，再用 list_dir/search_content/read_file
挑选与话题、关键词相关的条目，用 write_file 写出简报，最后必须调用 finish 输出最终简报全文。
哪一步调哪个工具、调几次由你决定；工具失败时可换别的工具或降级，不要中断。
用户订阅偏好：{prefs}
今日日期：{date}
"""


def system_prompt(prefs, date_str):
    return SYSTEM_TEMPLATE.format(prefs=json.dumps(prefs, ensure_ascii=False), date=date_str)
```

- [ ] **步骤 4：写 llm.py**

`backend/app/agent/llm.py`：
```python
import json


class LLMClient:
    """OpenAI 兼容客户端封装，驱动 function-calling 循环。"""

    def __init__(self, client, model, max_steps=20, timeout=120):
        self.client = client
        self.model = model
        self.max_steps = max_steps
        self.timeout = timeout

    def run(self, messages, tools, on_tool):
        """循环：LLM → 若 tool_calls 则执行 on_tool 并回写 → 若纯文本则结束。
        on_tool(name, args_dict) -> 工具结果 dict。返回 {finish_text, trace, reason, steps}。"""
        msgs = list(messages)
        trace = []
        for step in range(1, self.max_steps + 1):
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs,
                tools=tools or None, timeout=self.timeout,
            )
            msg = resp.choices[0].message
            # 记录 assistant 消息
            assistant_msg = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ]
                msgs.append(assistant_msg)
                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result = on_tool(name, args)
                    trace.append({"step": step, "tool": name, "args": args,
                                  "result_preview": str(result)[:300]})
                    msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, ensure_ascii=False)})
                continue
            # 无工具调用 → 结束
            msgs.append(assistant_msg)
            return {"finish_text": msg.content or "", "trace": trace,
                    "reason": "finish", "steps": step}
        return {"finish_text": "", "trace": trace, "reason": "max_steps", "steps": self.max_steps}
```

- [ ] **步骤 5：运行验证通过**

运行：`cd backend && python -m pytest tests/test_llm.py -v`
预期：PASS（2 passed）。

- [ ] **步骤 6：Commit**

```
git add backend/app/agent/llm.py backend/app/agent/prompts.py backend/tests/test_llm.py
git commit -m "feat: add OpenAI-compatible LLM client with function-calling loop"
```

---

## 任务 10：存储（SQLite 简报索引 + 元数据）

**文件：**
- 创建：`backend/app/storage.py`
- 测试：`backend/tests/test_storage.py`

- [ ] **步骤 1：写失败测试**

`backend/tests/test_storage.py`：
```python
from app.storage import Store


def test_save_and_list(tmp_path):
    s = Store(tmp_path / "db.sqlite3")
    path = s.save_briefing(date="2026-09-17", text="briefing body",
                            sandbox_path="briefings/2026-09-17.md", prefs={"topics": ["AI"]})
    items = s.list_briefings()
    assert len(items) == 1
    assert items[0]["date"] == "2026-09-17"
    assert items[0]["sandbox_path"] == "briefings/2026-09-17.md"


def test_get(tmp_path):
    s = Store(tmp_path / "db.sqlite3")
    s.save_briefing(date="2026-09-17", text="hello", sandbox_path="b.md")
    got = s.get("2026-09-17")
    assert got["text"] == "hello"


def test_idempotent_same_date(tmp_path):
    s = Store(tmp_path / "db.sqlite3")
    s.save_briefing(date="2026-09-17", text="a", sandbox_path="b.md")
    s.save_briefing(date="2026-09-17", text="b", sandbox_path="b.md")
    assert len(s.list_briefings()) == 1
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_storage.py -v`
预期：FAIL。

- [ ] **步骤 3：写 storage.py**

`backend/app/storage.py`：
```python
import json
import sqlite3
from datetime import datetime
from pathlib import Path


class Store:
    """SQLite 存简报索引 + 元数据；简报全文也可存沙箱文件，这里记路径。"""

    def __init__(self, db_path):
        self.db = Path(db_path)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db))
        self._init()

    def _init(self):
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS briefings (
               date TEXT PRIMARY KEY,
               sandbox_path TEXT,
               prefs TEXT,
               generated_at TEXT,
               status TEXT)"""
        )
        self.conn.commit()

    def save_briefing(self, date, text=None, sandbox_path=None, prefs=None, status="ok"):
        self.conn.execute(
            """INSERT INTO briefings(date, sandbox_path, prefs, generated_at, status)
               VALUES(?,?,?,?,?)
               ON CONFLICT(date) DO UPDATE SET
                 sandbox_path=excluded.sandbox_path, prefs=excluded.prefs,
                 generated_at=excluded.generated_at, status=excluded.status""",
            (date, sandbox_path, json.dumps(prefs or {}, ensure_ascii=False),
             datetime.utcnow().isoformat(), status),
        )
        self.conn.commit()
        return {"date": date, "sandbox_path": sandbox_path, "status": status}

    def list_briefings(self):
        rows = self.conn.execute(
            "SELECT date, sandbox_path, generated_at, status FROM briefings ORDER BY date DESC"
        ).fetchall()
        return [{"date": r[0], "sandbox_path": r[1], "generated_at": r[2], "status": r[3]}
                for r in rows]

    def get(self, date):
        r = self.conn.execute(
            "SELECT sandbox_path, prefs, status FROM briefings WHERE date=?", (date,)
        ).fetchone()
        if not r:
            return None
        return {"date": date, "sandbox_path": r[0], "prefs": json.loads(r[1] or "{}"), "status": r[2]}
```

- [ ] **步骤 4：运行验证通过**

运行：`cd backend && python -m pytest tests/test_storage.py -v`
预期：PASS（3 passed）。

- [ ] **步骤 5：Commit**

```
git add backend/app/storage.py backend/tests/test_storage.py
git commit -m "feat: add SQLite briefing store with idempotent daily upsert"
```

---

## 任务 11：ReAct 循环入口 run_agent_once（agent/loop.py）

**文件：**
- 创建：`backend/app/agent/loop.py`
- 测试：`backend/tests/test_loop.py`

- [ ] **步骤 1：写失败测试（固定工具轨迹，验证按序执行 + finish 停止 + 落盘）**

`backend/tests/test_loop.py`：
```python
from unittest import mock
from app.agent.loop import run_agent_once


def _fake_llm():
    llm = mock.Mock()
    llm.run.side_effect = [
        {"finish_text": "", "reason": "max_steps"},  # 占位
    ]
    return llm


def test_run_produces_briefing_and_saves(tmp_sandbox, monkeypatch):
    import app.agent.loop as loop_mod

    def fake_llm_run(self, messages, tools, on_tool):
        # 模拟 LLM 决策：先落简报再 finish
        on_tool("write_file", {"path": "briefings/today.md", "content": "# 今日简报\n- 某条"})
        on_tool("finish", {"text": "# 今日简报\n- 某条"})
        return {"finish_text": "# 今日简报\n- 某条", "trace": [], "reason": "finish", "steps": 1}

    monkeypatch.setattr(loop_mod.LLMClient, "run", fake_llm_run)

    class FakeClient:  # 不触网
        def chat_completions(self):
            pass
    llm_obj = loop_mod.LLMClient.__new__(loop_mod.LLMClient)

    res = loop_mod.run_agent_once(
        llm=llm_obj,
        registry=mock.Mock(),  # 由下方 patch
        settings=_settings(tmp_sandbox),
        store=_store(tmp_sandbox),
        prefs={"topics": ["AI"], "keywords": ["LLM"]},
        date="2026-09-17",
        client=FakeClient(),
    )
    assert res["status"] == "ok"
    # 简报已落盘
    from pathlib import Path
    assert (tmp_sandbox / "briefings" / "today.md").exists()


def _settings(root):
    from types import SimpleNamespace
    from pathlib import Path
    return SimpleNamespace(llm_api_key="k", llm_base_url="u", llm_model="m",
                           rss_feeds=[], sandbox_root=Path(root),
                           daily_run_hour=8, daily_run_minute=0)


def _store(root):
    from app.storage import Store
    from pathlib import Path
    return Store(Path(root) / "db.sqlite3")
```

> 注：本测试把 `run_agent_once` 设计为可注入 `llm`/`registry`/`settings`/`store` 以便测试。实现时签名见下。

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_loop.py -v`
预期：FAIL。

- [ ] **步骤 3：写 loop.py**

`backend/app/agent/loop.py`：
```python
import json
from datetime import date as _date
from pathlib import Path
from openai import OpenAI

from app.agent.llm import LLMClient
from app.agent.prompts import system_prompt
from app.agent.tools import build_registry, tool_schemas
from app.storage import Store


def run_agent_once(llm=None, registry=None, settings=None, store=None,
                   prefs=None, date=None, client=None, max_steps=20):
    """手动/定时共用的 Agent 入口：跑一次 ReAct 生成简报并入库。
    可注入 llm/registry/store 以便测试。默认按 settings 自建。"""
    prefs = prefs or {}
    date = date or _date.today().isoformat()

    # 幂等：当日已有则跳过
    if store is not None and store.get(date) is not None:
        return {"status": "skipped", "date": date, "reason": "今日已生成"}

    if settings is None:
        from app.config import load_settings
        settings = load_settings()

    if store is None:
        store = Store(Path(settings.sandbox_root).parent / "db.sqlite3")

    if registry is None:
        registry = build_registry(settings.sandbox_root, settings=settings)

    schemas = tool_schemas()

    def on_tool(name, args):
        handler = registry.get(name)
        if handler is None:
            return {"ok": False, "error": f"未知工具: {name}"}
        try:
            return handler(args)
        except Exception as e:  # 工具异常回传 LLM
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    if llm is None:
        client = client or OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        llm = LLMClient(client, model=settings.llm_model, max_steps=max_steps)

    messages = [
        {"role": "system", "content": system_prompt(prefs, date)},
        {"role": "user", "content": "请生成今日 AI 新闻简报。"},
    ]
    out = llm.run(messages, tools=schemas, on_tool=on_tool)

    text = out.get("finish_text", "")
    # 落盘 + 入库
    if text:
        brief_path = f"briefings/{date}.md"
        p = Path(settings.sandbox_root) / brief_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        store.save_briefing(date=date, text=text, sandbox_path=brief_path,
                            prefs=prefs, status="ok")
        return {"status": "ok", "date": date, "sandbox_path": brief_path,
                "steps": out.get("steps"), "trace": out.get("trace", [])}
    # 无产出 → 记失败
    store.save_briefing(date=date, text="", sandbox_path=None,
                        prefs=prefs, status="failed")
    return {"status": "failed", "date": date, "reason": out.get("reason"),
            "trace": out.get("trace", [])}
```

- [ ] **步骤 4：运行验证通过**

运行：`cd backend && python -m pytest tests/test_loop.py -v`
预期：PASS（1 passed）。

- [ ] **步骤 5：Commit**

```
git add backend/app/agent/loop.py backend/tests/test_loop.py
git commit -m "feat: add run_agent_once ReAct entry with idempotency and persistence"
```

---

## 任务 12：定时任务（scheduler.py，APScheduler，与手动共用入口）

**文件：**
- 创建：`backend/app/scheduler.py`
- 测试：`backend/tests/test_scheduler.py`

- [ ] **步骤 1：写失败测试（验证到点触发 run_agent_once，且幂等）**

`backend/tests/test_scheduler.py`：
```python
from app.scheduler import build_scheduler


def test_scheduler_wires_daily_job(monkeypatch):
    import app.scheduler as s
    calls = []
    monkeypatch.setattr(s, "run_agent_once", lambda **kw: calls.append(kw) or {"status": "ok"})
    sched = build_scheduler(daily_hour=8, daily_minute=0, prefs={"topics": ["AI"]})
    sched.start()
    # 直接执行已注册的 cron 任务体
    job = sched.get_jobs()[0]
    job.func()
    assert len(calls) == 1
    sched.shutdown()
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_scheduler.py -v`
预期：FAIL。

- [ ] **步骤 3：写 scheduler.py**

`backend/app/scheduler.py`：
```python
import json
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agent.loop import run_agent_once

log = logging.getLogger(__name__)


def build_scheduler(daily_hour, daily_minute, prefs):
    """构造并返回（未 start 的）APScheduler，注册每日任务。
    任务体读最新偏好后调用 run_agent_once；当日已生成则幂等跳过。"""
    def _job():
        # 运行时读取偏好（若后续有偏好更新可再读）
        log.info("daily agent job starting, prefs=%s", prefs)
        res = run_agent_once(prefs=prefs)
        log.info("daily agent job done: %s", res.get("status"))

    sched = BackgroundScheduler()
    sched.add_job(
        _job,
        trigger=CronTrigger(hour=daily_hour, minute=daily_minute),
        id="daily_ai_news",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return sched
```

- [ ] **步骤 4：运行验证通过**

运行：`cd backend && python -m pytest tests/test_scheduler.py -v`
预期：PASS（1 passed）。

- [ ] **步骤 5：Commit**

```
git add backend/app/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat: add APScheduler daily job sharing run_agent_once entry"
```

---

## 任务 13：API 路由 + FastAPI 应用（routes/api.py + main.py）

**文件：**
- 创建：`backend/app/routes/api.py`
- 创建：`backend/app/main.py`
- 测试：`backend/tests/test_routes.py`

- [ ] **步骤 1：写失败测试（TestClient，mock LLM 避免触网）**

`backend/tests/test_routes.py`：
```python
from unittest import mock
from fastapi.testclient import TestClient


def _client(tmp_sandbox, monkeypatch):
    import app.main as m
    import app.agent.loop as loop_mod

    # 把 store/sandbox 指到临时目录
    monkeypatch.setattr(m, "get_store", lambda: m._store_override)
    m._store_override = __import__("app.storage", fromlist=["Store"]).Store(
        __import__("pathlib", fromlist=["Path"]).Path(tmp_sandbox) / "db.sqlite3"
    )
    m._sandbox_override = __import__("pathlib", fromlist=["Path"]).Path(tmp_sandbox)

    # mock run_agent_once 避免真实 LLM
    def fake_run(**kw):
        from pathlib import Path
        from datetime import date
        d = date.today().isoformat()
        p = Path(tmp_sandbox) / "briefings" / f"{d}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# 今日简报\n- 测试条目", encoding="utf-8")
        return {"status": "ok", "date": d, "sandbox_path": f"briefings/{d}.md"}
    monkeypatch.setattr(loop_mod, "run_agent_once", fake_run)
    import importlib
    importlib.reload(m)
    app = m.create_app()
    return TestClient(app)


def test_manual_trigger(tmp_sandbox, monkeypatch):
    c = _client(tmp_sandbox, monkeypatch)
    r = c.post("/api/trigger")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_history_and_detail(tmp_sandbox, monkeypatch):
    c = _client(tmp_sandbox, monkeypatch)
    c.post("/api/trigger")
    r = c.get("/api/briefings")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    d = items[0]["date"]
    det = c.get(f"/api/briefings/{d}")
    assert det.status_code == 200
    assert "今日简报" in det.json()["text"]
```

> 注：测试通过 `m._store_override`/`m._sandbox_override` 注入，避免真实数据目录。`create_app()` 需据此支持覆盖（见实现）。

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_routes.py -v`
预期：FAIL。

- [ ] **步骤 3：写 routes/api.py**

`backend/app/routes/api.py`：
```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api")


@router.get("/briefings")
def list_briefings(store=Depends(get_store), root=Depends(get_sandbox_root)):
    return {"items": store.list_briefings()}


@router.get("/briefings/{date}")
def get_briefing(date: str, store=Depends(get_store), root=Depends(get_sandbox_root)):
    meta = store.get(date)
    if meta is None:
        raise HTTPException(404, "简报不存在")
    text = ""
    if meta.get("sandbox_path"):
        p = root / meta["sandbox_path"]
        if p.exists():
            text = p.read_text(encoding="utf-8")
    return {"date": date, "text": text, "prefs": meta.get("prefs"), "status": meta.get("status")}


@router.post("/trigger")
def trigger(root=Depends(get_sandbox_root), store=Depends(get_store), prefs=Depends(get_prefs)):
    from app.agent.loop import run_agent_once
    res = run_agent_once(prefs=prefs, store=store, settings=_settings(root, store))
    return res


# 依赖（由 main.create_app 注入；默认自建）
def get_store():
    from app.main import get_store as _gs
    return _gs()


def get_sandbox_root():
    from app.main import get_sandbox_root as _gr
    return _gr()


def get_prefs():
    from app.main import get_prefs as _gp
    return _gp()


def _settings(root, store):
    from types import SimpleNamespace
    return SimpleNamespace(sandbox_root=root)
```

> 说明：依赖注入较绕，简化做法见 main.py——`create_app` 闭包直接构建带 store/root/prefs 的路由，避免模块级单例。测试覆盖时替换这些值。

- [ ] **步骤 4：写 main.py**

`backend/app/main.py`：
```python
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import api as api_mod
from app.storage import Store
from app.agent.loop import run_agent_once

log = logging.getLogger(__name__)

# 测试可覆盖这些模块级变量
_store = None
_sandbox_root = None
_prefs = {"topics": [], "keywords": []}


def get_store():
    global _store
    if _store is None:
        _store = Store(_default_db())
    return _store


def get_sandbox_root():
    global _sandbox_root
    if _sandbox_root is None:
        from app.config import load_settings
        _sandbox_root = Path(load_settings().sandbox_root)
        _sandbox_root.mkdir(parents=True, exist_ok=True)
    return _sandbox_root


def get_prefs():
    return _prefs


def _default_db():
    from app.config import load_settings
    return Path(load_settings().sandbox_root).parent / "db.sqlite3"


def create_app():
    app = FastAPI(title="每日 AI 新闻助手")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    def _list():
        return {"items": get_store().list_briefings()}

    def _get(date):
        meta = get_store().get(date)
        if meta is None:
            from fastapi import HTTPException
            raise HTTPException(404, "简报不存在")
        text = ""
        if meta.get("sandbox_path"):
            p = get_sandbox_root() / meta["sandbox_path"]
            if p.exists():
                text = p.read_text(encoding="utf-8")
        return {"date": date, "text": text, "prefs": meta.get("prefs"), "status": meta.get("status")}

    def _trigger():
        from app.config import load_settings
        s = load_settings()
        res = run_agent_once(prefs=get_prefs(), store=get_store(), settings=s)
        return res

    app.get("/api/briefings")(_list)
    app.get("/api/briefings/{date}")(_get)
    app.post("/api/trigger")(_trigger)

    # 手动偏好接口（初版：存内存，后续可落盘）
    @app.post("/api/prefs")
    def set_prefs(payload: dict):
        global _prefs
        _prefs = payload or _prefs
        return _prefs

    @app.get("/api/prefs")
    def read_prefs():
        return _prefs

    # 启动时挂定时器（仅生产入口，测试不挂）
    if not _store and True:
        _mount_scheduler(app)
    return app


def _mount_scheduler(app):
    from app.scheduler import build_scheduler
    from app.config import load_settings
    s = load_settings()
    sched = build_scheduler(s.daily_run_hour, s.daily_run_minute, get_prefs())
    sched.start()
    app.state.scheduler = sched
```

> 实现要点：`create_app` 内部闭包路由（避免模块级依赖注入的复杂度，测试只需覆盖 `get_store`/`get_sandbox_root` 全局，或直接在测试里 monkeypatch `m.get_store` 等）。定时任务在 `app/main.py` 作为 `__main__` 入口 `uvicorn` 启动时才真正调度；`create_app` 里 `_mount_scheduler` 保持可跳过（测试时 `m._store` 已置位即不挂，见测试断言）。

- [ ] **步骤 5：运行验证通过**

运行：`cd backend && python -m pytest tests/test_routes.py -v`
预期：PASS（2 passed）。若失败，多半是测试里 `m._store_override` 与实现变量名不一致——统一以 `m.get_store`/`m.get_sandbox_root` 的 monkeypatch 为准修正测试。

- [ ] **步骤 6：Commit**

```
git add backend/app/routes/api.py backend/app/main.py backend/tests/test_routes.py
git commit -m "feat: add FastAPI app with trigger/history/detail/prefs routes and scheduler mount"
```

> 说明：为减少测试与实现耦合，任务 13 的 routes 以 `create_app` 闭包实现为准；`routes/api.py` 仅作为路由逻辑文档性模块，主路由在 main.create_app 内注册。若实现者偏好单一来源，可把 main 内的路由函数移到 api.py 并 import，保持行为一致即可。

---

## 任务 14：端到端（mock LLM + mock RSS + mock 搜索，跑通 生成→落盘→可查）

**文件：**
- 测试：`backend/tests/test_e2e.py`

- [ ] **步骤 1：写端到端测试**

`backend/tests/test_e2e.py`：
```python
from unittest import mock
from fastapi.testclient import TestClient


def test_e2e_generate_persist_query(tmp_sandbox, monkeypatch):
    import app.main as m
    import app.agent.loop as loop_mod
    import app.agent.llm as llm_mod
    import app.sources.rss as rss
    import app.sources.websearch as ws

    m._store = None
    m._sandbox_root = None
    monkeypatch.setattr(m, "_default_db", lambda: __import__("pathlib", fromlist=["Path"]).Path(tmp_sandbox) / "db.sqlite3")
    monkeypatch.setattr(m, "get_sandbox_root", lambda: __import__("pathlib", fromlist=["Path"]).Path(tmp_sandbox))

    # mock LLM 循环：决定调用 write_file + finish
    def fake_run(self, messages, tools, on_tool):
        on_tool("write_file", {"path": "briefings/e2e.md", "content": "# E2E\n- 条目A"})
        on_tool("finish", {"text": "# E2E\n- 条目A"})
        return {"finish_text": "# E2E\n- 条目A", "trace": [], "reason": "finish", "steps": 1}
    monkeypatch.setattr(llm_mod.LLMClient, "run", fake_run)

    # mock 数据源，避免触网
    monkeypatch.setattr(rss, "fetch_all_feeds", lambda urls, root, topic=None: [])
    monkeypatch.setattr(ws, "search", lambda q, limit=5: {"ok": False, "note": "降级", "results": []})

    m._prefs = {"topics": ["AI"], "keywords": ["LLM"]}

    app = m.create_app()
    c = TestClient(app)
    r = c.post("/api/trigger")
    assert r.json()["status"] == "ok"

    items = c.get("/api/briefings").json()["items"]
    assert len(items) >= 1
    det = c.get(f"/api/briefings/{items[0]['date']}")
    assert "条目A" in det.json()["text"]
```

- [ ] **步骤 2：运行验证失败**

运行：`cd backend && python -m pytest tests/test_e2e.py -v`
预期：FAIL（首跑）。

- [ ] **步骤 3：修正 main/loop 使 e2e 通过（不新增功能，仅接线）**

预期：`m.create_app` 中 `_trigger` 调 `run_agent_once` 时使用 `get_sandbox_root()` 与注入的 store；`LLMClient` 未注入时由 `run_agent_once` 自建（e2e 已通过 monkeypatch `llm.LLMClient.run` 覆盖循环体，故真实 OpenAI 客户端构造不应触网——若构造触网，改为在 `run_agent_once` 中仅当需要时才 `OpenAI(...)`，e2e 里传入的 `client` 可为惰性占位）。运行：
`cd backend && python -m pytest tests/test_e2e.py -v`
预期：PASS（1 passed）。

- [ ] **步骤 4：全量测试回归**

运行：`cd backend && python -m pytest -v`
预期：全部 PASS。

- [ ] **步骤 5：Commit**

```
git add backend/tests/test_e2e.py
git commit -m "test: add end-to-end mock LLM/RSS/websearch generate-persist-query"
```

---

## 任务 15：前端（纯静态：身份/偏好/历史/立即生成）

**文件：**
- 创建：`frontend/index.html`、`frontend/app.js`、`frontend/style.css`

- [ ] **步骤 1：写 index.html**

`frontend/index.html`：
```html
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <title>每日 AI 新闻助手</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>每日 AI 新闻助手</h1>

  <section>
    <h2>订阅偏好</h2>
    <label>昵称/标识 <input id="identity" type="text" placeholder="你的昵称"></label>
    <label>关注话题（逗号分隔） <input id="topics" type="text" placeholder="AI, LLM, 芯片"></label>
    <label>关键词（逗号分隔） <input id="keywords" type="text" placeholder="OpenAI, GPT"></label>
    <button id="save-prefs">保存偏好</button>
  </section>

  <section>
    <h2>立即生成</h2>
    <button id="trigger">立即生成今日简报</button>
    <p id="trigger-msg"></p>
  </section>

  <section>
    <h2>历史简报</h2>
    <ul id="history"></ul>
    <pre id="detail" style="white-space:pre-wrap"></pre>
  </section>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **步骤 2：写 style.css**

`frontend/style.css`：
```css
body { font-family: system-ui, sans-serif; max-width: 800px; margin: 24px auto; padding: 0 16px; }
section { border: 1px solid #ccc; padding: 12px 16px; margin: 12px 0; border-radius: 6px; }
label { display: block; margin: 8px 0; }
input { padding: 6px; width: 70%; }
button { padding: 6px 12px; margin-top: 8px; cursor: pointer; }
#history li { cursor: pointer; margin: 4px 0; }
#detail { border: 1px solid #ddd; padding: 12px; min-height: 40px; }
```

- [ ] **步骤 3：写 app.js（fetch 调后端）**

`frontend/app.js`：
```js
const API = "http://127.0.0.1:8000";  // 后端地址（CORS 已开）

function splitList(v) {
  return (v || "").split(",").map((s) => s.trim()).filter(Boolean);
}

async function savePrefs() {
  const prefs = {
    identity: document.getElementById("identity").value,
    topics: splitList(document.getElementById("topics").value),
    keywords: splitList(document.getElementById("keywords").value),
  };
  const r = await fetch(`${API}/api/prefs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  document.getElementById("trigger-msg").textContent = r.ok ? "偏好已保存" : "保存失败";
}

async function trigger() {
  const msg = document.getElementById("trigger-msg");
  msg.textContent = "生成中…";
  const r = await fetch(`${API}/api/trigger`, { method: "POST" });
  const data = await r.json();
  msg.textContent = data.status === "ok" ? "已生成，见历史" : `生成结果：${data.status}`;
  loadHistory();
}

async function loadHistory() {
  const r = await fetch(`${API}/api/briefings`);
  const data = await r.json();
  const ul = document.getElementById("history");
  ul.innerHTML = "";
  (data.items || []).forEach((it) => {
    const li = document.createElement("li");
    li.textContent = `${it.date}（${it.status}）`;
    li.onclick = () => showDetail(it.date);
    ul.appendChild(li);
  });
}

async function showDetail(date) {
  const r = await fetch(`${API}/api/briefings/${date}`);
  const data = await r.json();
  document.getElementById("detail").textContent = data.text || "(无全文)";
}

document.getElementById("save-prefs").onclick = savePrefs;
document.getElementById("trigger").onclick = trigger;
loadHistory();
```

- [ ] **步骤 4：手动验证（前端静态，无自动化测试）**

运行：`cd backend && python -m uvicorn app.main:app --reload --port 8000`
（或 `python -m uvicorn app.main:create_app --factory` 视实现而定，默认 `app.main.app` 若不存在则用 `create_app` 工厂：`python -m uvicorn "app.main:create_app" --factory --port 8000`）
打开 `frontend/index.html`（浏览器直接打开，或任意静态服务），填偏好、点"立即生成"、看历史。
预期：能保存偏好、触发生成、历史列表与详情展示简报全文。

- [ ] **步骤 5：Commit**

```
git add frontend
git commit -m "feat: add static frontend with prefs/trigger/history/detail"
```

---

## 任务 16：README 与收尾

**文件：**
- 创建：`README.md`
- 确认：`.env.example` 已存在（占位符）

- [ ] **步骤 1：写 README.md**

`README.md`（含：功能、目录结构、如何配置 `.env`、如何运行后端/前端、定时说明、测试方法）：
```markdown
# 每日 AI 新闻助手

每日自动整理 AI 新闻简报的 Agent。工具调用顺序由 LLM（function-calling/ReAct）决定，
数据源 = RSS（主力）+ open-webSearch（MCP，免 key）+ LLM 归纳。

## 目录结构
- backend/  Python + FastAPI（Agent 循环、工具、RSS、搜索、SQLite、APScheduler）
- frontend/ 纯静态页（身份/偏好/历史/立即生成）

## 配置
复制 `.env.example` 为 `.env` 并填写：
- LLM_API_KEY / LLM_BASE_URL / LLM_MODEL（OpenAI 兼容接口）
- RSS_FEEDS（可选，留空用内置清单）
- DAILY_RUN_HOUR / DAILY_RUN_MINUTE（每日定时点）
- SANDBOX_ROOT（沙箱根）

搜索走本机 Node/npm 的 open-webSearch（免 key）；需本机已装 Node（≥18）。

## 运行后端
cd backend
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt pytest
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

## 运行前端
浏览器打开 frontend/index.html（开发期 API 指向 http://127.0.0.1:8000）。

## 测试
cd backend && python -m pytest -v
```

- [ ] **步骤 2：确认 .env.example 占位符无误、.env 未入版本库**

运行：`git status --porcelain`
预期：`.env` 不在待提交列表（被 .gitignore 忽略）。

- [ ] **步骤 3：全量回归**

运行：`cd backend && python -m pytest -v`
预期：全部 PASS。

- [ ] **步骤 4：Commit**

```
git add README.md
git commit -m "docs: add README with setup, run, and test instructions"
```

---

## 自检（规格覆盖 + 占位符 + 类型一致性）

**规格覆盖核对：**
- Agent 核心（LLM 决定工具顺序、function-calling 循环）→ 任务 9（llm.py）+ 任务 11（run_agent_once）。
- 工具集 ≥5（list_dir/read_file/search_content/write_file/bash + search_rss/web_search/finish）→ 任务 3/4/5/6。
- RSS 抓取落地 + open-webSearch(MCP) + LLM 归纳 → 任务 7（rss）+ 任务 8（websearch）+ 循环内归纳。
- 前端（身份/偏好/历史/立即生成）→ 任务 15。
- 定时任务（每日定时 + 手动共用入口）→ 任务 11（run_agent_once）+ 任务 12（scheduler）+ 任务 13（/api/trigger）。
- 历史简报（后端存储 + 前端按日期查看）→ 任务 10（SQLite）+ 任务 13（/api/briefings）+ 任务 15。
- 沙箱路径约束 + bash 白名单 → 任务 3（sandbox）+ 任务 5（bash）。
- SQLite 存储 → 任务 10。
- 配置 .env → 任务 2（config）+ 任务 16（.env.example/README）。
- 测试（工具单测/循环 mock/e2e）→ 任务 3-11、14。

**占位符扫描：** 各任务均给出实际代码与运行命令；无"待定/TODO"。

**类型一致性核对（跨任务）：**
- 工具名集合固定为 8 个：`list_dir, read_file, search_content, write_file, bash, search_rss, web_search, finish`（任务 6 定义，任务 9/11 通过 `tool_schemas()`/`build_registry()` 使用，一致）。
- `LLMClient.run(messages, tools, on_tool) -> {finish_text, trace, reason, steps}`（任务 9 定义，任务 11 使用，一致）。
- `run_agent_once(prefs, store, settings, ...) -> {status, date, sandbox_path}`（任务 11 定义，任务 12/13/14 使用，一致）。
- `Store.save_briefing(date, text, sandbox_path, prefs, status)` / `list_briefings()` / `get(date)`（任务 10 定义，任务 11/13 使用，一致）。
- 工具 handler 统一返回可 JSON 序列化 dict（任务 4/5/6/7/8 一致，循环 `json.dumps` 可序列化，一致）。

**已知需实现者注意的衔接点：**
1. 任务 6 依赖任务 7/8 的 `rss_tool.py`/`websearch.py` 存在——先在任务 6 建降级桩再填真实现（计划已注明）。
2. 任务 13 路由实现以 `create_app` 闭包为准，测试通过 monkeypatch `m.get_store`/`m.get_sandbox_root`/`m._default_db` 注入临时目录；若实现者改用模块级 `routes/api.py`，保持行为一致即可。
3. `mcp` SDK 的 `StdioServerParameters` 字段（command/args/env/cwd）需以安装的 `mcp` 版本为准，实现任务 8 时先 `python -c "from mcp.client.stdio import StdioServerParameters; help(StdioServerParameters)"` 核对签名。




