"""清单 —— examples/minimal-notes 的领域代码（纯函数，无副作用、无全局状态）。"""

from __future__ import annotations


def add(note: str, notes: list[str] | None = None) -> list[str]:
    """加一条记事；返回新列表（不改原列表）。"""
    text = note.strip()
    if not text:
        raise ValueError("记事不许为空")
    return [*(notes or []), text]


def search(keyword: str, notes: list[str]) -> list[str]:
    """按关键词搜记事（大小写不敏感）。"""
    key = keyword.strip().lower()
    if not key:
        raise ValueError("关键词不许为空")
    return [n for n in notes if key in n.lower()]
