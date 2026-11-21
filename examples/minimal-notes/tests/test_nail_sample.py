"""★ 反例钉子 —— 喂进坏掉的样本，断言判据会把它逮住。通过 = 有牙。"""

import pytest

from notes import search


def test_nail_rejects_empty_keyword():
    """空关键词是坏样本，必须被**拒绝**（抛错），而不是返回全部记事。"""
    with pytest.raises(ValueError):
        search("   ", ["a", "b"])
