"""薄壳共用的「尚未实现」异常。

卡 179 把 `ledger.py` / `invariants.py` / `claim.py` / `land.py` / `trace.py` 定为**薄壳**
（「只做最小可实现：能 import、签名清楚、**没实现就明确报错**、有钉子钉住这一点，
不许半成品冒充成品」）。本异常就是那句「明确报错」的机器落点：签名在、行为未建时抛它，
调用方（CLI）据此给出稳定退出码，**绝不假装返回一个像样的结果**。
"""

from __future__ import annotations


class PendingError(Exception):
    """该能力已声明接口但**尚未实现**（薄壳）。★ 不是「失败」，是「没建」。"""
