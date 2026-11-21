"""正常路径的用例。"""

import pytest

from notes import add, search


def test_add_appends_without_mutating():
    base = ["a"]
    out = add("b", base)
    assert out == ["a", "b"]
    assert base == ["a"]  # 不改原列表


def test_add_rejects_blank():
    with pytest.raises(ValueError):
        add("   ")


def test_search_is_case_insensitive():
    assert search("MILK", ["Buy milk", "call mom"]) == ["Buy milk"]
