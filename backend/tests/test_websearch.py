"""web_search 源测试:全部 mock `_call_mcp_search`,不触网,CI/无网可绿。

mock 形状对齐真实 mcp SDK 的 CallToolResult/TextContent(snake_case is_error、
content 为带 .type/.text 属性的对象),覆盖 JSON 结果解析与非 JSON 回退两条路径。"""
import json
from types import SimpleNamespace
from unittest import mock

from app.sources import websearch


def _result(content, is_error=False):
    """构造对齐真实 SDK 形状的工具结果:content 为带 .type/.text 属性的对象列表。"""
    return SimpleNamespace(
        is_error=is_error,
        content=[SimpleNamespace(type="text", text=t) for t in content],
    )


def test_web_search_degrades_when_unavailable():
    with mock.patch.object(websearch, "_call_mcp_search", side_effect=RuntimeError("mcp down")):
        res = websearch.search("AI news", limit=3)
    assert res["ok"] is False
    assert "降级" in res["note"]
    assert "results" not in res or res["results"] == []


def test_web_search_is_error_degrades():
    with mock.patch.object(websearch, "_call_mcp_search", return_value=_result([], is_error=True)):
        res = websearch.search("AI news", limit=3)
    assert res["ok"] is False
    assert "降级" in res["note"]


def test_web_search_parses_json_results():
    """mock 返回真实 open-websearch 的 JSON text block(results 非空),
    断言 search 解析出可读条目(标题/链接)而非原始 JSON 行。"""
    payload = json.dumps({
        "query": "AI news",
        "results": [
            {"title": "Result A", "url": "https://a.example", "description": "About A"},
            {"title": "Result B", "url": "https://b.example", "description": "About B"},
        ],
    })
    with mock.patch.object(websearch, "_call_mcp_search", return_value=_result([payload])):
        res = websearch.search("AI news", limit=3)
    assert res["ok"] is True
    assert res["results"] == [
        "Result A (https://a.example) — About A",
        "Result B (https://b.example) — About B",
    ]
    # 拿到的是可读条目,不是原始 JSON 源码行
    assert '{"query"' not in res["results"][0]


def test_web_search_falls_back_to_lines_when_not_json():
    """json.loads 失败(非 JSON),回退按非空行切分。"""
    with mock.patch.object(websearch, "_call_mcp_search",
                           return_value=_result(["plain line A", "", "plain line B"])):
        res = websearch.search("AI news", limit=3)
    assert res["ok"] is True
    assert res["results"] == ["plain line A", "plain line B"]
