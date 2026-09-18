import json
from types import SimpleNamespace

from app.agent.llm import LLMClient


def _msg(content=None, tool_calls=None):
    """构造一个 OpenAI 风格的 assistant message:有 .role/.content/.tool_calls。"""
    return SimpleNamespace(role="assistant", content=content, tool_calls=tool_calls)


def _tcall(name, args, tc_id="c1"):
    return SimpleNamespace(id=tc_id, type="function",
                           function=SimpleNamespace(name=name, arguments=json.dumps(args)))


class SeqClient:
    """假 OpenAI 客户端:chat.completions.create 按序返回预设 assistant message。

    每次调用记录 kwargs(便于断言 tools 是否传了);message 耗尽后若再调用则抛错,
    避免测试静默地拿到默认值。
    """

    def __init__(self, messages):
        self._msgs = list(messages)
        self.calls = []
        chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.chat = chat
        self.client = SimpleNamespace(chat=chat)

    def _create(self, **kw):
        self.calls.append(kw)
        if not self._msgs:
            raise AssertionError("seq client 消息耗尽,LLM 循环调用次数超出预设脚本")
        m = self._msgs.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=m)])


def _make_client(scripted):
    """把预设 message 列表包成 LoopClient(LLMClient 直接接受带 .chat 的对象)。"""
    c = SeqClient(scripted)
    return c


def test_loop_executes_tool_then_finishes():
    # LLM 先要 list_dir,看到结果后调 finish
    client = _make_client([
        _msg(None, [_tcall("list_dir", {"path": "."}, tc_id="1")]),
        _msg(None, [_tcall("finish", {"text": "final briefing text"}, tc_id="2")]),
    ])
    llm = LLMClient(client, model="m", registry={
        "list_dir": lambda a: {"ok": True, "result": ["f.txt"]},
        "finish": lambda a: {"finish": a.get("text", "").strip() != "", "text": a.get("text", "")},
    })
    out = llm.run(system="s", user="u", max_steps=10)
    assert out["final_text"] == "final briefing text"
    assert out["stopped_by"] == "finish"
    assert out["steps"] >= 2


def test_loop_stops_at_finish_tool():
    client = _make_client([
        _msg(None, [_tcall("finish", {"text": "done"}, tc_id="1")]),
    ])
    llm = LLMClient(client, model="m",
                    registry={"finish": lambda a: {"finish": a.get("text", "").strip() != "",
                                                   "text": a.get("text", "")}})
    out = llm.run(system="s", user="u")
    assert out["final_text"] == "done"
    assert out["stopped_by"] == "finish"


def test_finish_empty_text_does_not_stop(tmp_path):
    """与任务 6 finish 语义一致:handler 返回 finish=False 时循环不结束。"""
    client = _make_client([
        _msg(None, [_tcall("finish", {"text": "   "}, tc_id="1")]),
        _msg(None, [_tcall("finish", {"text": "补全的简报"}, tc_id="2")]),
    ])
    llm = LLMClient(client, model="m",
                    registry={"finish": lambda a: {"finish": a.get("text", "").strip() != "",
                                                   "text": a.get("text", "")}})
    out = llm.run(system="s", user="u")
    assert out["final_text"] == "补全的简报"
    assert out["stopped_by"] == "finish"


def test_max_steps_truncates():
    client = _make_client([
        _msg(None, [_tcall("list_dir", {"path": "."}, tc_id=str(i))]) for i in range(5)],
    )
    llm = LLMClient(client, model="m", registry={"list_dir": lambda a: {"ok": True, "result": []}})
    out = llm.run(system="s", user="u", max_steps=3)
    assert out["stopped_by"] == "max_steps"
    assert out["final_text"] is None
    assert out["steps"] == 3
    assert len(client.calls) == 3


def test_unknown_tool_error_reported_to_llm():
    client = _make_client([
        _msg(None, [_tcall("no_such_tool", {"x": 1}, tc_id="1")]),
        _msg(None, [_tcall("finish", {"text": "t"}, tc_id="2")]),
    ])
    llm = LLMClient(client, model="m",
                    registry={"finish": lambda a: {"finish": True, "text": a.get("text", "")}})
    out = llm.run(system="s", user="u")
    assert out["stopped_by"] == "finish"
    # 未知工具的结果回传给 LLM 的内容里应有错误标记
    tool_msgs = [c for c in client.calls]
    second_call_messages = tool_msgs[1]["messages"]
    tool_results = [m for m in second_call_messages if m["role"] == "tool"]
    assert any("未知工具" in m["content"] for m in tool_results)


