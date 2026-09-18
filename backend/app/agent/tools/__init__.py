from app.agent.tools.files import FileTools
from app.agent.tools.bash import BashTool
from app.agent.tools.finish import finish
from app.agent.tools import rss_tool, websearch


def build_registry(sandbox_root, settings=None, llm=None):
    """返回 {tool_name: handler}。handler 接受 LLM 给的参数字典,返回可 JSON 序列化结果。
    文件类工具统一包一层:异常也转成 {"ok": False, "error": ...} 回传 LLM,不中断循环。"""
    ft = FileTools(sandbox_root)
    bt = BashTool(sandbox_root)

    def wrap(fn, *a, **k):
        try:
            return {"ok": True, "result": fn(*a, **k)}
        except Exception as e:
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


def _fn(name, desc, props, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required or []},
        },
    }


def tool_schemas():
    """OpenAI tools 数组(供 LLM 注册)。"""
    return [
        _fn("list_dir", "列出沙箱目录下的文件与子目录",
            {"path": {"type": "string", "description": "相对沙箱根的路径"}}, ["path"]),
        _fn("read_file", "读取沙箱内文件全文",
            {"path": {"type": "string", "description": "相对沙箱根的文件路径"}}, ["path"]),
        _fn("search_content", "在沙箱目录内按关键词全文检索,返回命中文件与行",
            {"keyword": {"type": "string", "description": "要检索的关键词"},
             "dir": {"type": "string", "description": "检索起始目录,相对沙箱根"}}, ["keyword"]),
        _fn("write_file", "写入沙箱内文件(简报/草稿),自动建父目录",
            {"path": {"type": "string", "description": "相对沙箱根的文件路径"},
             "content": {"type": "string", "description": "要写入的文件全文"}}, ["path", "content"]),
        _fn("bash", "在沙箱内执行白名单只读命令(仅 grep/cat/ls 等,拒绝危险命令)",
            {"command": {"type": "string", "description": "单个白名单只读命令,禁止 shell 元字符"}},
            ["command"]),
        _fn("search_rss", "抓取指定话题的 RSS 新闻并落地沙箱,返回条目摘要",
            {"topic": {"type": "string", "description": "话题名或过滤词,可省略"}}, []),
        _fn("web_search", "联网搜索(open-webSearch,免 key),返回结果列表",
            {"query": {"type": "string", "description": "搜索查询词"},
             "limit": {"type": "integer", "description": "返回条数上限"}}, ["query"]),
        _fn("finish", "将最终简报全文放入 text 后结束任务",
            {"text": {"type": "string", "description": "最终简报全文(必须为完整正文,不可为空/占位)"}},
            ["text"]),
    ]
