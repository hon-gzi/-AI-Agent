from app.agent.tools.bash import BashTool


def _tool(tmp_sandbox, **kw):
    return BashTool(tmp_sandbox, **kw)


def test_echo_allowed(tmp_sandbox):
    bt = _tool(tmp_sandbox)
    out = bt.run("echo hi")
    assert out["ok"] is True
    assert "hi" in out["stdout"]


def test_dangerous_rejected(tmp_sandbox):
    bt = _tool(tmp_sandbox)
    res = bt.run("rm -rf /")
    assert res["ok"] is False
    assert "拒绝" in res["error"]
    # 放行/拒绝分支返回键统一(拒绝时 stdout/stderr 为空串)
    assert res["stdout"] == ""
    assert res["stderr"] == ""
    assert res["returncode"] is None


def test_metachar_rejected(tmp_sandbox):
    """含 shell 元字符的命令(如 grep x; rm)必须被白名单拒绝。"""
    bt = _tool(tmp_sandbox)
    res = bt.run("grep x; rm y")
    assert res["ok"] is False
    assert "拒绝" in res["error"]


def test_path_escape_rejected(tmp_sandbox):
    """白名单首 token 命中但路径/变量逃逸须被拒(防注入后读走密钥)。"""
    bt = _tool(tmp_sandbox)
    for cmd in [
        "cat ../../../../../../etc/passwd",
        "cat /etc/passwd",
        "echo ${PATH}",
        "cat C:\\Windows\\win.ini",
    ]:
        res = bt.run(cmd)
        assert res["ok"] is False
        assert "拒绝" in res["error"]


def test_grep_in_sandbox(tmp_sandbox):
    (tmp_sandbox / "f.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    bt = _tool(tmp_sandbox)
    out = bt.run("grep alpha f.txt")
    # 白名单放行:命令未被拒绝(ok=True)。
    assert out["ok"] is True
    # 沙箱 cwd 生效:命中文件,输出含 alpha(本机 grep 可用时 returncode==0)。
    assert "alpha" in out["stdout"]


def test_timeout_returns_error(tmp_sandbox):
    """注入假 runner 抛 TimeoutExpired,断言返回命令超时常量。"""
    import subprocess

    def fake_runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="grep", timeout=1)

    bt = _tool(tmp_sandbox, runner=fake_runner)
    res = bt.run("grep x f.txt")
    assert res["ok"] is False
    assert res["error"] == "命令超时"
