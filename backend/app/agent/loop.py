"""ReAct 入口:按订阅偏好 + 日期生成一份 AI 新闻简报并落到沙箱。

工具顺序由 LLM 决定;本模块只负责组装 prompt、驱动 LLMClient 循环、落盘。
落盘策略(保持 DRY):优先信任 LLM 的 write_file 产物——
若 briefings/<date>.md 已存在且非空,直接采用;否则才把 finish 的 final_text 落盘。
"""
import json
from datetime import date as _date
from pathlib import Path

from app.agent.llm import LLMClient
from app.agent.sandbox import Sandbox
from app.agent.tools import build_registry
from app.config import load_settings


def _system_prompt(prefs, date_str):
    return (
        "你是每日 AI 新闻助手。请基于订阅偏好生成今日 AI 新闻简报。\n"
        f"订阅偏好:{json.dumps(prefs or {}, ensure_ascii=False)}\n"
        f"当前日期:{date_str}\n"
        "可用工具:search_rss(抓 RSS 落地沙箱)、web_search(联网搜索,可能降级)、"
        "list_dir/read_file/search_content(读沙箱已抓内容)、bash(只读命令)、"
        "write_file(把简报写入沙箱 briefings/ 目录)、finish(结束并输出最终简报全文)。\n"
        "流程建议:先 search_rss 抓内容 → list_dir/search_content/read_file 挑取 → "
        "write_file 写出简报 → finish 输出最终简报全文。工具顺序由你决定。"
    )


def _briefing_path(sb: Sandbox, date_str: str) -> Path:
    """沙箱内 briefings/<date>.md 绝对路径(经 Sandbox.resolve 校验,不越界)。"""
    target = sb.resolve(f"briefings/{date_str}.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def run_agent_once(client_or_llm, settings=None, prefs=None, date=None, max_steps=20):
    """手动触发(任务 13 API)与定时任务(任务 12)共用的唯一 Agent 入口。

    参数:
      client_or_llm: 已构造的 LLMClient,或裸 OpenAI 兼容 client(有 .chat 属性)。
      settings: 缺失时 load_settings() 读取(测试中 mock 掉,避免读真实 .env)。
      prefs: 订阅偏好 dict,拼进 system prompt。
      date: 简报日期(YYYY-MM-DD),缺省取今天。

    返回:
      {"status": "ok", "date", "briefing_path", "content", "stopped_by"}
      或 {"status": "no_output", "date", "stopped_by"}(LLM 结束时无有效文本且沙箱无已有简报)。
    """
    settings = settings or load_settings()
    date_str = date or _date.today().isoformat()
    registry = build_registry(settings.sandbox_root, settings=settings)
    if isinstance(client_or_llm, LLMClient):
        llm = client_or_llm
    else:
        llm = LLMClient(client_or_llm, model=settings.llm_model,
                        registry=registry, max_steps=max_steps)

    out = llm.run(system=_system_prompt(prefs, date_str), user="请生成今日 AI 新闻简报。")
    text = (out.get("final_text") or "").strip()

    sb = Sandbox(settings.sandbox_root)
    target = _briefing_path(sb, date_str)

    # 优先信任 LLM 的 write_file 产物:文件已存在且非空 → 直接采用(不覆盖)
    if target.exists() and target.stat().st_size > 0:
        content = target.read_text(encoding="utf-8")
    else:
        content = text
        if content:
            target.write_text(content, encoding="utf-8")

    if not content:
        return {"status": "no_output", "date": date_str, "stopped_by": out.get("stopped_by")}
    return {"status": "ok", "date": date_str, "briefing_path": str(target),
            "content": content, "stopped_by": out.get("stopped_by")}
