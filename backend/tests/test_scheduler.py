from unittest import mock
from app.scheduler import make_job, build_scheduler


def test_make_job_returns_callable(tmp_sandbox):
    job = make_job(settings=_settings(tmp_sandbox), prefs={"topics": ["AI"]})
    assert callable(job)


def test_make_job_runs_agent_once(tmp_sandbox):
    with mock.patch("app.scheduler.run_agent_once", return_value={"status": "ok"}) as m, \
            mock.patch("app.scheduler.LLMClient.from_settings", return_value=object()):
        job = make_job(settings=_settings(tmp_sandbox), prefs={"topics": ["AI"]})
        res = job()
    m.assert_called_once()
    assert res["status"] == "ok"


def test_make_job_propagates_exception_after_logging(tmp_sandbox, caplog):
    """run_agent_once 抛异常时,job 记录异常并向上抛(交回 APScheduler 记日志),不静默吞掉。"""
    import logging
    with mock.patch("app.scheduler.LLMClient.from_settings", return_value=object()), \
            mock.patch("app.scheduler.run_agent_once", side_effect=RuntimeError("boom")), \
            caplog.at_level(logging.ERROR, logger="app.scheduler"):
        job = make_job(settings=_settings(tmp_sandbox), prefs={"topics": ["AI"]})
        try:
            job()
            assert False, "should raise"
        except RuntimeError:
            pass
    assert any("daily agent run failed" in r.getMessage() for r in caplog.records if r.name == "app.scheduler")


def test_build_scheduler_registers_daily_job():
    with mock.patch("app.scheduler.make_job") as mjob:
        mjob.return_value = lambda: None
        sched = build_scheduler(settings=_settings(_fake_root()))
        jobs = sched.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "daily_ai_news"
        assert "cron" in str(jobs[0].trigger).lower() or jobs[0].trigger.__class__.__name__.endswith("CronTrigger")


def _settings(root):
    from types import SimpleNamespace
    from pathlib import Path
    return SimpleNamespace(llm_api_key="k", llm_base_url="u", llm_model="m",
                           rss_feeds=[], daily_run_hour=8, daily_run_minute=0,
                           sandbox_root=Path(root))


def _fake_root():
    import tempfile
    p = tempfile.mkdtemp()
    from pathlib import Path
    return p
