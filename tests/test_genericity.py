"""泛用性（提升就绪）的用例 —— 判据：全框架目录不许出现任何项目专有引用。

★ 本文件**不写真名**：被禁的词用拼接构造（`_WORD = "time" + "flow"`），
  否则「grep 全框架目录 = 0 命中」这条判据会被这个测试文件自己弄红。
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parents[1]

_ORIGIN_WORD = "time" + "flow"           # 本项目专有名（构造，避免自命中）
_REPO_PATH_TOKENS = ("复盘" + "/", "docs" + "/traceability", "gates" + "/diag")


def _iter_text_files(root: Path):
    skip_dirs = {"__pycache__", ".pipe", ".pytest_cache", ".git", "build", "dist"}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.suffix in {".pyc", ".pyo", ".so", ".dll", ".exe", ".png", ".jpg"}:
            continue
        try:
            yield p, p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def test_no_project_specific_word_anywhere_in_framework():
    hits = [(str(p.relative_to(FRAMEWORK)), _ORIGIN_WORD) for p, text in _iter_text_files(FRAMEWORK)
            if _ORIGIN_WORD in text]
    assert hits == [], f"框架里出现了项目专有名（提升就绪 P1 失败）：{hits}"


def test_detector_has_teeth():
    """反例钉子：检测器真的咬得住一个合成命中，否则上面的 0 命中是恒真。"""
    synthetic = "some " + _ORIGIN_WORD + " here"
    assert _ORIGIN_WORD in synthetic


def test_schema_and_templates_have_no_repo_paths():
    targets = [FRAMEWORK / "pipeline.schema.json", FRAMEWORK / "templates"]
    bad = []
    for target in targets:
        files = [target] if target.is_file() else list(target.rglob("*"))
        for f in files:
            if not f.is_file() or any(part in {"__pycache__", ".pipe"} for part in f.parts):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for token in _REPO_PATH_TOKENS:
                if token in text:
                    bad.append((str(f.relative_to(FRAMEWORK)), token))
    assert bad == [], f"schema/模板里出现了本仓专有路径（提升就绪 P3 失败）：{bad}"


def test_pyproject_is_self_contained_and_has_pipe_entry():
    data = tomllib.loads((FRAMEWORK / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"]
    assert data["project"]["scripts"]["pipe"].startswith("cli")
    assert data["build-system"]["build-backend"] == "setuptools.build_meta"


def test_schema_json_is_valid_json_schema_shape():
    schema = json.loads((FRAMEWORK / "pipeline.schema.json").read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"meta", "paths", "cards", "gates", "workers", "exit_codes"}


def test_core_library_imports_without_cli():
    """判据（卡 179 §②）：把 CLI 删掉，库仍可 import。"""
    import importlib
    for mod in ("framework", "framework.config", "framework.gates", "framework.exit_codes",
                "framework.ledger", "framework.invariants", "framework.claim",
                "framework.land", "framework.trace"):
        assert importlib.import_module(mod) is not None
    assert "cli" not in [m for m in ("cli.main",) if m in sys.modules]
