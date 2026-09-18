"""APScheduler 定时任务:每日定点跑 run_agent_once,与手动触发共用同一 Agent 入口。"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agent.loop import run_agent_once
from app.agent.llm import LLMClient
from app.agent.tools import build_registry

log = logging.getLogger(__name__)


def make_job(settings, prefs):
    """构造每日任务的 job 函数(返回 callable,不立即执行)。

    settings/prefs 在建 job 时固定;若需每次取最新 prefs,改读全局偏好(任务 13 提供)。"""
    def _job():
        registry = build_registry(settings.sandbox_root, settings=settings)
        client = LLMClient.from_settings(settings, registry)
        res = run_agent_once(client, settings=settings, prefs=prefs)
        log.info("daily agent run: %s", res.get("status"))
        return res
    return _job


def build_scheduler(settings, prefs=None):
    """构造并返回(未 start)的 BackgroundScheduler,注册每日任务。start 由 main.py 负责。"""
    sched = BackgroundScheduler()
    sched.add_job(
        make_job(settings, prefs),
        trigger=CronTrigger(hour=settings.daily_run_hour, minute=settings.daily_run_minute),
        id="daily_ai_news",
        replace_existing=True,
    )
    return sched
