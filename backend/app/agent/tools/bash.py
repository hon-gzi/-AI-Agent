import subprocess

from app.agent.sandbox import Sandbox


class BashTool:
    """在沙箱目录内执行白名单命令(只读类),拒绝危险命令。"""

    def __init__(self, root, timeout=20, runner=None):
        self.sb = Sandbox(root)
        self.timeout = timeout
        # 可注入 runner(默认 subprocess.run),便于测试超时路径等无需真实子进程。
        self._runner = runner if runner is not None else subprocess.run

    def run(self, command):
        if not self.sb.is_bash_allowed(command):
            return {
                "ok": False,
                "error": f"命令被白名单拒绝: {command}",
                "stdout": "",
                "stderr": "",
                "returncode": None,
            }
        try:
            proc = self._runner(
                command,
                shell=True,
                cwd=str(self.sb.root),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return {
                "ok": True,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-2000:],
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": "命令超时",
                "stdout": "",
                "stderr": "",
                "returncode": None,
            }
        except Exception as e:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"执行异常: {e}",
                "stdout": "",
                "stderr": "",
                "returncode": None,
            }
