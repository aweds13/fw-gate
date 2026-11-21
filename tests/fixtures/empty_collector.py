"""反例夹具：模拟一个「一条样例都没收集到」的收集器。

行为对齐 `pytest` 的「no tests collected」：写出 JUnit XML（`tests="0"`）并以退出码 **5** 退出。
用它来证明框架的三值判决把**空集**判成 `inconclusive`，而**不是**绿。

退出码 5 不在门的 `exit_ok=[0]` 里 —— 如果框架只看退出码，它会判 `fail`；
本夹具钉住的是：框架**还**读了 JUnit 的样例数、把它判成 `inconclusive`（判不了 ≠ 通过 ≠ 失败）。
"""

from __future__ import annotations

import sys
from pathlib import Path

EMPTY_JUNIT = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<testsuite name="empty" tests="0" failures="0" errors="0" skipped="0"></testsuite>\n'
)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法：empty_collector.py <junit.xml 输出路径>", file=sys.stderr)
        return 2
    out = Path(argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(EMPTY_JUNIT, encoding="utf-8")
    return 5  # pytest：no tests collected


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
