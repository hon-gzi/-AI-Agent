from pathlib import Path

# 仅允许只读/安全命令前缀(初版白名单,避免写系统与危险命令)
BASH_WHITELIST = ["grep", "cat", "ls", "wc", "head", "tail", "echo", "sort", "uniq", "date"]

# shell 元字符黑名单:命令中出现即直接拒绝,防注入绕过首 token 白名单
# (如 "grep x; rm -rf /" / "grep | rm x" / "$(...)" / "cat f > /etc/passwd")
SHELL_METACHARACTERS = [";", "|", "&", "`", "$(", ">", "<", "(", ")"]


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
        """首 token 白名单 + 元字符黑名单:含 shell 元字符直接拒绝,否则首 token 须命中白名单。"""
        text = command or ""
        if any(meta in text for meta in SHELL_METACHARACTERS):
            return False
        first = text.strip().split()[0] if text.strip() else ""
        return first in BASH_WHITELIST
