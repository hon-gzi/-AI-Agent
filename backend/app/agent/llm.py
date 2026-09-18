"""LLM 客户端:OpenAI 兼容的 function-calling(ReAct)循环。

工具调用顺序由 LLM 决定;本模块只负责把 tool_calls 分发给 handler、
把结果回写进 messages,直到 LLM 不再调工具、finish 真正结束或达到 max_steps。
结束判定依赖 finish handler 的结果(result.get("finish")),与任务 6 的 finish
语义一致:空 text 不结束。
"""
import json

from openai import OpenAI


class LLMClient:
    def __init__(self, client, model, registry, max_steps=20, timeout=120):
        self.client = client          # OpenAI 实例(可注入 mock,只需有 .chat)
        self.model = model
        self.registry = registry      # {tool_name: handler(args_dict) -> dict}
        self.max_steps = max(max_steps, 1)
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings, registry, max_steps=20, timeout=120):
        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        return cls(client, model=settings.llm_model, registry=registry,
                   max_steps=max_steps, timeout=timeout)

    def _tools_payload(self):
        from app.agent.tools import tool_schemas
        return tool_schemas()

    def _exec_tool_call(self, tc, msgs):
        """执行单个 tool_call,把结果回写 msgs;返回 (result, finished)。

        finished=True 表示 finish handler 判定真正结束(finish 为 True)。"""
        name = tc.function.name
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        handler = self.registry.get(name)
        if handler is None:
            result = {"ok": False, "error": f"未知工具: {name}"}
        else:
            try:
                result = handler(args)
            except Exception as e:  # 工具异常回传 LLM,不中断循环
                result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        finished = bool(result.get("finish"))
        msgs.append({"role": "tool", "tool_call_id": tc.id,
                     "content": json.dumps(result, ensure_ascii=False)})
        return result, finished

    def run(self, system, user, max_steps=None):
        steps = max(1, self.max_steps if max_steps is None else max_steps)
        msgs = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        final_text = None
        stopped_by = "max_steps"
        consumed = 0
        for step in range(steps):
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs, tools=self._tools_payload(),
                timeout=self.timeout,
            )
            consumed = step + 1
            m = resp.choices[0].message
            # LLM 不再调工具:以当前文本为最终输出结束
            if not m.tool_calls:
                final_text = m.content or ""
                stopped_by = "finish"
                break
            msgs.append({
                "role": "assistant",
                "content": m.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name,
                                  "arguments": tc.function.arguments}}
                    for tc in m.tool_calls
                ],
            })
            for tc in m.tool_calls:
                result, finished = self._exec_tool_call(tc, msgs)
                if finished:
                    # finish handler 返回 finish=True:取其 text 为最终输出
                    final_text = (result.get("text") or "").strip() or None
                    stopped_by = "finish"
                    break
            if stopped_by == "finish":
                break
        return {"final_text": final_text, "stopped_by": stopped_by, "steps": consumed}
