from pathlib import Path

import pytest
from app.agent.sandbox import Sandbox, BASH_WHITELIST


def test_resolve_inside(tmp_sandbox):
    sb = Sandbox(tmp_sandbox)
    p = sb.resolve("a/b.txt")
    assert p.is_relative_to(tmp_sandbox)


def test_resolve_root_allowed(tmp_sandbox):
    sb = Sandbox(tmp_sandbox)
    assert sb.resolve(".").is_relative_to(tmp_sandbox)


def test_escape_rejected(tmp_sandbox):
    sb = Sandbox(tmp_sandbox)
    with pytest.raises(Exception):
        sb.resolve("../outside.txt")


def test_bash_whitelist_allows_readonly():
    assert any(w.startswith("grep") for w in BASH_WHITELIST)


def test_bash_whitelist_rejects_dangerous():
    joined = " ".join(BASH_WHITELIST)
    assert "rm" not in joined


def test_bash_allowed_readonly_passes():
    sb = Sandbox("C:/sandbox")
    assert sb.is_bash_allowed("grep x") is True
    assert sb.is_bash_allowed("grep foo f") is True
    assert sb.is_bash_allowed("rm -rf /") is False


def test_bash_allowed_rejects_metacharacter_injection():
    sb = Sandbox("C:/sandbox")
    assert sb.is_bash_allowed("grep x; rm -rf /") is False
    assert sb.is_bash_allowed("grep | rm x") is False
    assert sb.is_bash_allowed("ls a && rm b") is False
    assert sb.is_bash_allowed("grep $(rm x) f") is False
    assert sb.is_bash_allowed("cat f > /etc/passwd") is False
