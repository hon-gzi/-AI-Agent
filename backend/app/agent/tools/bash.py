import subprocess

from app.agent.sandbox import Sandbox


class BashTool:
    """在沙箱目录内执行白名单命令(只读类),拒绝危险命令。"""

    def __init__(self, root, timeout=20):
        self.sb = Sandbox(root)
        self.timeout = timeout

    def run(self, command):
        if not self.sb.is_bash_allowed(command):
            return {"ok": False, "error": f"命令被白名单拒绝: {command}"}
        try:
            proc = subprocess.run(
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
            return {"ok": False, "error": "命令超时"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"执行异常: {e}"}
