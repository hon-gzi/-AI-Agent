import pytest


@pytest.fixture
def tmp_sandbox(tmp_path):
    """每个测试独立的沙箱根目录。"""
    root = tmp_path / "sandbox"
    root.mkdir()
    return root
