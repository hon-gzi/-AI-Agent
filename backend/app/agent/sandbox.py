import re
from pathlib import Path

# 仅允许只读/安全命令前缀(初版白名单,避免写系统与危险命令)
BASH_WHITELIST = ["grep", "cat", "ls", "wc", "head", "tail", "echo", "sort", "uniq", "date"]

# shell 元字符黑名单:命令中出现即直接拒绝,防注入绕过首 token 白名单
# (如 "grep x; rm -rf /" / "grep | rm x" / "$(...)" / "cat f > /etc/passwd")
# 换行符(\n/\r)是 shell 命令分隔符,需一并拉黑,否则 "cat f\nrm -rf /" 第二行绕过白名单。
SHELL_METACHARACTERS = [";", "|", "&", "`", "$(", ">", "<", "(", ")", "\n", "\r"]


def has_dangerous_path(command: str) -> bool:
    """检测命令中的路径逃逸/变量扩展特征:出现即拒绝。

    命中以下任一即返回 True:
    - ".." 作为路径成分(其后跟随路径分隔符 / 或 \\\\,或位于行尾);
      覆盖 "../"、"..\\\\"、及 "cat .." 后接空格行尾的场景。
    - "$" 变量扩展(含 "${...}"、"$VAR" 及 "$(...)",其中 "$(...)" 亦由元字符黑名单拦下,
      但在此一并显式拦下以便单点兜底)。
    - 绝对路径前缀:POSIX 风格以 / 开头(作为参数出现),
      以及 Windows 盘符(如 C: 后接 / 或 \\)。

    白名单命令本身(grep/cat 等)不含上述字符,故安全的只读命令不受影响。
    """
    text = command or ""
    # ".." 作为路径成分:其后跟随分隔符,或 ".." 是末尾 token(行尾)。
    # (?<![\w]) 确保 ".." 两侧非普通字符合(排除 "file..txt" 这类文件名)。
    if ".." in text:
        if re.search(r"(?<![\w])\.\.(?=[/\\]|$|\s)", text):
            return True
    # 变量扩展:任意 "$"。
    if "$" in text:
        return True
    # 绝对路径:POSIX / 前缀(非命令首 token 位置),或 Windows 盘符。
    # Windows 盘符:字母 + 冒号 + / 或反斜杠
    if re.search(r"[A-Za-z]:[\\/]", text):
        return True
    # POSIX 绝对路径:空格/tab 后紧跟 /(作为参数),例如 "cat /etc/passwd"。
    # 行首的 / 不作为首 token 白名单命中(grep/cat 等不含 /),故单独拦下参数形绝对路径。
    if re.search(r"(?<=\s)/", text):
        return True
    return False


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
        """白名单 + 元字符黑名单 + 路径逃逸黑名单,任一命中即拒绝,否则首 token 须命中白名单。"""
        text = command or ""
        if any(meta in text for meta in SHELL_METACHARACTERS):
            return False
        if has_dangerous_path(text):
            return False
        first = text.strip().split()[0] if text.strip() else ""
        return first in BASH_WHITELIST
