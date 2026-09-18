from unittest import mock
from types import SimpleNamespace
from app.sources import rss
from app.agent.tools import rss_tool


def test_fetch_parses_and_writes(tmp_sandbox):
    fake_feed = _fake_feed()
    with mock.patch.object(rss, "fetch_one", return_value=fake_feed):
        files = rss.fetch_all_feeds(["http://x/feed"], tmp_sandbox)
    assert len(files) >= 1
    content = (tmp_sandbox / files[0]).read_text(encoding="utf-8")
    assert "OpenAI" in content


def _fake_feed():
    entries = [SimpleNamespace(title="OpenAI GPT", link="https://x/1", summary="new model")]
    return SimpleNamespace(entries=entries, feed=SimpleNamespace(title="FeedX"))


def test_single_source_failure_isolated(tmp_sandbox):
    """某源 fetch_one 抛异常,其余源仍正常落地。"""
    def side_effect(url):
        if "bad" in url:
            raise RuntimeError("network down")
        return _fake_feed()

    with mock.patch.object(rss, "fetch_one", side_effect=side_effect):
        files = rss.fetch_all_feeds(["http://bad/feed", "http://good/feed"], tmp_sandbox)
    # 只有 good 源落地
    assert len(files) == 1
    assert "good" in files[0]
    assert "bad" not in files[0]


def test_topic_hit_writes_and_miss_returns_empty(tmp_sandbox):
    """topic 命中→写文件;topic 全不命中→返回 [] 且不落盘。"""
    with mock.patch.object(rss, "fetch_one", return_value=_fake_feed()):
        hit = rss.fetch_all_feeds(["http://x/feed"], tmp_sandbox, topic="openai")
        assert len(hit) == 1
        assert (tmp_sandbox / hit[0]).exists()

        miss = rss.fetch_all_feeds(["http://x/miss/feed"], tmp_sandbox, topic="google")
        assert miss == []
        # rss 目录下不应有 good/miss 对应的文件(该 url 无内容)
        rss_dir = tmp_sandbox / "rss"
        assert not any("miss" in f.name for f in rss_dir.iterdir())


def test_search_rss_tool_exception_degrades(tmp_sandbox):
    """fetch_all_feeds 抛异常时,search_rss 返回 {"ok": False, ...} 不中断。"""
    settings = SimpleNamespace(sandbox_root=tmp_sandbox, rss_feeds=["http://x/feed"])
    with mock.patch.object(rss, "fetch_all_feeds", side_effect=RuntimeError("boom")):
        out = rss_tool.search_rss("AI", settings=settings)
    assert out["ok"] is False
    assert "boom" in out["error"]
    assert out["files"] == []
