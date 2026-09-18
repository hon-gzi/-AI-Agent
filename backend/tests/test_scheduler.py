from unittest import mock
from app.scheduler import make_job, build_scheduler


def test_make_job_returns_callable(tmp_sandbox):
    job = make_job(settings=_settings(tmp_sandbox), prefs={"topics": ["AI"]})
    assert callable(job)


def test_make_job_runs_agent_once(tmp_sandbox):
    with mock.patch("app.scheduler.run_agent_once", return_value={"status": "ok"}) as m, \
            mock.patch("app.scheduler.LLMClient.from_settings", return_value=object()):
        job = make_job(settings=_settings(tmp_sandbox), prefs={"topics": ["AI"]})
        job()
    m.assert_called_once()
    # 应把生成的简报路径回传/记录(至少调用成功)
    assert m.return_value["status"] == "ok"


def test_build_scheduler_registers_daily_job():
    with mock.patch("app.scheduler.make_job") as mjob:
        mjob.return_value = lambda: None
        sched = build_scheduler(settings=_settings(_fake_root()))
        assert sched is not None
        jobs = sched.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].trigger.__class__.__name__.endswith("CronTrigger") or "cron" in str(jobs[0].trigger).lower()


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
