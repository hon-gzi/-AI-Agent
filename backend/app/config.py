import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# config.py 位于 <root>/backend/app/config.py,故 parents[2] 即项目根 <root>
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# sanity 校验:层级假设成立时 <root>/backend 应存在,否则说明文件被放错位置
assert (PROJECT_ROOT / "backend").is_dir(), f"PROJECT_ROOT sanity check failed: {PROJECT_ROOT}"

DEFAULT_SANDBOX = "backend/data/sandbox"


def _to_int(name: str, default: int, lo: int, hi: int) -> int:
    """读取环境变量并解析为 int,合法范围 [lo, hi];非法或越界时回退 default 并告警。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        print(f"[config] WARNING: {name}={raw!r} 不是合法整数,回退默认 {default}")
        return default
    if not lo <= value <= hi:
        print(f"[config] WARNING: {name}={raw!r} 超出范围 [{lo}, {hi}],回退默认 {default}")
        return default
    return value


@dataclass
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    rss_feeds: list = field(default_factory=list)
    daily_run_hour: int = 8
    daily_run_minute: int = 0
    sandbox_root: Path = PROJECT_ROOT / Path(DEFAULT_SANDBOX)


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    sandbox = os.getenv("SANDBOX_ROOT", DEFAULT_SANDBOX)
    sandbox_path = Path(sandbox)
    sandbox_root = sandbox_path if sandbox_path.is_absolute() else PROJECT_ROOT / sandbox_path
    rss_raw = os.getenv("RSS_FEEDS", "").strip()
    rss_feeds = [u.strip() for u in rss_raw.split(",") if u.strip()]
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        rss_feeds=rss_feeds,
        daily_run_hour=_to_int("DAILY_RUN_HOUR", 8, 0, 23),
        daily_run_minute=_to_int("DAILY_RUN_MINUTE", 0, 0, 59),
        sandbox_root=sandbox_root,
    )
