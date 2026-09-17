import pytest
from app.agent.sandbox import Sandbox, BASH_WHITELIST


def test_resolve_inside(tmp_sandbox):
    sb = Sandbox(tmp_sandbox)
    p = sb.resolve("a/b.txt")
    assert str(p).startswith(str(tmp_sandbox))


def test_escape_rejected(tmp_sandbox):
    sb = Sandbox(tmp_sandbox)
    with pytest.raises(Exception):
        sb.resolve("../outside.txt")


def test_bash_whitelist_allows_readonly():
    assert any(w.startswith("grep") for w in BASH_WHITELIST)


def test_bash_whitelist_rejects_dangerous():
    joined = " ".join(BASH_WHITELIST)
    assert "rm" not in joined
