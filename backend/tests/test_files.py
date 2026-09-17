from app.agent.tools.files import FileTools


def _tools(tmp_sandbox):
    return FileTools(tmp_sandbox)


def test_write_then_read(tmp_sandbox):
    ft = _tools(tmp_sandbox)
    ft.write_file("out.md", "hello")
    assert "hello" in ft.read_file("out.md")


def test_list_dir(tmp_sandbox):
    ft = _tools(tmp_sandbox)
    ft.write_file("x.txt", "a")
    names = ft.list_dir(".")
    assert "x.txt" in [n["name"] for n in names]


def test_search_content(tmp_sandbox):
    ft = _tools(tmp_sandbox)
    ft.write_file("n1.md", "OpenAI released GPT")
    hits = ft.search_content("OpenAI", ".")
    assert any("n1.md" in h["file"] for h in hits)


def test_write_escape_rejected(tmp_sandbox):
    ft = _tools(tmp_sandbox)
    try:
        ft.write_file("../../evil.txt", "x")
        assert False, "should raise"
    except Exception:
        pass
