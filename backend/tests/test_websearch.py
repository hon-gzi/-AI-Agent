from unittest import mock
from app.sources import websearch


def test_web_search_degrades_when_unavailable():
    with mock.patch.object(websearch, "_call_mcp_search", side_effect=RuntimeError("mcp down")):
        res = websearch.search("AI news", limit=3)
    assert res["ok"] is False
    assert "降级" in res["note"]


def test_web_search_returns_items():
    class R:
        isError = False
        content = [{"type": "text", "text": "1. result A\n2. result B"}]

    # search() 同时兼容真实 mcp SDK 的 TextContent(有 .type/.text 属性)与 dict,
    # 故此处 mock 用 dict content block,解析逻辑需覆盖两种形态。
    with mock.patch.object(websearch, "_call_mcp_search", return_value=R()):
        res = websearch.search("AI news", limit=3)
    assert res["ok"] is True
    assert "result A" in res["results"][0]
