"""联网搜索源:经官方 mcp SDK 的 stdio 通道起 open-webSearch(免 key/免注册/本地运行),
调其 `search` 工具取网页搜索结果。任何异常(网络受限、npm 不可用、MCP 起不来)都降级为
"仅 RSS",不中断 ReAct 循环。"""
import asyncio
import json
import os
import platform

_ENGINE = os.getenv("WEBSEARCH_ENGINE", "duckduckgo")
# 60s 是 "npx 冷启动拉取包 + 实际搜索" 的合并预算:实测单次冷启动可达 ~29s,
# 贴 30s 红线,故提到 60s 避免慢网/慢盘下正常搜索被误判为超时降级。
_TIMEOUT = 60


def _stdio_command():
    """Windows 下 npx 实为 npx.cmd,需经 cmd /c 调起;POSIX 直接 npx。
    返回 [command, *args] 两段,便于传给 StdioServerParameters。

    注:当前用 `open-websearch@latest` 每次可能触发 npx 解析/下载(冷启动慢)。
    可优化项:若已缓存,改用固定版本(如 `open-websearch@1.x.y`)可避免重复拉取 @latest。
    """
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


def _block_text(block):
    """content block 可能是 pydantic TextContent(有 .type/.text 属性),也可能是 dict。"""
    btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", "")
    if btype == "text":
        return block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
    return None


def _content(raw):
    """兼容真实 mcp CallToolResult(.content 为属性 list)与 mock 对象。"""
    content = raw.get("content") if isinstance(raw, dict) else getattr(raw, "content", None)
    return content if content is not None else []


def _is_error(raw):
    """真实 mcp CallToolResult 用 snake_case 的 is_error;mock/旧版可能用 isError。两者都查。"""
    err = raw.get("is_error") if isinstance(raw, dict) else getattr(raw, "is_error", None)
    if err is None:
        err = raw.get("isError") if isinstance(raw, dict) else getattr(raw, "isError", None)
    return bool(err)


def _parse_json_results(joined: str, limit: int):
    """open-websearch 的 text block 是 JSON 字符串(形如
    {"query":..., "results":[{"title","url","description"},...]}),先 json.loads 抽
    LLM 友好的条目;成功则返回可读条目列表,失败(非 JSON)返回 None 由调用方回退按行切分。"""
    try:
        data = json.loads(joined)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None
    items = []
    for r in results:
        if isinstance(r, dict):
            title = (r.get("title") or "").strip()
            url = (r.get("url") or "").strip()
            desc = (r.get("description") or r.get("snippet") or "").strip()
            line = title
            if url:
                line += f" ({url})" if line else url
            if desc:
                line += f" — {desc}" if line else desc
            items.append(line)
        elif isinstance(r, str):
            s = r.strip()
            if s:
                items.append(s)
    return items[:limit] if items else None


def _call_mcp_search(query: str, limit: int):
    """用官方 mcp SDK 的 stdio 通道起 open-webSearch,调其 search 工具,返回原始 tool result。

    延迟 import mcp(避免顶层拉起 SDK)。测试 mock 本函数即可隔离 MCP 不触网。"""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    cmd = _stdio_command()
    params = StdioServerParameters(command=cmd[0], args=cmd[1:], env=_env(), cwd=None)

    async def _run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await asyncio.wait_for(
                    session.call_tool("search", {"query": query, "limit": limit}),
                    timeout=_TIMEOUT,
                )

    return asyncio.run(_run())


def search(query: str, limit: int = 5) -> dict:
    """联网搜索入口;任何异常都降级为仅 RSS,不中断 Agent。

    结果解析优先把 open-websearch 的 JSON text block 抽成 LLM 友好的条目(标题/链接/摘要),
    非 JSON 才回退按非空行切分。不再对外透传原始 `raw`(无人使用,YAGNI)。"""
    try:
        raw = _call_mcp_search(query, limit)
        if _is_error(raw):
            return {"ok": False, "note": "搜索出错,已降级为仅 RSS", "results": []}
        texts = [t for t in (_block_text(b) for b in _content(raw)) if t]
        joined = "\n".join(texts)
        parsed = _parse_json_results(joined, limit)
        if parsed is not None:
            results = parsed
        else:
            results = [line for line in joined.splitlines() if line.strip()][:limit]
        return {"ok": True, "results": results}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "note": f"搜索不可用({e}),已降级为仅 RSS", "results": []}
