"""归集屏障 + 完成申报 —— **薄壳**（卡 179 §主控裁的范围：本轮只做最小可实现）。

对齐设计 §③.2 第 5 条 `pipe claim` 与 `tools/pool/task.py`：任务集齐**成功申请**才放行
（不是攒够 N 条）；域检查按**卡树实际改动 vs 权威域**，不吃自报清单；成功必须带 `--evidence`。

★ 本模块**尚未实现**：签名在，行为未建。调用即抛 `PendingError`（**不返回假结果**）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pending import PendingError


@dataclass(frozen=True)
class ClaimResult:
    """一条完成申报的结果（**目标形态**，本卡未实现）。"""

    task: str
    member: str
    status: str
    accepted: bool
    detail: str


def submit(
    *,
    task: str,
    member: str,
    status: str,
    files: list[str],
    why: str,
    evidence: str,
    claims_dir: str | Path,
) -> ClaimResult:
    """收一条完成申报（写进 `claims_dir`）。

    参数：`status` ∈ `success|failed`；`files` = 声明改动的文件；`evidence` = 指针。
    ★ 未实现：抛 `PendingError`。
    """
    raise PendingError(
        "framework.claim.submit 尚未实现（本卡只做薄壳）。"
        "目标：收申请 + 域检查（卡树实际改动 vs 权威域）+ 成功必须带 evidence。"
    )


def collect(*, task: str, claims_dir: str | Path) -> list[ClaimResult]:
    """读一个任务的全部申报（归集屏障的输入）。

    ★ 未实现：抛 `PendingError`。
    """
    raise PendingError(
        "framework.claim.collect 尚未实现（本卡只做薄壳）。"
        "目标：集齐非只读成员的成功申请才放行。"
    )
