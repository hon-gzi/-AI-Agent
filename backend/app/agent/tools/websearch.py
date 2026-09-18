"""联网搜索工具:经 mcp SDK 调 open-webSearch(免 key)的 search 工具。
失败/不可用时返回降级提示,由 LLM 改用 RSS/沙箱已有内容,不中断流程。"""
from app.sources import websearch as _ws


def web_search(query: str, limit: int = 5):
    res = _ws.search(query=query, limit=limit)
    return {"ok": res["ok"], "results": res.get("results", []), "note": res.get("note", "")}
