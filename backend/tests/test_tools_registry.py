from json import dumps

from app.agent.tools import build_registry, ALL_TOOL_NAMES, tool_schemas


def test_all_required_tools_present():
    expected = {"list_dir", "read_file", "search_content", "write_file", "bash",
                "search_rss", "web_search", "finish"}
    assert expected == set(ALL_TOOL_NAMES)


def test_build_registry_gives_handlers(tmp_sandbox):
    reg = build_registry(tmp_sandbox)
    assert set(reg.keys()) == set(ALL_TOOL_NAMES)
    r = reg["finish"]({"text": "done"})
    assert r["finish"] is True


def test_finish_empty_text_does_not_end(tmp_sandbox):
    reg = build_registry(tmp_sandbox)
    r = reg["finish"]({"text": "   "})
    assert r["finish"] is False
    assert "不能为空" in r["error"]


def test_finish_valid_text_ends(tmp_sandbox):
    reg = build_registry(tmp_sandbox)
    r = reg["finish"]({"text": "今日简报正文"})
    assert r["finish"] is True
    assert r["text"] == "今日简报正文"


def test_all_handlers_return_json_serializable(tmp_sandbox):
    """契约:任意 handler 喂合法参数,返回值都能 json.dumps。"""
    reg = build_registry(tmp_sandbox)
    cases = {
        "list_dir": {"path": "."},
        "read_file": {"path": "a.txt"},
        "search_content": {"keyword": "x", "dir": "."},
        "write_file": {"path": "a.txt", "content": "c"},
        "bash": {"command": "echo hi"},
        "search_rss": {"topic": "AI"},
        "web_search": {"query": "AI"},
        "finish": {"text": "ok"},
    }
    for name, args in cases.items():
        dumps(reg[name](args))  # 不抛异常即通过


def test_lambda_missing_args_is_caught(tmp_sandbox):
    """缺参由 wrap 兜住,返回 dict 而非抛异常。"""
    reg = build_registry(tmp_sandbox)
    r = reg["write_file"]({})  # 缺 path,空路径经 Sandbox.resolve 被拒
    assert isinstance(r, dict)
    assert r["ok"] is False


def test_tool_schemas_serializable_and_complete():
    schemas = tool_schemas()
    dumps(schemas)
    names = {s["function"]["name"] for s in schemas}
    assert names == set(ALL_TOOL_NAMES)
