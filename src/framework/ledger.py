"""台账求值 —— **薄壳**（卡 179 §主控裁的范围：本轮只做最小可实现）。

对齐设计 §③.2 第 7 条 `pipe ledger check`：逐条证据求值（`file:`/`text:`/`route:`/
`table:`/`column:`/`ui:`/`test:`，见 卡表与规矩 §22）+ 不变式核查。

★ 本模块**尚未实现**：签名在，行为未建。调用即抛 `PendingError`（**不返回假结果**）。
  真正的实现属阶段一后续（证据前缀的求值语义绑本仓结构，迁移见骨架设计 §追加 B）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pending import PendingError


@dataclass(frozen=True)
class EvidenceResult:
    """一条证据的求值结果（**目标形态**，本卡未实现）。"""

    entry_id: str
    assertion: str
    ok: bool
    detail: str


def check(
    ledger_path: str | Path,
    *,
    commit: str | None = None,
    missing_only: bool = False,
) -> list[EvidenceResult]:
    """求值台账里每条 `evidence`，返回逐条结果。

    参数：`ledger_path` 台账文件；`commit` 只审某一笔（None = 当前 HEAD）；
    `missing_only` 只回报失败条目。

    ★ 未实现：抛 `PendingError`。
    """
    raise PendingError(
        "framework.ledger.check 尚未实现（本卡只做薄壳）。"
        "目标：逐条求值 file:/text:/route:/table:/column:/ui:/test: 证据（见 卡表与规矩 §22）。"
    )
