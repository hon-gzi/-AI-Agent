from app.agent.tools import build_registry, ALL_TOOL_NAMES


def test_all_required_tools_present():
    expected = {"list_dir", "read_file", "search_content", "write_file", "bash",
                "search_rss", "web_search", "finish"}
    assert expected == set(ALL_TOOL_NAMES)


def test_build_registry_gives_handlers(tmp_sandbox):
    reg = build_registry(tmp_sandbox)
    assert set(reg.keys()) == set(ALL_TOOL_NAMES)
    r = reg["finish"]({"text": "done"})
    assert r["finish"] is True
