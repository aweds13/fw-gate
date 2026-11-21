"""薄 CLI 的用例：真跑 `python cli/main.py`，核退出码与 `--json`（stdout 数据面）。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parents[1]
CLI = FRAMEWORK / "cli" / "main.py"
EXAMPLE = FRAMEWORK / "examples" / "minimal-notes"


def run_cli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def _copy_example(tmp_path: Path) -> Path:
    dst = tmp_path / "repo"
    shutil.copytree(EXAMPLE, dst, ignore=shutil.ignore_patterns("__pycache__", ".pipe"))
    return dst


def test_help_exits_zero_and_lists_exit_codes():
    p = run_cli("--help")
    assert p.returncode == 0
    assert "退出码" in p.stdout
    assert "pipe" in p.stdout


def test_no_command_is_usage_error():
    p = run_cli()
    assert p.returncode == 2


def test_init_then_second_init_refuses(tmp_path: Path):
    target = tmp_path / "proj"
    p1 = run_cli("init", "--dir", str(target))
    assert p1.returncode == 0, p1.stderr
    assert (target / "pipeline.toml").is_file()

    p2 = run_cli("init", "--dir", str(target))
    assert p2.returncode == 5  # 前置条件缺失（已存在）


def test_gate_on_example_is_green_and_json_parses(tmp_path: Path):
    repo = _copy_example(tmp_path)
    p = run_cli("--config", str(repo / "pipeline.toml"), "--json", "gate")
    assert p.returncode == 0, p.stderr
    payload = json.loads(p.stdout)
    assert payload["overall"] == "pass"
    assert payload["ok"] is True
    assert payload["gates"][0]["verdict"] == "pass"


def test_doctor_on_example_reports_teeth(tmp_path: Path):
    repo = _copy_example(tmp_path)
    p = run_cli("--config", str(repo / "pipeline.toml"), "--json", "doctor")
    assert p.returncode == 0, p.stderr
    payload = json.loads(p.stdout)
    assert payload["all_have_teeth"] is True
    assert payload["gates"][0]["has_teeth"] is True


def test_card_new_creates_file(tmp_path: Path):
    repo = _copy_example(tmp_path)
    p = run_cli("--config", str(repo / "pipeline.toml"), "card", "new",
                "--id", "T-42", "--title", "试试", "--domain", "src/notes/__init__.py")
    assert p.returncode == 0, p.stderr
    assert (repo / "cards" / "T-42.md").is_file()

    # 第二次同号 → 被策略拒绝（4），不覆盖
    p2 = run_cli("--config", str(repo / "pipeline.toml"), "card", "new",
                 "--id", "T-42", "--title", "再来")
    assert p2.returncode == 4


def test_missing_config_is_precondition_error(tmp_path: Path):
    p = run_cli("--config", str(tmp_path / "nope.toml"), "gate")
    assert p.returncode == 5


def test_thin_shell_commands_report_not_implemented(tmp_path: Path):
    repo = _copy_example(tmp_path)
    cfg = str(repo / "pipeline.toml")
    for args in (
        ("claim", "--task", "X", "--member", "M", "--status", "success"),
        ("land", "--task", "X"),
        ("ledger", "check"),
        ("trace", "seal", "--reason", "why"),
    ):
        p = run_cli("--config", cfg, "--json", *args)
        assert p.returncode == 5, (args, p.returncode, p.stdout, p.stderr)
        payload = json.loads(p.stdout)
        assert payload["error"]["kind"] == "not-implemented"


def test_gate_failure_exits_one(tmp_path: Path):
    (tmp_path / "gates.d").mkdir()
    (tmp_path / "gates.d" / "fail.toml").write_text(
        '[gate]\nname = "fail"\ncmd = ["' + sys.executable.replace("\\", "/") + '", "-c", "import sys; sys.exit(1)"]\n'
        'inputs = []\nnail = "x::y"\nreuse = "never"\nstage = "light"\ntimeout_s = 30\n',
        encoding="utf-8",
    )
    (tmp_path / "pipeline.toml").write_text(
        '[meta]\nschema_version = "0.1.0"\nframework_version = "0.1.0"\nproject_id = "p"\n'
        '[paths]\nledger = "ledger.toml"\ninvariants = "invariants.toml"\nevidence_dir = ".pipe/e"\n'
        'logs_dir = ".pipe/logs"\ngates_state = ".pipe/last.json"\ngates_reuse = ".pipe/reuse.json"\n'
        '[cards]\ncards_dir = "cards"\nspec_template = "t.md"\nbacklog = "backlog.toml"\n'
        'claims_dir = ".pipe/claims"\nauthoritative_domains = "backlog.toml"\n'
        '[gates]\ngates_dir = "gates.d"\n[workers]\nmodel_allowlist = ["m"]\ndefault_model = "m"\n'
        '[exit_codes]\ntable_version = "0.1.0"\n',
        encoding="utf-8",
    )
    p = run_cli("--config", str(tmp_path / "pipeline.toml"), "gate")
    assert p.returncode == 1, p.stderr
