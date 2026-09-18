"""RSS 抓取工具:抓取(内置或配置)RSS 源,落地沙箱,返回抓到的文件清单。失败降级不中断。

调用方应传入 Settings(至少带 sandbox_root);settings 为 None 时不触网、不读真实
.env/.env 密钥、不污染真实沙箱目录,直接返回显式错误以便测试/CI 用临时 settings 隔离。
"""
from pathlib import Path


def search_rss(topic: str, settings=None):
    from app.sources import rss
    # 缺 settings 时不做隐式 load_settings()(避免触网/读真实密钥/污染数据目录)
    if settings is None or not getattr(settings, "sandbox_root", None):
        return {"ok": False, "error": "缺少 settings(应传入带 sandbox_root 的 Settings)", "files": []}
    try:
        feeds = getattr(settings, "rss_feeds", None) or rss.DEFAULT_FEEDS
        root = Path(settings.sandbox_root)
        written = rss.fetch_all_feeds(feeds, root, topic=topic or None)
        if not written:
            return {"ok": True, "note": "未抓到匹配内容,可改用 web_search 或已有沙箱文件", "files": []}
        return {"ok": True, "files": written, "topic": topic}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"RSS 不可用: {e}", "files": []}
