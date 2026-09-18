from unittest import mock
from app.sources import rss


def test_fetch_parses_and_writes(tmp_sandbox):
    fake_feed = _fake_feed()
    with mock.patch.object(rss, "fetch_one", return_value=fake_feed):
        files = rss.fetch_all_feeds(["http://x/feed"], tmp_sandbox)
    assert len(files) >= 1
    content = (tmp_sandbox / files[0]).read_text(encoding="utf-8")
    assert "OpenAI" in content


def _fake_feed():
    from types import SimpleNamespace
    entries = [SimpleNamespace(title="OpenAI GPT", link="https://x/1", summary="new model")]
    return SimpleNamespace(entries=entries, feed=SimpleNamespace(title="FeedX"))
