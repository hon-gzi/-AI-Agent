from pathlib import Path

import pytest
from app.agent.sandbox import Sandbox, BASH_WHITELIST, has_dangerous_path


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


def test_bash_allowed_rejects_newline_and_cr_metachars(tmp_sandbox):
    """换行/回车是 shell 命令分隔符,须被拉黑,否则第二行绕过白名单。"""
    sb = Sandbox(tmp_sandbox)
    assert sb.is_bash_allowed("cat f\nrm -rf /") is False
    assert sb.is_bash_allowed("cat f\rrm x") is False
    assert sb.is_bash_allowed("grep x\ncat secret") is False


def test_has_dangerous_path_detects_components():
    assert has_dangerous_path("../etc/passwd") is True
    assert has_dangerous_path("..\\windows\\system.ini") is True
    assert has_dangerous_path("echo $HOME") is True
    assert has_dangerous_path("cat C:/Windows/win.ini") is True
    assert has_dangerous_path("cat /etc/passwd") is True
    # 普通只读命令无危险特征
    assert has_dangerous_path("cat f.txt") is False
    assert has_dangerous_path("grep alpha f.txt") is False


def test_bash_allowed_rejects_path_escape(tmp_sandbox):
    """首 token 命中白名单,但路径/变量逃逸须被拒(防 LLM 注入后读走 .env 密钥)。"""
    sb = Sandbox(tmp_sandbox)
    assert sb.is_bash_allowed("cat ../../../../../../etc/passwd") is False
    assert sb.is_bash_allowed("cat ..\\windows\\system.ini") is False
    assert sb.is_bash_allowed("grep ..") is False
    assert sb.is_bash_allowed("echo ${PATH}") is False
    assert sb.is_bash_allowed("cat C:\\Windows\\win.ini") is False
    assert sb.is_bash_allowed("cat C:/Windows/win.ini") is False
    assert sb.is_bash_allowed("cat /etc/passwd") is False
    # 安全的相对路径仍放行
    assert sb.is_bash_allowed("cat f.txt") is True
    assert sb.is_bash_allowed("grep alpha f.txt") is True
