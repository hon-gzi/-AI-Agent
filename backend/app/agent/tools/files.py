import os
from pathlib import Path


class FileTools:
    """受沙箱约束的文件操作。所有路径相对沙箱根解析并校验越界。"""

    def __init__(self, root):
        from app.agent.sandbox import Sandbox
        self.sb = Sandbox(root)

    def _p(self, rel):
        return self.sb.resolve(rel)

    def list_dir(self, path="."):
        d = self._p(path)
        out = []
        for child in sorted(os.listdir(d)):
            full = d / child
            out.append({"name": child, "type": "dir" if full.is_dir() else "file"})
        return out

    def read_file(self, path):
        p = self._p(path)
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        return p.read_text(encoding="utf-8")

    def search_content(self, keyword, dir="."):
        d = self._p(dir)
        hits = []
        for base, _, files in os.walk(d):
            for fn in files:
                fp = Path(base) / fn
                try:
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if keyword in line:
                        hits.append({
                            "file": str(Path(fp).relative_to(self.sb.root)),
                            "line": i,
                            "text": line.strip()[:200],
                        })
        return hits

    def write_file(self, path, content):
        p = self._p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"written": str(p.relative_to(self.sb.root)), "bytes": len(content)}
