"""`pipe` —— 薄 CLI（卡 179 §②）。

只做三件事：**解析参数 → 调库 → 把库结果映射成退出码**。业务逻辑一律在
`framework/src/framework/**`（判据：把本文件删掉，库仍然可测）。

约定（照术语表 §2）：
  - `stdout` 只放**数据**；`stderr` 只放**诊断**。
  - **不弹交互式提问**；`--help` 自描述且含退出码表。
  - 每条命令都有 `--json`：**人读的文案**与**机器读的结构**分开，字段名稳定。
  - 退出码照唯一一张表（`framework.exit_codes`）。

本文件可**直接执行**（`python framework/cli/main.py --help`）—— 顶部把本仓 `src/` 与本目录
加进 `sys.path`，这样没装包也能跑（`pyproject.toml` 里另注册了 `pipe` 控制台入口）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_FRAMEWORK_ROOT = _HERE.parent
for _p in (str(_FRAMEWORK_ROOT / "src"), str(_FRAMEWORK_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from framework import __version__, claim, gates, land, ledger, scaffold, trace  # noqa: E402
from framework.config import ConfigError, load  # noqa: E402
from framework.exit_codes import ExitCode  # noqa: E402
from framework.pending import PendingError  # noqa: E402

EXIT_TABLE = """退出码（唯一一张表）：
  0    通过
  1    判据不通过（门红 / 审计红）
  2    用法 / 参数错
  3    资源闸拒跑
  4    被策略拒绝（越界 / 未授权）
  5    前置条件缺失（文件 / 段 / 键不存在；含「薄壳未实现」）
  6    被外部打断（可续跑）
  7    资源全挂，停止
  124  单道门硬超时
