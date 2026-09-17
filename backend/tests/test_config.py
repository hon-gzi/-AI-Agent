from app.config import PROJECT_ROOT, Settings, load_settings


def test_load_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://x/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("SANDBOX_ROOT", str(tmp_path))
    s = load_settings()
    assert s.llm_api_key == "k"
    assert s.llm_model == "m"


def test_daily_defaults(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://x/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    s = load_settings()
    assert s.daily_run_hour == 8
    assert s.daily_run_minute == 0


def test_sandbox_root_resolves_relative(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://x/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("SANDBOX_ROOT", "backend/data/sandbox")
    s = load_settings()
    assert s.sandbox_root.is_absolute()
    assert s.sandbox_root.is_relative_to(PROJECT_ROOT / "backend")
    assert s.sandbox_root == PROJECT_ROOT / "backend" / "data" / "sandbox"


def test_sandbox_root_absolute_passthrough(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://x/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("SANDBOX_ROOT", str(tmp_path))
    s = load_settings()
    assert s.sandbox_root == tmp_path


def test_settings_has_all_fields():
    s = Settings(llm_api_key="", llm_base_url="", llm_model="")
    assert s.rss_feeds == []
    assert s.daily_run_hour == 8
    assert s.daily_run_minute == 0
    assert s.sandbox_root == PROJECT_ROOT / "backend" / "data" / "sandbox"
