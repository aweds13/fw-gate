"""配置加载 + 严格 schema 校验的用例（卡 179 §验收：缺键 / 未知键 / 坏 TOML 各报一条）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework.config import ConfigError, load

VALID = """
[meta]
schema_version = "0.1.0"
framework_version = "0.1.0"
project_id = "demo"

[paths]
ledger = "ledger.toml"
invariants = "invariants.toml"
evidence_dir = ".pipe/evidence"
logs_dir = ".pipe/logs"
gates_state = ".pipe/last.json"
gates_reuse = ".pipe/reuse.json"

[cards]
cards_dir = "cards"
spec_template = "card-template.md"
backlog = "backlog.toml"
claims_dir = ".pipe/claims"
authoritative_domains = "backlog.toml"

[gates]
gates_dir = "gates.d"

[workers]
model_allowlist = ["a-model", "b-model"]
default_model = "a-model"

[exit_codes]
table_version = "0.1.0"
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "pipeline.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_valid_config_loads_with_defaults(tmp_path: Path):
    cfg = load(_write(tmp_path, VALID))
    assert cfg.meta["project_id"] == "demo"
    assert cfg.meta["project_name"] == "demo"          # 默认 = project_id
    assert cfg.meta["default_branch"] == "main"
    assert cfg.events["source_uri"] == "pipe://demo"   # 默认 = pipe://<project_id>
    assert cfg.resource["port_base"] == 8531
    assert cfg.workers["default_model"] == "a-model"


def test_missing_required_key_reports_explicitly(tmp_path: Path):
    broken = VALID.replace('project_id = "demo"\n', "", 1)
    with pytest.raises(ConfigError) as ei:
        load(_write(tmp_path, broken))
    assert "meta.project_id" in str(ei.value)
    assert "缺键" in str(ei.value)


def test_unknown_key_reports_explicitly(tmp_path: Path):
    broken = VALID.replace('framework_version = "0.1.0"', 'framework_version = "0.1.0"\nframewrk_version = "typo"', 1)
    with pytest.raises(ConfigError) as ei:
        load(_write(tmp_path, broken))
    msg = str(ei.value)
    assert "未知键" in msg and "framewrk_version" in msg


def test_bad_toml_reports_explicitly(tmp_path: Path):
    with pytest.raises(ConfigError) as ei:
        load(_write(tmp_path, "[meta\nschema_version = \"0.1.0\"]\n"))
    assert "不是合法 TOML" in str(ei.value)


def test_unknown_section_reports_explicitly(tmp_path: Path):
    with pytest.raises(ConfigError) as ei:
        load(_write(tmp_path, VALID + "\n[bogus]\nx = 1\n"))
    assert "未知段" in str(ei.value)


def test_default_model_must_be_in_allowlist(tmp_path: Path):
    broken = VALID.replace('default_model = "a-model"', 'default_model = "c-model"', 1)
    with pytest.raises(ConfigError) as ei:
        load(_write(tmp_path, broken))
    assert "model_allowlist" in str(ei.value)


def test_schema_major_mismatch_rejected(tmp_path: Path):
    broken = VALID.replace('schema_version = "0.1.0"', 'schema_version = "9.0.0"', 1)
    with pytest.raises(ConfigError) as ei:
        load(_write(tmp_path, broken))
    assert "主版本" in str(ei.value)


def test_missing_config_file_reports_explicitly(tmp_path: Path):
    with pytest.raises(ConfigError) as ei:
        load(tmp_path / "nope.toml")
    assert "配置不存在" in str(ei.value)


def test_gate_file_and_inline_merge(tmp_path: Path):
    (tmp_path / "gates.d").mkdir()
    (tmp_path / "gates.d" / "lint.toml").write_text(
        '[gate]\nname = "lint"\ncmd = ["python", "-c", "print(1)"]\ninputs = []\n'
        'nail = "tests/x.py::test_y"\nreuse = "never"\nstage = "light"\ntimeout_s = 10\n',
        encoding="utf-8",
    )
    cfg = load(_write(tmp_path, VALID))
    gates = cfg.all_gates()
    assert "lint" in gates and gates["lint"].timeout_s == 10