（126 / 127 / 128+N 由 shell / 信号层发，我们永不发。）"""


def _emit(json_mode: bool, payload: dict, lines: list[str]) -> None:
    """stdout 输出：`--json` 给结构化，否则给人读文案。"""
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in lines:
            print(line)


def _diag(message: str) -> None:
    print(message, file=sys.stderr)


def _die(message: str, code: int, json_mode: bool, *, kind: str = "error") -> int:
    if json_mode:
        print(json.dumps({"error": {"kind": kind, "message": message, "exit_code": code}},
                         ensure_ascii=False, indent=2))
    else:
        _diag(f"错误：{message}")
    return code


def _load_or_die(config_path: str | None, json_mode: bool):
    """读配置；失败返回 (None, exit_code)。成功返回 (Config, 0)。"""
    try:
        return load(config_path), int(ExitCode.OK)
    except ConfigError as exc:
        return None, _die(str(exc), int(ExitCode.PRECONDITION), json_mode, kind="config")


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

def _cmd_init(args: argparse.Namespace) -> int:
    try:
        written = scaffold.init(args.dir, template=args.template, force=args.force)
    except scaffold.ScaffoldError as exc:
        return _die(str(exc), exc.exit_code, args.json, kind="scaffold")
    _emit(args.json,
          {"command": "init", "dir": str(Path(args.dir).resolve()), "template": args.template,
           "files": written, "count": len(written)},
          [f"铺出 {len(written)} 个文件到 {Path(args.dir).resolve()}（模板 {args.template}）",
           *[f"  + {p}" for p in written]])
    return int(ExitCode.OK)


def _cmd_gate(args: argparse.Namespace) -> int:
    cfg, code = _load_or_die(args.config, args.json)
    if cfg is None:
        return code
    try:
        run = gates.run_gates(cfg, only=args.only)
    except KeyError as exc:
        return _die(str(exc), int(ExitCode.USAGE), args.json, kind="usage")
    gates.write_state(cfg, run)
    overall = run.overall()
    ok = overall == gates.Verdict.PASS
    lines = [f"门禁总判决：{overall.value}（{'绿' if ok else '非绿'}）"]
    for r in run.results:
        verdict = r.verdict if r.verdict is not None else "—"
        reused = " [复用]" if r.reused else ""
        lines.append(f"  {r.name:<16} {r.run_state:<8} {verdict:<13} exit={r.exit_code} "
                     f"{r.seconds:>6.2f}s{reused}")
    _emit(args.json, run.to_dict(), lines)
    return int(ExitCode.OK) if ok else int(ExitCode.GATE_FAIL)


def _cmd_doctor(args: argparse.Namespace) -> int:
    cfg, code = _load_or_die(args.config, args.json)
    if cfg is None:
        return code
    specs = cfg.all_gates()
    rows = []
    all_teeth = True
    for name in sorted(specs):
        has_teeth, rc, reason = gates.run_nail(cfg, specs[name])
        all_teeth = all_teeth and has_teeth
        rows.append({"name": name, "nail": specs[name].nail,
                     "has_teeth": has_teeth, "exit_code": rc, "detail": reason})
    lines = [f"金丝雀自检：{len(rows)} 道门，"
             f"{'全部有牙' if all_teeth else '有门失效（判据退化成注释）'}"]
    for row in rows:
        lines.append(f"  {row['name']:<16} {'有牙' if row['has_teeth'] else '失效'}  {row['detail']}")
    _emit(args.json, {"command": "doctor", "all_have_teeth": all_teeth, "gates": rows}, lines)
    return int(ExitCode.OK) if all_teeth else int(ExitCode.GATE_FAIL)


def _cmd_card_new(args: argparse.Namespace) -> int:
    cfg, code = _load_or_die(args.config, args.json)
    if cfg is None:
        return code
    try:
        out = scaffold.new_card(
            cards_dir=cfg.cards["cards_dir"],
            spec_template=cfg.cards["spec_template"],
            card_id=args.id,
            title=args.title,
            domain=args.domain or [],
        )
    except scaffold.ScaffoldError as exc:
        return _die(str(exc), exc.exit_code, args.json, kind="scaffold")
    _emit(args.json,
          {"command": "card new", "card_id": args.id, "spec_path": str(out),
           "domain": args.domain or []},
          [f"生成卡：{out}"])
    return int(ExitCode.OK)


def _cmd_claim(args: argparse.Namespace) -> int:
    cfg, code = _load_or_die(args.config, args.json)
    if cfg is None:
        return code
    try:
        result = claim.submit(
            task=args.task, member=args.member, status=args.status,
            files=args.files or [], why=args.why or "", evidence=args.evidence or "",
            claims_dir=cfg.cards["claims_dir"],
        )
    except PendingError as exc:
        return _die(str(exc), int(ExitCode.PRECONDITION), args.json, kind="not-implemented")
    _emit(args.json, {"command": "claim", "task": result.task, "member": result.member,
                      "status": result.status, "accepted": result.accepted},
          [f"申报：{result.task}/{result.member} {result.status} accepted={result.accepted}"])
    return int(ExitCode.OK)


def _cmd_land(args: argparse.Namespace) -> int:
    cfg, code = _load_or_die(args.config, args.json)
    if cfg is None:
        return code
    try:
        steps = land.land(task=args.task, repo_root=cfg.repo_root, dry_run=args.dry_run)
    except PendingError as exc:
        return _die(str(exc), int(ExitCode.PRECONDITION), args.json, kind="not-implemented")
    _emit(args.json, {"command": "land", "steps": [s.__dict__ for s in steps]},
          [f"集成与发布：{len(steps)} 步"])
    return int(ExitCode.OK)


def _cmd_ledger_check(args: argparse.Namespace) -> int:
    cfg, code = _load_or_die(args.config, args.json)
    if cfg is None:
        return code
    try:
        results = ledger.check(cfg.paths["ledger"], commit=args.commit, missing_only=args.missing)
    except PendingError as exc:
        return _die(str(exc), int(ExitCode.PRECONDITION), args.json, kind="not-implemented")
    _emit(args.json, {"command": "ledger check", "results": [r.__dict__ for r in results]},
          [f"台账：{len(results)} 条"])
    return int(ExitCode.OK)


def _cmd_trace_seal(args: argparse.Namespace) -> int:
    cfg, code = _load_or_die(args.config, args.json)
    if cfg is None:
        return code
    try:
        result = trace.seal(repo_root=cfg.repo_root, reason=args.reason,
                            algorithm=cfg.seal["algorithm"])
    except PendingError as exc:
        return _die(str(exc), int(ExitCode.PRECONDITION), args.json, kind="not-implemented")
    _emit(args.json, {"command": "trace seal", "tree": result.tree, "rev": result.rev,
                      "algorithm": result.algorithm}, [f"封存：{result.tree}"])
    return int(ExitCode.OK)


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipe",
        description="pipe —— 可带走的管线：核心库 + 薄 CLI（框架版本 " + __version__ + "）",
        epilog=EXIT_TABLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"pipe {__version__}")
    parser.add_argument("--config", help="pipeline.toml 路径（默认读 $PIPELINE_TOML 或 ./pipeline.toml）")
    parser.add_argument("--json", action="store_true", help="输出机器可读的结构化 JSON")
    sub = parser.add_subparsers(dest="command", metavar="<命令>")

    p_init = sub.add_parser("init", help="把模板仓铺到一个目录（幂等：第二次拒绝或逐字节相同）")
    p_init.add_argument("--template", default="minimal", help="模板名（默认 minimal）")
    p_init.add_argument("--dir", default=".", help="目标目录（默认当前目录）")
    p_init.add_argument("--force", action="store_true", help="允许覆盖已存在文件（目标必须在仓内）")
    p_init.set_defaults(func=_cmd_init)

    p_gate = sub.add_parser("gate", help="按配置跑门（并发 / 每门硬超时 / 三值判决）")
    p_gate.add_argument("--only", nargs="+", metavar="门名", help="只跑这些门")
    p_gate.set_defaults(func=_cmd_gate)

    p_doctor = sub.add_parser("doctor", help="金丝雀自检：对每道门真跑它的反例钉子")
    p_doctor.set_defaults(func=_cmd_doctor)

    p_card = sub.add_parser("card", help="卡相关")
    card_sub = p_card.add_subparsers(dest="card_command", metavar="<子命令>")
    p_card_new = card_sub.add_parser("new", help="从模板生成一张卡")
    p_card_new.add_argument("--id", required=True, help="卡号")
    p_card_new.add_argument("--title", required=True, help="标题")
    p_card_new.add_argument("--domain", nargs="*", metavar="路径", help="权威域（文件路径）")
    p_card_new.set_defaults(func=_cmd_card_new)

    p_claim = sub.add_parser("claim", help="提交一条完成申报（薄壳：未实现则报错）")
    p_claim.add_argument("--task", required=True)
    p_claim.add_argument("--member", required=True)
    p_claim.add_argument("--status", required=True, choices=["success", "failed"])
    p_claim.add_argument("--files", nargs="*", metavar="路径")
    p_claim.add_argument("--why")
    p_claim.add_argument("--evidence")
    p_claim.set_defaults(func=_cmd_claim)

    p_land = sub.add_parser("land", help="集成与发布七步（薄壳：未实现则报错）")
    p_land.add_argument("--task", required=True)
    p_land.add_argument("--dry-run", action="store_true")
    p_land.set_defaults(func=_cmd_land)

    p_ledger = sub.add_parser("ledger", help="台账相关")
    ledger_sub = p_ledger.add_subparsers(dest="ledger_command", metavar="<子命令>")
    p_ledger_check = ledger_sub.add_parser("check", help="逐条求值台账证据（薄壳：未实现则报错）")
    p_ledger_check.add_argument("--all", action="store_true", help="只对账台账、重建进度")
    p_ledger_check.add_argument("--commit", help="只审某一笔")
    p_ledger_check.add_argument("--missing", action="store_true", help="只回报失败条目")
    p_ledger_check.set_defaults(func=_cmd_ledger_check)

    p_trace = sub.add_parser("trace", help="封存与事件")
    trace_sub = p_trace.add_subparsers(dest="trace_command", metavar="<子命令>")
    p_trace_seal = trace_sub.add_parser("seal", help="给当前提交树打封存指纹（薄壳：未实现则报错）")
    p_trace_seal.add_argument("--reason", required=True, help="为什么改封存（必填）")
    p_trace_seal.set_defaults(func=_cmd_trace_seal)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help(sys.stderr)
        return int(ExitCode.USAGE)
    try:
        return func(args)
    except ConfigError as exc:
        return _die(str(exc), int(ExitCode.PRECONDITION), getattr(args, "json", False), kind="config")
    except PendingError as exc:
        return _die(str(exc), int(ExitCode.PRECONDITION), getattr(args, "json", False), kind="not-implemented")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
