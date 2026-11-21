"""不变式核查 —— **薄壳**（卡 179 §主控裁的范围：本轮只做最小可实现）。

对齐设计 §③.2 第 7 条与 `tools/wb_invariants.py` 的口径：每条不变式有 claim / judge / nail / status，
新能力没进表就不算做完（见 抽取清单 #99/#100）。

★ 本模块**尚未实现**：签名在，行为未建。调用即抛 `PendingError`（**不返回假结果**）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pending import PendingError


@dataclass(frozen=True)
class InvariantResult:
    """一条不变式的核查结果（**目标形态**，本卡未实现）。"""

    inv_id: str
    status: str
    detail: str


def check(register_path: str | Path) -> list[InvariantResult]:
    """核查不变式登记册里的每一条（judge / nail 路径与用例是否存在）。

    ★ 未实现：抛 `PendingError`。
    """
    raise PendingError(
        "framework.invariants.check 尚未实现（本卡只做薄壳）。"
        "目标：核查每条不变式的 judge/nail 是否存在，缺失报 missing（照 tools/wb_invariants.py）。"
    )
