"""FastAPI 应用工厂:CORS、偏好存取、手动触发、历史简报、挂载定时任务。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.loop import run_agent_once
from app.routes.api import build_router
from app.scheduler import build_scheduler


def create_app(settings=None):
    from app.config import load_settings
    settings = settings or load_settings()

    app = FastAPI(title="每日 AI 新闻助手")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])

    # 初版偏好:内存态(任务 13 可升级为持久化)
    prefs_state = {"topics": [], "keywords": []}
    app.state.prefs = prefs_state
    app.state.settings = settings

    def _agent_entry(*a, **kw):
        # 延迟到调用时取 app.main.run_agent_once,使测试打桩生效
        import app.main as _m
        return _m.run_agent_once(*a, **kw)

    app.include_router(build_router(settings, prefs_state, _agent_entry))

    # 挂载定时任务(不 start;start 由 start_scheduler 单独调用,测试不触发)
    app.state.scheduler = build_scheduler(settings, prefs_state)
    return app


def start_scheduler(app):
    """由进程启动入口调用:真正 start 调度器。"""
    sched = getattr(app.state, "scheduler", None)
    if sched and not sched.running:
        sched.start()


# 模块级 app:供 `uvicorn app.main:app` 直接启动(工厂 create_app 仍用于测试/注入 settings)。
# create_app() 读 .env(测试环境无 .env 时 load_settings 已做默认兜底),import 侧效应可接受。
app = create_app()


if __name__ == "__main__":
    import uvicorn
    from app.config import load_settings
    application = create_app(load_settings())
    start_scheduler(application)
    uvicorn.run(application, host="0.0.0.0", port=8000)
