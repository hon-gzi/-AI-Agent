import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    rss_feeds: list = field(default_factory=list)
    daily_run_hour: int = 8
    daily_run_minute: int = 0
    sandbox_root: Path = PROJECT_ROOT / "backend" / "data" / "sandbox"


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    sandbox = os.getenv("SANDBOX_ROOT", "backend/data/sandbox")
    sandbox_path = Path(sandbox)
    sandbox_root = sandbox_path if sandbox_path.is_absolute() else PROJECT_ROOT / sandbox_path
    rss_raw = os.getenv("RSS_FEEDS", "").strip()
    rss_feeds = [u.strip() for u in rss_raw.split(",") if u.strip()]
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        rss_feeds=rss_feeds,
        daily_run_hour=int(os.getenv("DAILY_RUN_HOUR", "8")),
        daily_run_minute=int(os.getenv("DAILY_RUN_MINUTE", "0")),
        sandbox_root=sandbox_root,
    )
