"""正常路径的用例（与钉子相对：这里断言「好的样本通过」）。"""

from pathlib import Path

from notes.evidence import evaluate

_ROOT = Path(__file__).resolve().parent


def test_existing_file_pointer_is_true():
    ok, _ = evaluate("file:pipeline.toml", _ROOT.parent)
    assert ok is True


def test_unknown_prefix_is_false():
    ok, why = evaluate("teleport:somewhere", _ROOT.parent)
    assert ok is False
    assert "未知前缀" in why
