"""门运行器的用例：真跑子进程（通过 / 失败 / 硬超时），以及示例仓端到端。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from framework.config import load
from framework.gates import GateSpec, Verdict, run_gate, run_gates

FRAMEWORK = Path(__file__).resolve().parents[1]
EXAMPLE = FRAMEWORK / "examples" / "minimal-notes"


def _spec(cmd, **kw) -> GateSpec:
    base = dict(name="t", cmd=tuple(cmd), inputs=(), nail="x::y", reuse="never",
                stage="light", timeout_s=30)
    base.update(kw)
    return GateSpec(**base)


def test_real_gate_passes(tmp_path: Path):
    res = run_gate(_spec([sys.executable, "-c", "print('hi')"]),
                   repo_root=tmp_path, logs_dir=tmp_path / "logs")
    assert res.verdict == Verdict.PASS.value and res.exit_code == 0
    assert (tmp_path / "logs" / "t.log").is_file()


def test_real_gate_fails_on_nonzero(tmp_path: Path):
    res = run_gate(_spec([sys.executable, "-c", "import sys; sys.exit(1)"]),
                   repo_root=tmp_path, logs_dir=tmp_path / "logs")
    assert res.verdict == Verdict.FAIL.value


def test_real_gate_hard_timeout(tmp_path: Path):
    res = run_gate(_spec([sys.executable, "-c", "import time; time.sleep(5)"], timeout_s=1),
                   repo_root=tmp_path, logs_dir=tmp_path / "logs")
    assert res.timed_out is True
    assert res.exit_code == 124
    assert res.verdict == Verdict.FAIL.value


def test_input_hash_changes_with_content(tmp_path: Path):
    from framework.gates import input_hash
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    spec = _spec([sys.executable, "-c", "pass"], inputs=("a.py",))
    h1 = input_hash(spec, tmp_path)
    (tmp_path / "a.py").write_text("x = 2\n", encoding="utf-8")
    h2 = input_hash(spec, tmp_path)
    assert h1 != h2 and h1 is not None


def test_input_hash_none_when_no_inputs(tmp_path: Path):
    from framework.gates import input_hash
    assert input_hash(_spec([sys.executable, "-c", "pass"]), tmp_path) is None


def _copy_example(tmp_path: Path) -> Path:
    dst = tmp_path / "repo"
    shutil.copytree(EXAMPLE, dst, ignore=shutil.ignore_patterns("__pycache__", ".pipe"))
    return dst


def test_example_repo_gate_is_green(tmp_path: Path):
    """端到端：把示例仓复制到临时目录，按它自己的配置跑门 —— 必须绿，且出 JUnit。"""
    repo = _copy_example(tmp_path)
    cfg = load(repo / "pipeline.toml")
    run = run_gates(cfg)
    assert run.overall() == Verdict.PASS, [r.to_dict() for r in run.results]
    tests = [r for r in run.results if r.name == "tests"]
    assert tests and tests[0].collected and tests[0].collected > 0
    assert (repo / ".pipe" / "evidence" / "junit" / "tests.xml").is_file()
