"""API 路由:历史简报、手动触发、偏好存取。

路由与 main.create_app 解耦:`build_router(settings, prefs_state, run_agent_once)`
接受可注入的依赖,便于测试打桩 `app.main.run_agent_once` 与注入 settings。"""
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def build_router(settings, prefs_state, run_agent_once):
    """构造 APIRouter,prefix=/api。

    参数:
      settings: 已注入的 settings(避免读真实 .env);
      prefs_state: 可变 dict,初版偏好的内存态;
      run_agent_once: trigger 路由调用的 Agent 入口(测试中为打桩后的引用)。
    """
    router = APIRouter(prefix="/api")
    briefings_dir = Path(settings.sandbox_root) / "briefings"

    @router.get("/briefings")
    def list_briefings():
        briefings_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for f in sorted(briefings_dir.glob("*.md"), reverse=True):
            items.append({"date": f.stem, "path": str(f),
                         "generated_at": f.stat().st_mtime})
        return {"items": items}

    @router.get("/briefings/{date}")
    def get_briefing(date: str):
        # 校验 YYYY-MM-DD,拒绝路径注入(../、.. 等)
        if not _DATE_RE.match(date):
            raise HTTPException(400, "date 须为 YYYY-MM-DD")
        f = briefings_dir / f"{date}.md"
        if not f.exists():
            raise HTTPException(404, f"简报不存在: {date}")
        return {"date": date, "content": f.read_text(encoding="utf-8")}

    @router.post("/trigger")
    def trigger():
        from app.agent.llm import LLMClient
        from app.agent.tools import build_registry
        registry = build_registry(settings.sandbox_root, settings=settings)
        client = LLMClient.from_settings(settings, registry)
        return run_agent_once(client, settings=settings, prefs=dict(prefs_state),
                              date=None)

    @router.get("/prefs")
    def get_prefs():
        return dict(prefs_state)

    @router.post("/prefs")
    def set_prefs(payload: dict):
        topics = payload.get("topics", [])
        keywords = payload.get("keywords", [])
        if not (isinstance(topics, list) and all(isinstance(t, str) for t in topics)):
            raise HTTPException(400, "topics/keywords 须为字符串列表")
        if not (isinstance(keywords, list) and all(isinstance(k, str) for k in keywords)):
            raise HTTPException(400, "topics/keywords 须为字符串列表")
        prefs_state.clear()
        prefs_state.update({"topics": topics, "keywords": keywords})
        return dict(prefs_state)

    return router
