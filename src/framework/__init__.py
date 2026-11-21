"""framework —— 可带走的管线核心库（卡 179 / T-G279）。

分层（照骨架设计 §4.1）：
  - **核心库**（本包）：配置加载 · 门运行器 · 退出码 · 台账/申报/集成/封存的薄壳。
  - **薄 CLI**：`framework/cli/main.py`，只做「解析参数 → 调库 → 映射退出码」。
  - **模板仓 / 示例仓**：`framework/templates/**`、`framework/examples/**`。

泛用性硬判据（骨架设计 §追加 C.3，P1–P6）：
  - **本包与 CLI 不许出现任何项目专有引用**（判据：全框架目录 grep 项目专有名 = 0 命中）。
  - 自带 `pyproject.toml`，可独立安装/运行。
  - 项目专有路径只许出现在**项目侧**的 `pipeline.toml`，不进代码。

本包**不 print、不 sys.exit、不读全局状态**；`import framework` 即可用。
"""

from __future__ import annotations

__version__ = "0.1.0"

from . import config, exit_codes, gates  # noqa: E402

__all__ = ["config", "exit_codes", "gates", "__version__"]
