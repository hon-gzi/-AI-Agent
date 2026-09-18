"""联网搜索源:经官方 mcp SDK 的 stdio 通道起 open-webSearch(免 key/免注册/本地运行),
调其 `search` 工具取网页搜索结果。任何异常(网络受限、npm 不可用、MCP 起不来)都降级为
"仅 RSS",不中断 ReAct 循环。"""
import asyncio
import os
import platform

_ENGINE = os.getenv("WEBSEARCH_ENGINE", "duckduckgo")
_TIMEOUT = 30


def _stdio_command():
    """Windows 下 npx 实为 npx.cmd,需经 cmd /c 调起;POSIX 直接 npx。
    返回 [command, *args] 两段,便于传给 StdioServerParameters。"""
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
    """联网搜索入口;任何异常都降级为仅 RSS,不中断 Agent。"""
    try:
        raw = _call_mcp_search(query, limit)
        texts = [t for t in (_block_text(b) for b in _content(raw)) if t]
        joined = "\n".join(texts)
        if _is_error(raw):
            return {"ok": False, "note": "搜索出错,已降级为仅 RSS", "results": []}
        results = [line for line in joined.splitlines() if line.strip()][:limit]
        return {"ok": True, "results": results, "raw": joined}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "note": f"搜索不可用({e}),已降级为仅 RSS", "results": []}
