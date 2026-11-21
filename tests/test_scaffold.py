"""脚手架的用例：`init` 幂等（第二次拒绝）、`--force` 覆盖、`card new` 不覆盖。"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework import scaffold


def test_init_writes_files_and_refuses_second_time(tmp_path: Path):
    target = tmp_path / "newproj"
    written = scaffold.init(target, repo_root=tmp_path)
    assert written, "至少铺出一个文件"
    assert (target / "pipeline.toml").is_file()
    assert (target / "gates.d" / "tests.toml").is_file()
    assert (target / "tests" / "test_nail_sample.py").is_file()

    # 第二次：明确拒绝（不悄悄覆盖用户改动）
    with pytest.raises(scaffold.ScaffoldError) as ei:
        scaffold.init(target, repo_root=tmp_path)
    assert ei.value.exit_code == 5
    assert "已存在" in str(ei.value)


def test_init_force_is_byte_identical(tmp_path: Path):
    target = tmp_path / "newproj"
    scaffold.init(target, repo_root=tmp_path)
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    scaffold.init(target, repo_root=tmp_path, force=True)
    after = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert before == after  # 幂等：逐字节相同


def test_init_force_outside_repo_refused(tmp_path: Path):
    inside = tmp_path / "ok"
    scaffold.init(inside, repo_root=tmp_path)  # 正常
    outside = tmp_path.parent / "elsewhere-xyz"
    with pytest.raises(scaffold.ScaffoldError) as ei:
        scaffold.init(outside, repo_root=tmp_path, force=True)
    assert ei.value.exit_code == 4


def test_init_missing_template_refused(tmp_path: Path):
    with pytest.raises(scaffold.ScaffoldError) as ei:
        scaffold.init(tmp_path / "x", template="no-such-template")
    assert ei.value.exit_code == 5


def test_new_card_and_no_overwrite(tmp_path: Path):
    cards = tmp_path / "cards"
    tpl = tmp_path / "tpl.md"
    tpl.write_text("# {{id}} {{title}}\n域：{{domain}}\n", encoding="utf-8")
    out = scaffold.new_card(cards_dir=cards, spec_template=tpl, card_id="T-1",
                            title="第一张卡", domain=["src/a.py"])
    assert out.is_file()
    body = out.read_text(encoding="utf-8")
    assert "T-1" in body and "第一张卡" in body and "src/a.py" in body

    with pytest.raises(scaffold.ScaffoldError) as ei:
        scaffold.new_card(cards_dir=cards, spec_template=tpl, card_id="T-1", title="再来", domain=[])
    assert ei.value.exit_code == 4


def test_new_card_missing_template(tmp_path: Path):
    with pytest.raises(scaffold.ScaffoldError) as ei:
        scaffold.new_card(cards_dir=tmp_path / "c", spec_template=tmp_path / "nope.md",
                          card_id="T-1", title="x", domain=[])
    assert ei.value.exit_code == 5
