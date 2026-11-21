"""门（gate）执行器：并发跑门、每门硬超时、记输入面、结果落盘、**三值判决**。

★ 三值判决（照骨架设计 §2.1 / 术语表 #13）：
  - `pass`：拿到了通过证据（退出码落在 `exit_ok` 里，**且**收集到的样例数 > 0）。
  - `fail`：拿到了**不通过**的证据（退出码不在 `exit_ok`、或超时）。
  - `inconclusive`：**判不了**（例：一条样例都没收集到 —— 空集）。
  ★ `inconclusive` **绝不许当成 `pass`**；它**也不等于** `not-run`（没跑是 RunState，不是 Verdict）。

★ `not-run` 是**运行状态**，不是判决：运行时依赖缺失（如没装 node）时记 `not_run`，
  **不许静默跳过当通过**（骨架设计 §2.1 的 `needs_runtime`）。

本模块是**纯库**：不 print、不 `sys.exit`、不读全局状态。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from .config import Config, GateSpec

# 每道门的日志/状态落盘时用的子目录名（相对 evidence_dir / logs_dir）。
STATE_SCHEMA = "pipe/1"


class Verdict(str, Enum):
    """三值判决（ISO/IEC/IEEE 29119-3：Pass / Fail / Inconclusive）。"""

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class RunState(str, Enum):
    """运行状态：跑了没跑。★ 与 Verdict 正交，`not_run` 不是一种判决。"""

    RAN = "ran"
    NOT_RUN = "not_run"


def classify(
    *,
    ran: bool,
    timed_out: bool,
    exit_code: int | None,
    exit_ok: tuple[int, ...],
    collected: int | None,
) -> tuple[RunState, Verdict | None, str]:
    """把「一次运行的读数」判成 (运行状态, 判决, 原因)。

    判据顺序（先判「有没有跑」→ 再判「超时」→ 再判「空集」→ 最后看退出码）：
      1. `ran=False` → (`not_run`, None, ...)：没跑，**没有判决**。
      2. `timed_out=True` → (`ran`, fail, "超时")。
      3. `collected == 0` → (`ran`, **inconclusive**, "空集：一条样例都没收集到")。
      4. `exit_code in exit_ok` → (`ran`, pass, ...)。
      5. 其余 → (`ran`, fail, ...)。
    """
    if not ran:
        return RunState.NOT_RUN, None, "未运行（运行时依赖缺失）—— 没有判决，不算通过"
    if timed_out:
        return RunState.RAN, Verdict.FAIL, "硬超时"
    if collected is not None and collected == 0:
        return RunState.RAN, Verdict.INCONCLUSIVE, "空集：一条样例都没收集到 —— 无法判定，不许当绿"
    if exit_code is not None and exit_code in exit_ok:
        return RunState.RAN, Verdict.PASS, f"退出码 {exit_code} 在 exit_ok={list(exit_ok)} 内"
    return RunState.RAN, Verdict.FAIL, f"退出码 {exit_code} 不在 exit_ok={list(exit_ok)} 内"


@dataclass
class GateResult:
    """一道门跑完的读数。"""

    name: str
    stage: str
    blocking: bool
    run_state: str
    verdict: str | None
    exit_code: int | None
    seconds: float
    timed_out: bool
    collected: int | None
    input_hash: str | None
    reused: bool
    reason: str
    log_path: str | None = None
    emits: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["emits"] = list(self.emits)
        return d


@dataclass
class GatesRun:
    """一趟门禁的全部结果 + 总判决。"""

    results: list[GateResult] = field(default_factory=list)

    def overall(self) -> Verdict:
        """总判决：**阻断门**里的最坏值（fail > inconclusive > pass）。

        `not_run` 的阻断门**不算通过** → 折成 inconclusive（判不了就别报绿）。
        """
        blocking = [r for r in self.results if r.blocking]
        if not blocking:
            return Verdict.PASS
        worst = Verdict.PASS
        for r in blocking:
            v = r.verdict
            if r.run_state == RunState.NOT_RUN:
                v = Verdict.INCONCLUSIVE
            if v == Verdict.FAIL:
                return Verdict.FAIL
            if v == Verdict.INCONCLUSIVE:
                worst = Verdict.INCONCLUSIVE
        return worst

    def to_dict(self) -> dict:
        return {
            "schema": STATE_SCHEMA,
            "overall": self.overall().value,
            "ok": self.overall() == Verdict.PASS,
            "gates": [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# 运行时依赖探测
# ---------------------------------------------------------------------------

def _probe_python() -> str | None:
    return sys.executable if shutil.which(sys.executable) or Path(sys.executable).exists() else None


def _probe_node() -> str | None:
    return shutil.which("node")


def probe_runtime(name: str) -> str | None:
    """探测一个运行时依赖；找到返回路径，找不到返回 None（**不猜、不兜底**）。"""
    if name == "python":
        return _probe_python()
    if name == "node":
        return _probe_node()
    if name == "psutil":
        try:
            import psutil  # noqa: F401
        except ImportError:
            return None
        return "psutil"
    # 未知运行时名：按 PATH 里的可执行文件找；找不到就是没有。
    return shutil.which(name)


def missing_runtimes(spec: GateSpec) -> list[str]:
    return [r for r in spec.needs_runtime if probe_runtime(r) is None]


# ---------------------------------------------------------------------------
# 输入面（输入哈希 → 增量执行判据）
# ---------------------------------------------------------------------------

def input_hash(spec: GateSpec, repo_root: Path) -> str | None:
    """按 `inputs` 的 glob 现算输入面摘要。

    `inputs` 为空 → 返回 None（口径：**空 = 每次真跑**，不复用）。
    """
    if not spec.inputs:
        return None
    digest = hashlib.sha256()
    files: list[Path] = []
    for pattern in spec.inputs:
        files.extend(sorted(repo_root.glob(pattern)))
    seen: set[str] = set()
    for f in files:
        if not f.is_file():
            continue
        rel = f.relative_to(repo_root).as_posix() if f.is_relative_to(repo_root) else f.as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(f.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# JUnit XML → 收集到的样例数（标准产物，不含框架私有格式）
# ---------------------------------------------------------------------------

def count_junit(path: Path) -> int | None:
    """从 JUnit XML 数 `tests`。数不出来（文件缺 / 不是 XML）→ None（不猜）。"""
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if suites:
        total = 0
        for s in suites:
            if s is root and root.tag != "testsuite":
                continue
            raw = s.get("tests")
            if raw is None:
                return None
            total += int(raw)
        return total
    return sum(1 for _ in root.iter("testcase"))


# ---------------------------------------------------------------------------
# 跑一道门
# ---------------------------------------------------------------------------

def _kill_tree(pid: int) -> None:
    """掐整棵进程树（照长任务协议：按 PID，不按进程名 —— 名字会误伤同名进程）。"""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True, check=False,
        )
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:  # pragma: no cover
            pass


def run_gate(
    spec: GateSpec,
    *,
    repo_root: Path,
    logs_dir: Path,
    junit_dir: Path | None = None,
    env: dict[str, str] | None = None,
) -> GateResult:
    """跑一道门（阻塞式单门）。返回 `GateResult`。

    - 运行时依赖缺失 → `not_run`（**不是** pass）。
    - 硬超时 → 掐整棵进程树，`exit_code=124`、`timed_out=True`、判决 `fail`。
    - `emits` 含 `junit` 时，从 `<junit_dir>/<门名>.xml` 数样例数；为 0 → `inconclusive`。
    """
    start = time.monotonic()
    ih = input_hash(spec, repo_root)

    missing = missing_runtimes(spec)
    if missing:
        return GateResult(
            name=spec.name, stage=spec.stage, blocking=spec.blocking,
            run_state=RunState.NOT_RUN.value, verdict=None, exit_code=None,
            seconds=0.0, timed_out=False, collected=None, input_hash=ih, reused=False,
            reason=f"缺运行时依赖 {missing} —— 记 not_run，不当通过", emits=spec.emits,
        )

    needs_junit = "junit" in spec.emits
    junit_path = (junit_dir / f"{spec.name}.xml") if (needs_junit and junit_dir) else None
    if junit_path is not None:
        junit_path.parent.mkdir(parents=True, exist_ok=True)
        if junit_path.is_file():
            junit_path.unlink()  # 清掉上一趟的，免得旧文件冒充本趟证据

    child_env = dict(os.environ)
    if env:
        child_env.update(env)

    run_cwd = repo_root if repo_root.is_dir() else Path.cwd()
    timed_out = False
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.Popen(
            list(spec.cmd),
            cwd=str(run_cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=child_env,
        )
    except FileNotFoundError as exc:
        return GateResult(
            name=spec.name, stage=spec.stage, blocking=spec.blocking,
            run_state=RunState.RAN.value, verdict=Verdict.FAIL.value, exit_code=None,
            seconds=time.monotonic() - start, timed_out=False, collected=None,
            input_hash=ih, reused=False, reason=f"命令找不到：{exc}", emits=spec.emits,
        )

    try:
        out_b, err_b = proc.communicate(timeout=spec.timeout_s)
        exit_code = proc.returncode
        stdout = out_b.decode("utf-8", "replace")
        stderr = err_b.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc.pid)
        try:
            out_b, err_b = proc.communicate(timeout=10)
            stdout = out_b.decode("utf-8", "replace")
            stderr = err_b.decode("utf-8", "replace")
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()
        exit_code = 124

    seconds = time.monotonic() - start
    collected: int | None = None
    if not timed_out and junit_path is not None:
        collected = count_junit(junit_path)

    run_state, verdict, reason = classify(
        ran=True, timed_out=timed_out, exit_code=exit_code,
        exit_ok=spec.exit_ok, collected=collected,
    )

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{spec.name}.log"
    log_path.write_text(
        f"# gate={spec.name} stage={spec.stage} verdict={verdict.value if verdict else None}\n"
        f"# cmd={list(spec.cmd)}\n"
        f"# exit_code={exit_code} timed_out={timed_out} seconds={seconds:.2f} "
        f"collected={collected} input_hash={ih}\n"
        f"# --- stdout ---\n{stdout}\n# --- stderr ---\n{stderr}\n",
        encoding="utf-8",
    )

    return GateResult(
        name=spec.name, stage=spec.stage, blocking=spec.blocking,
        run_state=run_state.value, verdict=verdict.value if verdict else None,
        exit_code=exit_code, seconds=round(seconds, 3), timed_out=timed_out,
        collected=collected, input_hash=ih, reused=False, reason=reason,
        log_path=str(log_path), emits=spec.emits,
    )


def _load_reuse(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_reuse(path: Path, results: list[GateResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    for r in results:
        if r.reused:  # 沿用上一条记录，不覆盖
            continue
        data[r.name] = {
            "input_hash": r.input_hash,
            "verdict": r.verdict,
            "run_state": r.run_state,
            "exit_code": r.exit_code,
        }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_gates(
    config: Config,
    *,
    only: list[str] | None = None,
    max_concurrent: int | None = None,
) -> GatesRun:
    """按配置跑门（**并发**，每门硬超时）。返回 `GatesRun`。

    `only` 给了就只跑这些门；给了未声明的门名 → `KeyError`（调用方映射成用法错）。
    """
    gates = config.all_gates()
    if only is not None:
        unknown = [n for n in only if n not in gates]
        if unknown:
            raise KeyError(f"未声明的门：{unknown}（已声明：{sorted(gates)}）")
        chosen = [gates[n] for n in only]
    else:
        chosen = [gates[n] for n in sorted(gates)]

    reuse_path = config.paths["gates_reuse"]
    reuse = _load_reuse(reuse_path)
    junit_dir = None
    if "junit_dir" in config.reports:
        junit_dir = Path(config.reports["junit_dir"])

    results: list[GateResult] = []
    to_run: list[GateSpec] = []
    for spec in chosen:
        ih = input_hash(spec, config.repo_root)
        prev = reuse.get(spec.name)
        if spec.reuse == "hash" and prev and ih is not None and prev.get("input_hash") == ih:
            results.append(GateResult(
                name=spec.name, stage=spec.stage, blocking=spec.blocking,
                run_state=prev.get("run_state", RunState.RAN.value),
                verdict=prev.get("verdict"), exit_code=prev.get("exit_code"),
                seconds=0.0, timed_out=False, collected=None, input_hash=ih, reused=True,
                reason="输入面未变，沿用上次结果（增量执行）", emits=spec.emits,
            ))
        else:
            to_run.append(spec)

    workers = max_concurrent if max_concurrent is not None else int(config.resource.get("max_concurrent_gates", 2))
    workers = max(1, workers)
    if to_run:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for res in pool.map(
                lambda s: run_gate(s, repo_root=config.repo_root, logs_dir=config.paths["logs_dir"],
                                   junit_dir=junit_dir),
                to_run,
            ):
                results.append(res)

    results.sort(key=lambda r: r.name)
    run = GatesRun(results=results)
    _save_reuse(reuse_path, results)
    return run


def write_state(config: Config, run: GatesRun) -> Path:
    """把一趟门禁结果写到 `[paths].gates_state`（结构化产物）。返回路径。"""
    state_path = config.paths["gates_state"]
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(run.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state_path


def run_nail(config: Config, spec: GateSpec) -> tuple[bool, int, str]:
    """跑一道门的**反例钉子**（金丝雀自检）。

    ★ 钉子语义（本框架的定义，写死在 PIPELINE.md）：钉子是一条**喂进故意坏掉的样本、
    断言门会把它逮住**的用例。因此：
      - 钉子**通过（退出 0）** ⇒ 门**有牙**（正常）。
      - 钉子**失败（退出非 0）** ⇒ 门**失效**（判据退化成注释）。
    （骨架设计 §③.2 把这一句写成「钉子红 = 有牙」；本实现按卡 179 §④ 的用法取
     「断言成立 = 有牙」，两处措辞的冲突已在回报里点名。）

    返回 (有牙?, 退出码, 原因)。
    """
    cmd = [sys.executable, "-m", "pytest", spec.nail, "-q", "--no-header"]
    try:
        proc = subprocess.run(
            cmd, cwd=str(config.repo_root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=spec.timeout_s,
        )
    except subprocess.TimeoutExpired:
        return False, 124, f"钉子超时（>{spec.timeout_s}s）：{spec.nail}"
    except FileNotFoundError as exc:  # pragma: no cover
        return False, 127, f"跑钉子失败（命令找不到）：{exc}"
    if proc.returncode == 0:
        return True, 0, f"钉子通过（断言成立）：{spec.nail}"
    return False, proc.returncode, f"钉子失败（门失效）：{spec.nail}"
