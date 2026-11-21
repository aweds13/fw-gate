"""封存指纹 + 事件 —— **薄壳**（卡 179 §主控裁的范围：本轮只做最小可实现）。

对齐设计 §③.2 第 8 条 `pipe trace seal`：把 `HEAD^{tree}` 剔掉 `[seal].ignore` 后的指纹写进
`[paths].gates_state`；事件落 `[events].ndjson_path`（NDJSON / CloudEvents）。

★ 本模块**尚未实现**：签名在，行为未建。调用即抛 `PendingError`（**不返回假结果**）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pending import PendingError


@dataclass(frozen=True)
class SealResult:
    """封存结果（**目标形态**，本卡未实现）。"""

    tree: str
    rev: str | None
    algorithm: str


def seal(*, repo_root: str | Path, reason: str, algorithm: str = "sha256") -> SealResult:
    """给当前提交树打完封存指纹（改封存必须给 `reason`，照 §8 坑 5）。

    ★ 未实现：抛 `PendingError`。
    """
    raise PendingError(
        "framework.trace.seal 尚未实现（本卡只做薄壳）。"
        "目标：HEAD^{tree} 剔 [seal].ignore 后出指纹（sha256），写 [paths].gates_state。"
    )


def emit_event(*, ndjson_path: str | Path, event: dict) -> None:
    """追加一条事件到 NDJSON（一行一事件）。★ 未实现：抛 `PendingError`。"""
    raise PendingError(
        "framework.trace.emit_event 尚未实现（本卡只做薄壳）。"
        "目标：一行一事件落到 [events].ndjson_path（CloudEvents 1.0 或 NDJSON）。"
    )
