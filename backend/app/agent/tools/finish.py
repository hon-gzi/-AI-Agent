def finish(args):
    """结束 ReAct 循环并产出最终简报文本。
    若 text 为空/纯空白,不结束(返回 finish=False),让循环继续以便 LLM 补全简报。"""
    text = (args or {}).get("text", "") or ""
    if not text.strip():
        return {"finish": False, "error": "text 不能为空,请输出最终简报全文"}
    return {"finish": True, "text": text}
