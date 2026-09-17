from pathlib import Path

# 仅允许只读/安全命令前缀(初版白名单,避免写系统与危险命令)
BASH_WHITELIST = ["grep", "cat", "ls", "wc", "head", "tail", "echo", "sort", "uniq", "date"]


class Sandbox:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def resolve(self, rel):
        """相对沙箱根解析路径;越界(逃逸出根)抛错。"""
        target = (self.root / rel).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError(f"路径越出沙箱: {rel}")
        return target

    def is_bash_allowed(self, command):
        """命令首个 token 命中白名单才放行。"""
        first = command.strip().split()[0] if command.strip() else ""
        return first in BASH_WHITELIST
