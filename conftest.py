"""让 `framework/tests/` 能 import 到 `src/framework`（不装包也能跑 pytest）。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