def test_tool_exception_returned_not_raised():
    def boom(a):
        raise RuntimeError("kaboom")

    client = _make_client([
        _msg(None, [_tcall("list_dir", {"path": "."}, tc_id="1")]),
        _msg(None, [_tcall("finish", {"text": "t"}, tc_id="2")]),
    ])
    llm = LLMClient(client, model="m",
                    registry={"list_dir": boom,
                              "finish": lambda a: {"finish": True, "text": a.get("text", "")}})
    out = llm.run(system="s", user="u")  # 不抛异常
    assert out["stopped_by"] == "finish"
    second_call_messages = client.calls[1]["messages"]
    tool_results = [m for m in second_call_messages if m["role"] == "tool"]
    assert any("RuntimeError" in m["content"] for m in tool_results)


def test_no_tool_calls_yields_final_text():
    """LLM 第一轮直接给纯文本,不再调工具 → 结束。"""
    client = _make_client([
        _msg("pure text answer", None),
    ])
    llm = LLMClient(client, model="m", registry={})
    out = llm.run(system="s", user="u")
    assert out["final_text"] == "pure text answer"
    assert out["stopped_by"] == "finish"
    assert out["steps"] == 1


def test_tools_payload_passed_to_api():
    client = _make_client([_msg(None, [_tcall("finish", {"text": "t"}, tc_id="1")])])
    llm = LLMClient(client, model="m",
                    registry={"finish": lambda a: {"finish": True, "text": a.get("text", "")}})
    llm.run(system="s", user="u")
    kwargs = client.calls[0]
    assert "tools" in kwargs
    names = {t["function"]["name"] for t in kwargs["tools"]}
    assert "finish" in names
    assert kwargs["model"] == "m"


def test_finish_mid_round_backfills_placeholder_for_unexecuted_tool_calls():
    """一轮内 finish 出现在多个 tool_calls 中时,其后未执行的 tool_calls 也要补占位 tool 消息,
    保证 assistant 声明的每个 tool_call 都有对应 tool 消息(OpenAI 协议完整性)。"""
    client = _make_client([
        _msg(None, [
            _tcall("list_dir", {"path": "."}, tc_id="a"),
            _tcall("finish", {"text": "done"}, tc_id="b"),
            _tcall("write_file", {"path": "x", "content": "y"}, tc_id="c"),
        ]),
    ])
    llm = LLMClient(client, model="m", registry={
        "list_dir": lambda a: {"ok": True, "result": []},
        "finish": lambda a: {"finish": a.get("text", "").strip() != "", "text": a.get("text", "")},
        "write_file": lambda a: {"ok": True, "result": a},
    })
    out = llm.run(system="s", user="u")
    assert out["stopped_by"] == "finish"
    assert out["final_text"] == "done"
    assert out["steps"] == 1


def test_finish_mid_round_no_dangling_tool_call_messages():
    """验证 finish 后未执行 tool_calls 被补占位:借助 SpyRegistry 记录被执行的 handler 名。"""
    executed = []

    def reg_for(name):
        def _h(args):
            if name == "finish":
                return {"finish": True, "text": "done"}
            executed.append(name)
            return {"ok": True}
        return _h

    client = _make_client([
        _msg(None, [
            _tcall("list_dir", {"path": "."}, tc_id="a"),
            _tcall("finish", {"text": "done"}, tc_id="b"),
            _tcall("write_file", {"path": "x", "content": "y"}, tc_id="c"),
        ]),
    ])
    llm = LLMClient(client, model="m",
                    registry={"list_dir": reg_for("list_dir"),
                              "finish": reg_for("finish"),
                              "write_file": reg_for("write_file")})
    out = llm.run(system="s", user="u")
    assert out["stopped_by"] == "finish"
    assert out["final_text"] == "done"
    # write_file 在 finish 之后,不应被执行
    assert "write_file" not in executed
    assert "list_dir" in executed


def test_bad_arguments_json_falls_back_to_empty_dict():
    """arguments 非法 JSON 时不崩,按 {} 处理(handler 内部自行兜缺参)。"""
    bad_tc = SimpleNamespace(id="1", type="function",
                             function=SimpleNamespace(name="list_dir", arguments="{bad json"))
    client = _make_client([
        _msg(None, [bad_tc]),
        _msg(None, [_tcall("finish", {"text": "t"}, tc_id="2")]),
    ])
    llm = LLMClient(client, model="m",
                    registry={"list_dir": lambda a: {"ok": True, "echo": a},
                              "finish": lambda a: {"finish": True, "text": a.get("text", "")}})
    out = llm.run(system="s", user="u")
    assert out["stopped_by"] == "finish"
    second_messages = client.calls[1]["messages"]
    tool_results = [m for m in second_messages if m["role"] == "tool"]
    assert json.loads(tool_results[0]["content"]) == {"ok": True, "echo": {}}
