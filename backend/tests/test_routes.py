from fastapi.testclient import TestClient
from unittest import mock


def _app(tmp_sandbox):
    import app.main as m
    app = m.create_app(settings=_settings(tmp_sandbox))
    return app


def _settings(root):
    from types import SimpleNamespace
    from pathlib import Path
    return SimpleNamespace(llm_api_key="k", llm_base_url="u", llm_model="m",
                           rss_feeds=[], daily_run_hour=8, daily_run_minute=0,
                           sandbox_root=Path(root))


def test_trigger_and_briefing_list(tmp_sandbox):
    app = _app(tmp_sandbox)
    with TestClient(app) as c:
        with mock.patch("app.main.run_agent_once", return_value={"status": "ok", "date": "2026-09-18", "briefing_path": str(tmp_sandbox/"briefings/2026-09-18.md"), "content": "今日简报"}):
            r = c.post("/api/trigger")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        # 触发后写入了简报文件
        p = tmp_sandbox / "briefings" / "2026-09-18.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("今日简报", encoding="utf-8")
        lst = c.get("/api/briefings")
        assert lst.status_code == 200
        items = lst.json()["items"]
        assert any(it["date"] == "2026-09-18" for it in items)


def test_briefing_detail(tmp_sandbox):
    app = _app(tmp_sandbox)
    p = tmp_sandbox / "briefings" / "2026-09-18.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("今日简报正文", encoding="utf-8")
    with TestClient(app) as c:
        r = c.get("/api/briefings/2026-09-18")
        assert r.status_code == 200
        assert "今日简报正文" in r.json()["content"]


def test_prefs_roundtrip(tmp_sandbox):
    app = _app(tmp_sandbox)
    with TestClient(app) as c:
        r = c.post("/api/prefs", json={"topics": ["AI", "LLM"], "keywords": ["OpenAI"]})
        assert r.status_code == 200
        got = c.get("/api/prefs").json()
        assert got["topics"] == ["AI", "LLM"]


def test_briefing_detail_bad_date(tmp_sandbox):
    """date 参数需校验 YYYY-MM-DD,拒绝路径注入(../ 等)。"""
    app = _app(tmp_sandbox)
    with TestClient(app) as c:
        r = c.get("/api/briefings/2026-09-18..%2f")  # 含非法字符
        assert r.status_code in (400, 404)
        r2 = c.get("/api/briefings/2026-9-8")  # 格式不合法
        assert r2.status_code == 400


def test_prefs_reject_non_string_items(tmp_sandbox):
    """topics/keywords 非字符串列表时返回 400。"""
    app = _app(tmp_sandbox)
    with TestClient(app) as c:
        r = c.post("/api/prefs", json={"topics": [1, 2]})
        assert r.status_code == 400


def test_briefing_detail_missing(tmp_sandbox):
    app = _app(tmp_sandbox)
    with TestClient(app) as c:
        r = c.get("/api/briefings/2026-01-01")
        assert r.status_code == 404
