"""RSS 抓取工具:抓取(内置或配置)RSS 源,落地沙箱,返回抓到的文件清单。失败降级不中断。"""
from pathlib import Path


def search_rss(topic: str, settings=None):
    from app.sources import rss
    try:
        feeds = (settings.rss_feeds if (settings and getattr(settings, "rss_feeds", None)) else None) or rss.DEFAULT_FEEDS
        root = _sandbox_root(settings)
        written = rss.fetch_all_feeds(feeds, root, topic=topic or None)
        if not written:
            return {"ok": True, "note": "未抓到匹配内容,可改用 web_search 或已有沙箱文件", "files": []}
        return {"ok": True, "files": written, "topic": topic}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"RSS 不可用: {e}", "files": []}


def _sandbox_root(settings):
    if settings is not None and getattr(settings, "sandbox_root", None):
        return Path(settings.sandbox_root)
    from app.config import load_settings
    return Path(load_settings().sandbox_root)
