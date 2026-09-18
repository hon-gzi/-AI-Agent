def finish(args):
    """结束 ReAct 循环并产出最终简报文本。"""
    return {"finish": True, "text": (args or {}).get("text", "")}
