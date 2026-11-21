"""脚手架：`pipe init`（铺模板仓）与 `pipe card new`（从模板生成卡）。

业务逻辑放库里，CLI 只做参数解析与打印（卡 179 §②：把 CLI 删掉，库仍可测）。

`init` **幂等**判据（卡 §你要产出什么 ③）：同一目录连跑两次 —— 第二次**明确拒绝**
（目标已存在且非空，未给 `--force`）或（给了 `--force`）**结果逐字节相同**；
**绝不悄悄覆盖用户改动**。
"""

from __future__ import annotations

import shutil
from pathlib import Path

TEMPLATES_REL = Path("templates")


class ScaffoldError(Exception):
    """脚手架出错；`exit_code` 是建议的退出码（CLI 直接用）。"""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def templates_root() -> Path:
    """`framework/templates/`（本文件在 `framework/src/framework/`，上溯三层）。"""
    return Path(__file__).resolve().parents[2] / TEMPLATES_REL


def default_template_dir(template: str = "minimal") -> Path:
    return templates_root() / template


def init(
    target_dir: str | Path,
    *,
    template: str = "minimal",
    force: bool = False,
    repo_root: str | Path | None = None,
) -> list[str]:
    """把模板铺到 `target_dir`，返回铺出的相对路径清单（排序）。

    退出码语义（异常里的 `exit_code`）：`5` 目标已存在且未 `--force`；`5` 模板缺失；
    `4` `--force` 目标在仓外（越界）。
    """
    target = Path(target_dir)
    if not target.is_absolute():
        target = (Path.cwd() / target)
    target = target.resolve()

    src = default_template_dir(template)
    if not src.is_dir():
        raise ScaffoldError(f"模板不存在：{src}（可用模板：{sorted(p.name for p in templates_root().glob('*') if p.is_dir())}）", 5)

    if force:
        root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
        if not (target == root or target.is_relative_to(root)):
            raise ScaffoldError(
                f"--force 目标在仓外（越界）：{target}（仓根 {root}）—— 拒绝", 4
            )

    written: list[str] = []
    for src_file in sorted(src.rglob("*")):
        rel = src_file.relative_to(src)
        dst = target / rel
        if src_file.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        if dst.exists() and not force:
            raise ScaffoldError(
                f"目标已存在：{dst}（未给 --force，拒绝覆盖 —— 保护用户改动）", 5
            )
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_file, dst)
        written.append(rel.as_posix())

    # 空目录（模板里没有文件的目录）也建出来，保证布局一致
    for src_dir in sorted(src.rglob("*")):
        if src_dir.is_dir():
            (target / src_dir.relative_to(src)).mkdir(parents=True, exist_ok=True)

    return sorted(written)


def new_card(
    *,
    cards_dir: str | Path,
    spec_template: str | Path,
    card_id: str,
    title: str,
    domain: list[str],
) -> Path:
    """从卡模板生成 `cards_dir/<id>-<slug>.md`；返回生成的文件路径。

    目标已存在 → `ScaffoldError(..., 4)`（不覆盖）；模板缺失 → `ScaffoldError(..., 5)`。
    """
    template_path = Path(spec_template)
    if not template_path.is_file():
        raise ScaffoldError(f"卡模板缺失：{template_path}", 5)

    slug = "-".join("".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in card_id).split("-"))
    slug = slug.strip("-") or "card"
    out_dir = Path(cards_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.md"
    if out_path.exists():
        raise ScaffoldError(f"卡已存在：{out_path}（不覆盖，卡号全局唯一）", 4)

    text = template_path.read_text(encoding="utf-8")
    text = (text
            .replace("{{id}}", card_id)
            .replace("{{title}}", title)
            .replace("{{domain}}", ", ".join(domain) if domain else "（未声明）"))
    out_path.write_text(text, encoding="utf-8")
    return out_path
