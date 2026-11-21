"""极小的证据指针求值（模板自带，演示「判据随件走」）。

规则（刻意从简）：
  - `file:<相对路径>`：文件存在即真。
  - 未知前缀：**一律为假**（不许猜、不许当成通过）。
"""

from __future__ import annotations

from pathlib import Path


def evaluate(pointer: str, root: str | Path) -> tuple[bool, str]:
    """求值一条证据指针，返回 (是否成立, 说明)。"""
    root_path = Path(root)
    prefix, sep, rest = pointer.partition(":")
    if not sep or not rest:
        return False, f"指针形状不对（要 prefix:value）：{pointer!r}"
    if prefix == "file":
        target = root_path / rest
        return target.exists(), f"file:{rest} -> {target}"
    return False, f"未知前缀 {prefix!r}（不猜，判为假）"
