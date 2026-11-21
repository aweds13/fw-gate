"""★ 反例钉子（counterexample nail）—— 故意喂进坏掉的样本，断言判据会把它逮住。

它**通过** ⇒ 判据有牙（正常）；它**失败** ⇒ 判据失效（退化成注释）。
`gates.d/tests.toml` 的 `nail` 指的就是本文件里的用例。
"""

from pathlib import Path

from notes.evidence import evaluate

_ROOT = Path(__file__).resolve().parent


def test_broken_pointer_is_rejected():
    """一个指向不存在文件的指针，必须被判为**假**（不许静默通过）。"""
    ok, why = evaluate("file:this-file-does-not-exist.txt", _ROOT.parent)
    assert ok is False, f"坏样本竟被判为真：{why}"


def test_malformed_pointer_is_rejected():
    """形状不对的指针，必须被判为**假**。"""
    ok, _ = evaluate("not-a-pointer", _ROOT.parent)
    assert ok is False
