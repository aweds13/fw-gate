"""唯一一张退出码表（照骨架设计 §③.1 / 术语表 §1）。

为什么单独一个模块：现在本仓有**四套互不兼容**的退出码表，`1` 与 `3` 同码不同义。
框架的口径是 **一张表、全部命令共用**，配置里用 `[exit_codes].table_version` 引用它的版本。

★ 只用 `0–255`（POSIX 只保留低 8 位：`wait()` 只看 `status & 0xFF`）。
★ **永不发** `126` / `127` / `128+N` —— 那三个由 shell / 信号层定义，程序自己发会与
  「命令没找到 / 被杀」混淆（见术语表 §1「三个雷区」）。

本模块是**纯常量 + 纯函数**：不 print、不 sys.exit、不读全局状态。
"""

from __future__ import annotations

from enum import IntEnum, unique

# 表版本：改这张表就要改它，引用它的配置不静默漂（骨架设计 §⑤.3）。
TABLE_VERSION = "0.1.0"


@unique
class ExitCode(IntEnum):
    """唯一退出码表（骨架设计 §③.1）。"""

    OK = 0
    """通过（POSIX exit status）。"""
    GATE_FAIL = 1
    """判据不通过：门红 / 审计红 / 检查报错（POSIX 惯例：grep/diff 的非 0 = 有差异）。"""
    USAGE = 2
    """用法 / 参数错。★ out-of-spec：sysexits.h 用 64 EX_USAGE；本表暂留 2。"""
    RESOURCE = 3
    """资源闸拒跑（内存 / 并发不够）。★ out-of-spec：近 69 EX_UNAVAILABLE / 75 EX_TEMPFAIL。"""
    POLICY = 4
    """被策略拒绝（缺 --allow-write / 越界域 / 白名单外模型）。语义对齐 77 EX_NOPERM。"""
    PRECONDITION = 5
    """前置条件缺失（文件 / 段 / 键不存在；可修了再来）。语义对齐 66 EX_NOINPUT + 78 EX_CONFIG。"""
    INTERRUPTED = 6
    """被外部打断（超时 / 被掐 / 撞上限；本轮不算数，可续跑）。语义对齐 75 EX_TEMPFAIL。"""
    ALL_DOWN = 7
    """资源全挂，停止（模型白名单全被限流）。★ out-of-spec：与 6 的「可续跑」语义相反。"""
    TIMEOUT = 124
    """单道门硬超时（到点掐整棵进程树）。GNU timeout 约定；本表沿用 run_gates.py 文件头。"""


# 我们发的码（完整集合）。
OUR_CODES: frozenset[int] = frozenset(int(c) for c in ExitCode)

# shell / 信号层保留：程序**不许**主动发。
SHELL_RESERVED: frozenset[int] = frozenset({126, 127}) | frozenset(range(128, 256))


def is_ours(code: int) -> bool:
    """这个码是我们发的（在白名单里）还是 shell 发的？"""
    return code in OUR_CODES


def is_shell_reserved(code: int) -> bool:
    """这个码是否由 shell / 信号层定义（我们永不发）？"""
    return code in SHELL_RESERVED


_DESCRIPTIONS: dict[int, str] = {
    int(ExitCode.OK): "通过",
    int(ExitCode.GATE_FAIL): "判据不通过（门红）",
    int(ExitCode.USAGE): "用法 / 参数错",
    int(ExitCode.RESOURCE): "资源闸拒跑",
    int(ExitCode.POLICY): "被策略拒绝",
    int(ExitCode.PRECONDITION): "前置条件缺失",
    int(ExitCode.INTERRUPTED): "被外部打断（可续跑）",
    int(ExitCode.ALL_DOWN): "资源全挂，停止（不自动重试）",
    int(ExitCode.TIMEOUT): "单道门硬超时",
    126: "shell：命令找到但不可执行（不是我们发的）",
    127: "shell：命令未找到（不是我们发的）",
}


def describe(code: int) -> str:
    """给一个退出码一句人话；未知码明确写「未知」，不猜。"""
    if is_shell_reserved(code) and code not in _DESCRIPTIONS:
        return f"shell / 信号层保留（不是我们发的）：{code}"
    return _DESCRIPTIONS.get(code, f"未知退出码：{code}")
