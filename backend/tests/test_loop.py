import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.agent import loop


def _make_seq_client(*msgs):
    """构造假 OpenAI 客户端:chat.completions.create 按序返回预设 assistant message。

    client.msgs 是剩余消息的可变列表,测试可追加;client.calls 记录每次 create 的 kwargs。
    """
    remaining = list(msgs)
    calls = []

    def _create(**kw):
        calls.append(kw)
        if not remaining:
            raise AssertionError("seq client 消息耗尽")
        m = remaining.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=m)])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    fake.calls = calls
    fake.msgs = remaining
    return fake


def _msg_with_tool_calls(tool_calls):
    return SimpleNamespace(role="assistant", content=None, tool_calls=tool_calls)


def _tc(tc_id, name, args):
    return SimpleNamespace(id=tc_id, type="function",
                           function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def _settings(root):
    return SimpleNamespace(llm_api_key="k", llm_base_url="u", llm_model="m",
                           rss_feeds=[], daily_run_hour=8, daily_run_minute=0,
                           sandbox_root=Path(root))


def test_run_agent_once_generates_and_persists(tmp_sandbox, monkeypatch):
    """LLM 先 write_file 把简报写进沙箱,再 finish 输出全文;run_agent_once 返回 ok 且文件落盘。"""
    write_msg = _msg_with_tool_calls([
        _tc("1", "write_file", {"path": "briefings/2026-09-18.md", "content": "# 简报\n- 条目A"}),
    ])
    finish_msg = _msg_with_tool_calls([
        _tc("2", "finish", {"text": "# 简报\n- 条目A"}),
    ])
    fake_client = _make_seq_client(write_msg, finish_msg)

    settings = _settings(tmp_sandbox)
    with mock.patch.object(loop, "load_settings", return_value=settings):
        res = loop.run_agent_once(fake_client, settings=settings,
                                  prefs={"topics": ["AI"], "keywords": ["LLM"]},
                                  date="2026-09-18")
    assert res["status"] == "ok"
    p = tmp_sandbox / "briefings" / "2026-09-18.md"
    assert p.exists()
    assert "条目A" in p.read_text(encoding="utf-8")
    assert "条目A" in res["content"]
    assert res["date"] == "2026-09-18"


def test_run_agent_once_no_output(tmp_sandbox):
    """finish text 为空(handler 返回 finish=False)→ LLM 后续也没再产出 → no_output。"""
    client = _make_seq_client(
        _msg_with_tool_calls([_tc("1", "finish", {"text": ""})]),
        # 没有更多消息,LLMClient 会耗尽脚本 → 这里直接让 finish 后 LLM 给出纯空文本
    )
    # 追加一条无 tool_calls 的空 message,使循环自然结束
    client.msgs.append(SimpleNamespace(role="assistant", content="", tool_calls=None))
    settings = _settings(tmp_sandbox)
    with mock.patch.object(loop, "load_settings", return_value=settings):
        res = loop.run_agent_once(client, settings=settings, date="2026-09-18")
    assert res["status"] == "no_output"
    assert not (tmp_sandbox / "briefings" / "2026-09-18.md").exists()


def test_run_agent_once_trusts_existing_briefing_file(tmp_sandbox):
    """LLM 已用 write_file 写过非空简报时,loop 信任该产物,finish 文本仅作 content 返回。"""
    bdir = tmp_sandbox / "briefings"
    bdir.mkdir()
    existing = bdir / "2026-09-18.md"
    existing.write_text("# 已有简报\n- 来自 write_file", encoding="utf-8")

    write_msg = _msg_with_tool_calls([
        _tc("1", "write_file", {"path": "briefings/2026-09-18.md",
                                 "content": "# 已有简报\n- 来自 write_file"}),
    ])
    finish_msg = _msg_with_tool_calls([
        _tc("2", "finish", {"text": "# 已有简报\n- 来自 write_file"}),
    ])
    fake_client = _make_seq_client(write_msg, finish_msg)
    settings = _settings(tmp_sandbox)
    with mock.patch.object(loop, "load_settings", return_value=settings):
        res = loop.run_agent_once(fake_client, settings=settings, date="2026-09-18")
    assert res["status"] == "ok"
    # 文件内容仍是 LLM write_file 写入的(loop 不覆盖重复内容)
    assert existing.read_text(encoding="utf-8") == "# 已有简报\n- 来自 write_file"
    assert res["briefing_path"] == str(existing)


def test_run_agent_once_accepts_llmclient_instance(tmp_sandbox):
    """client_or_llm 已是 LLMClient 时直接使用,不包一层。"""
    from app.agent.llm import LLMClient
    llm = LLMClient(_make_seq_client(
        _msg_with_tool_calls([_tc("1", "finish", {"text": "直接简报"})]),
    ), model="m",
        registry={"finish": lambda a: {"finish": bool(a.get("text", "").strip()),
                                       "text": a.get("text", "")}})
    settings = _settings(tmp_sandbox)
    with mock.patch.object(loop, "load_settings", return_value=settings):
        res = loop.run_agent_once(llm, settings=settings, date="2026-09-18")
    assert res["status"] == "ok"
    assert res["content"] == "直接简报"
    p = tmp_sandbox / "briefings" / "2026-09-18.md"
    assert p.exists()
