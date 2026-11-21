"""三值判决的用例 —— ★ 本文件含核心**反例钉子**：

    test_empty_collection_is_inconclusive_not_green

它跑一个真子进程（夹具），那夹具「一条样例都没收集到」；断言判决是 `inconclusive`**而不是绿**。
若有人把空集当绿（或只看退出码判 fail），这条会红。
"""

from __future__ import annotations

import sys
from pathlib import Path

from framework.gates import (
    GateResult,
    GateSpec,
    GatesRun,
    RunState,
    Verdict,
    classify,
    run_gate,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "empty_collector.py"


def _spec(**kw) -> GateSpec:
    base = dict(name="t", cmd=(sys.executable, "-c", "print('ok')"), inputs=(),
                nail="x::y", reuse="never", stage="light", timeout_s=30)
    base.update(kw)
    return GateSpec(**base)


# -- 纯函数 classify ---------------------------------------------------------

def test_classify_not_run_has_no_verdict():
    state, verdict, _ = classify(ran=False, timed_out=False, exit_code=None, exit_ok=(0,), collected=None)
    assert state == RunState.NOT_RUN
    assert verdict is None  # ★ not-run 不是一种判决


def test_classify_pass_requires_items():
    state, verdict, _ = classify(ran=True, timed_out=False, exit_code=0, exit_ok=(0,), collected=3)
    assert state == RunState.RAN and verdict == Verdict.PASS


def test_classify_fail_on_nonzero():
    _, verdict, _ = classify(ran=True, timed_out=False, exit_code=1, exit_ok=(0,), collected=2)
    assert verdict == Verdict.FAIL


def test_classify_timeout_is_fail():
    _, verdict, _ = classify(ran=True, timed_out=True, exit_code=124, exit_ok=(0,), collected=None)
    assert verdict == Verdict.FAIL


def test_classify_empty_set_is_inconclusive():
    _, verdict, why = classify(ran=True, timed_out=False, exit_code=5, exit_ok=(0,), collected=0)
    assert verdict == Verdict.INCONCLUSIVE
    assert "空集" in why


# -- ★ 核心反例钉子：真跑子进程、真空集 -------------------------------

def test_empty_collection_is_inconclusive_not_green(tmp_path: Path):
    """★ 夹具「一条都没收集到」→ 必须判 `inconclusive`，**不许绿灯**，也**不许**与 not-run 混。"""
    junit_dir = tmp_path / "junit"
    spec = _spec(
        name="tests",
        cmd=(sys.executable, str(FIXTURE), str(junit_dir / "tests.xml")),
        exit_ok=(0,),
        emits=("junit",),
    )
    res = run_gate(spec, repo_root=tmp_path, logs_dir=tmp_path / "logs", junit_dir=junit_dir)
    assert res.run_state == RunState.RAN.value
    assert res.collected == 0
    assert res.verdict == Verdict.INCONCLUSIVE.value, res.reason
    assert res.verdict != Verdict.PASS.value


def test_empty_collection_is_not_not_run(tmp_path: Path):
    """空集是「跑了但判不了」，**不是**「没跑」——两者必须分得开。"""
    junit_dir = tmp_path / "junit"
    spec = _spec(cmd=(sys.executable, str(FIXTURE), str(junit_dir / "tests.xml")),
                 exit_ok=(0,), emits=("junit",))
    res = run_gate(spec, repo_root=tmp_path, logs_dir=tmp_path / "logs", junit_dir=junit_dir)
    assert res.run_state == RunState.RAN.value
    assert res.verdict != RunState.NOT_RUN.value


def test_missing_runtime_is_not_run_not_pass(tmp_path: Path):
    """运行时依赖缺失 → not_run（**没有判决**），绝不是 pass。"""
    spec = _spec(needs_runtime=("definitely-not-a-real-runtime-xyz",))
    res = run_gate(spec, repo_root=tmp_path, logs_dir=tmp_path / "logs")
    assert res.run_state == RunState.NOT_RUN.value
    assert res.verdict is None


def test_overall_treats_blocking_not_run_as_inconclusive():
    """阻断门 not-run 时，总判决**不许**是绿 —— 折成 inconclusive。"""
    run = GatesRun(results=[
        GateResult(name="a", stage="light", blocking=True, run_state=RunState.NOT_RUN.value,
                   verdict=None, exit_code=None, seconds=0.0, timed_out=False, collected=None,
                   input_hash=None, reused=False, reason="缺依赖", emits=()),
    ])
    assert run.overall() == Verdict.INCONCLUSIVE


def test_overall_worst_is_fail():
    run = GatesRun(results=[
        GateResult(name="a", stage="light", blocking=True, run_state=RunState.RAN.value,
                   verdict=Verdict.PASS.value, exit_code=0, seconds=0.0, timed_out=False,
                   collected=1, input_hash=None, reused=False, reason="ok", emits=()),
        GateResult(name="b", stage="light", blocking=True, run_state=RunState.RAN.value,
                   verdict=Verdict.INCONCLUSIVE.value, exit_code=5, seconds=0.0, timed_out=False,
                   collected=0, input_hash=None, reused=False, reason="空集", emits=()),
        GateResult(name="c", stage="light", blocking=True, run_state=RunState.RAN.value,
                   verdict=Verdict.FAIL.value, exit_code=1, seconds=0.0, timed_out=False,
                   collected=2, input_hash=None, reused=False, reason="红", emits=()),
    ])
    assert run.overall() == Verdict.FAIL


def test_non_blocking_gate_does_not_affect_overall():
    run = GatesRun(results=[
        GateResult(name="info", stage="light", blocking=False, run_state=RunState.RAN.value,
                   verdict=Verdict.FAIL.value, exit_code=1, seconds=0.0, timed_out=False,
                   collected=None, input_hash=None, reused=False, reason="信息性", emits=()),
    ])
    assert run.overall() == Verdict.PASS
