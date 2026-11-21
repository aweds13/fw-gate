"""让 `tests/` 能 import 到 `src/notes`（不装包也能跑）。"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
