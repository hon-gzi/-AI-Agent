"""RSS 源:抓取内置/配置的 RSS feed,解析后落地沙箱内文本文件。"""
import feedparser
from pathlib import Path
from datetime import date


DEFAULT_FEEDS = [
    "https://hnrss.org/frontpage",
    "https://arxiv.org/rss/cs.AI",
    "https://feeds.arxiv.org/arxiv/ai",  # 备用
]


def _get(entry, key, default=""):
    """兼容 feedparser entry(有 .get)与 SimpleNamespace(无 .get)。"""
    if hasattr(entry, "get"):
        return entry.get(key, default)
    return getattr(entry, key, default)


def fetch_one(url: str):
    """抓取单个 feed,返回 feedparser 结果;网络/解析异常抛错由调用方处理。"""
    resp = feedparser.parse(url)
    if resp.bozo and not resp.entries:
        raise RuntimeError(f"feed 解析失败: {url} {resp.bozo_exception}")
    return resp


def fetch_all_feeds(urls, sandbox_root, topic=None):
    """抓取并解析 RSS,每条落地为沙箱内文本文件,返回写入的相对文件名列表。"""
    sandbox_root = Path(sandbox_root)
    sandbox_root.mkdir(parents=True, exist_ok=True)
    written = []
    today = date.today().isoformat()
    for url in urls:
        try:
            feed = fetch_one(url)
        except Exception:
            continue  # 单源失败不影响整体
        feed_title = feed.feed.get("title", url) if hasattr(feed.feed, "get") else getattr(feed.feed, "title", url)
        lines = [f"# {feed_title} ({today})", ""]
        for e in feed.entries:
            title = _get(e, "title", "").strip()
            link = _get(e, "link", "").strip()
            summary = _get(e, "summary", "").strip()
            blob = (title + " " + summary).lower()
            if topic and topic.lower() not in blob:
                continue
            lines.append(f"- {title}")
            if link:
                lines.append(f"  link: {link}")
            if summary:
                lines.append(f"  {summary[:300]}")
            lines.append("")
        if len(lines) > 2:  # 有内容才写
            fname = f"rss/{today}_{_slug(url)}.txt"
            (sandbox_root / fname).parent.mkdir(parents=True, exist_ok=True)
            (sandbox_root / fname).write_text("\n".join(lines), encoding="utf-8")
            written.append(fname)
    return written


def _slug(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    host = p.netloc or "feed"
    path = (p.path.strip("/").replace("/", "_") or "feed")
    return f"{host}_{path}"[:60]
