"""集成与发布 —— **薄壳**（卡 179 §主控裁的范围：本轮只做最小可实现）。

对齐设计 §③.2 第 6 条 `pipe land` 与 `tools/pool/landing.py`：**七步**
（回退派生物 → 迁树 → 文书 → 门禁 → 封存 → 白名单提交 → 审计 → ff）；开跑前幂等回退派生物。

★ 本模块**尚未实现**：签名在，行为未建。调用即抛 `PendingError`（**不返回假结果**）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pending import PendingError


@dataclass(frozen=True)
class LandStep:
    """一步的读数（**目标形态**，本卡未实现）。"""

    step: str
    ok: bool
    detail: str


def reset_derived(*, repo_root: str | Path) -> list[str]:
    """回退派生产物（幂等重跑的前置，照 T-G250）。★ 未实现：抛 `PendingError`。"""
    raise PendingError(
        "framework.land.reset_derived 尚未实现（本卡只做薄壳）。"
        "目标：把派生物退回 HEAD，只回退派生物、不碰源文件。"
    )


def land(*, task: str, repo_root: str | Path, dry_run: bool = False) -> list[LandStep]:
    """跑集成与发布**七步**；`dry_run=True` 只算不写。

    ★ 未实现：抛 `PendingError`。
    """
    raise PendingError(
        "framework.land.land 尚未实现（本卡只做薄壳）。"
        "目标：七步流水线（回退派生物→迁树→文书→门禁→封存→白名单提交→审计→ff）。"
    )
