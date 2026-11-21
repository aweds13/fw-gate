"""配置加载 + **严格** schema 校验（读 `pipeline.toml`）。

口径照本项目已立过的「白名单即 schema」：**缺键 / 拼错 / 未知键一律明确报错**，
绝不静默兜底。差异只有一处：设计书 §2.1 给部分可选键写了**文档化默认值**，这些默认值是 schema 的一部分，
不是「静默兜底」—— 拼错的键**不会**被当成默认值，而是当场报错（`additionalProperties: false` 的语义）。

本模块是**纯库**：不 print、不 `sys.exit`、不读全局状态（唯一例外是 `load()` 未传 `path` 时读
环境变量做旁路，这是**唯一的显式旁路**，不是默认值）。

校验对象 = `pipeline.schema.json`（JSON Schema 2020-12 骨架）的等价实现；两份必须一致。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "pipeline.toml"
ENV_OVERRIDE = "PIPELINE_TOML"

# 支持的配置 schema 主版本（骨架设计 §⑤.3：主版本不符 → 拒跑并给迁移命令）。
SUPPORTED_SCHEMA_MAJOR = "0"


class ConfigError(Exception):
    """配置读不了 / 缺键 / 未知键 / 值类型不对 / 跨字段矛盾 —— 明确报错，不静默、不兜底。"""


_MISSING = object()


@dataclass(frozen=True)
class FieldSpec:
    """一个配置字段的规格。kind 决定类型校验；choices 非空时限定取值。"""

    name: str
    kind: str  # str | int | number | bool | str_list | int_list
    required: bool
    default: Any = _MISSING
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class SectionSpec:
    name: str
    required: bool
    fields: tuple[FieldSpec, ...]


def _f(name: str, kind: str, required: bool, default: Any = _MISSING, choices: tuple[str, ...] = ()) -> FieldSpec:
    return FieldSpec(name=name, kind=kind, required=required, default=default, choices=choices)


# ---------------------------------------------------------------------------
# schema（= pipeline.schema.json 的等价实现）
# ---------------------------------------------------------------------------

SECTION_SPECS: dict[str, SectionSpec] = {
    "meta": SectionSpec("meta", True, (
        _f("schema_version", "str", True),
        _f("framework_version", "str", True),
        _f("project_id", "str", True),
        _f("project_name", "str", False, None),          # 默认 = project_id（跨字段）
        _f("repo_root", "str", False, "."),
        _f("default_branch", "str", False, "main"),
    )),
    "paths": SectionSpec("paths", True, (
        _f("ledger", "str", True),
        _f("invariants", "str", True),
        _f("evidence_dir", "str", True),
        _f("logs_dir", "str", True),
        _f("gates_state", "str", True),
        _f("gates_reuse", "str", True),
    )),
    "cards": SectionSpec("cards", True, (
        _f("cards_dir", "str", True),
        _f("spec_template", "str", True),
        _f("backlog", "str", True),
        _f("claims_dir", "str", True),
        _f("authoritative_domains", "str", True),
    )),
    "resource": SectionSpec("resource", False, (
        _f("min_free_gb", "number", False, 4.0),
        _f("max_concurrent_gates", "int", False, 2),
        _f("port_base", "int", False, 8531),
        _f("port_band", "int", True),                     # ★ 必填（铁律 37：整段空闲判据）
        _f("pytest_workers", "int", False, 0),
        _f("gate_lock_stale_s", "int", False, 10800),
    )),
    "workers": SectionSpec("workers", True, (
        _f("model_allowlist", "str_list", True),
        _f("default_model", "str", True),
        _f("max_turns_write", "int", False, 240),
        _f("max_turns_readonly", "int", False, 80),
        _f("watchdog_stall_s", "int", False, 480),
        _f("watchdog_busy_stall_s", "int", False, 1800),
        _f("watchdog_adaptive_max_s", "int", False, 3600),
        _f("heartbeat_s", "int", False, 120),
        _f("autocompact", "str", False, "1m"),
    )),
    "exit_codes": SectionSpec("exit_codes", True, (
        _f("table_version", "str", True),
        _f("table_path", "str", False, None),             # None = 用内置表
    )),
    "events": SectionSpec("events", False, (
        _f("format", "str", False, "ndjson", ("ndjson", "cloudevents")),
        _f("source_uri", "str", False, None),             # 默认 = pipe://<project_id>
        _f("ndjson_path", "str", False, None),            # 默认 = evidence_dir/"events.ndjson"
    )),
    "reports": SectionSpec("reports", False, (
        _f("sarif_dir", "str", False, None),              # 默认 = evidence_dir/"sarif"
        _f("junit_dir", "str", False, None),              # 默认 = evidence_dir/"junit"
        _f("coverage_format", "str", False, "cobertura", ("cobertura", "lcov")),
    )),
    "seal": SectionSpec("seal", False, (
        _f("ignore", "str_list", False, ("gates/**", "*.pyc", "__pycache__/**")),
        _f("algorithm", "str", False, "sha256", ("sha256",)),
    )),
}

# 门规格（[gates.<名>] 每个门 10 个键；文件式 gates.d/<名>.toml 的 [gate] 用同一套）。
GATE_REQUIRED = ("cmd", "inputs", "nail", "reuse", "stage", "timeout_s")
GATE_FIELDS: tuple[FieldSpec, ...] = (
    _f("cmd", "str_list", True),
    _f("inputs", "str_list", True),
    _f("nail", "str", True),
    _f("reuse", "str", True, _MISSING, ("hash", "never")),
    _f("stage", "str", True, _MISSING, ("light", "real", "browser")),
    _f("timeout_s", "int", True),
    _f("exit_ok", "int_list", False, (0,)),
    _f("blocking", "bool", False, True),
    _f("emits", "str_list", False, ()),
    _f("needs_runtime", "str_list", False, ()),
)


def _matches(value: Any, kind: str) -> bool:
    if kind == "str":
        return isinstance(value, str)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "str_list":
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    if kind == "int_list":
        return isinstance(value, list) and all(isinstance(x, int) and not isinstance(x, bool) for x in value)
    raise AssertionError(f"未知 kind：{kind}")  # pragma: no cover - 内部错误


def _kind_human(kind: str) -> str:
    return {
        "str": "字符串", "int": "整数", "number": "数字", "bool": "布尔",
        "str_list": "字符串数组", "int_list": "整数数组",
    }[kind]


@dataclass(frozen=True)
class GateSpec:
    """一道门的规格（照骨架设计 §2.1 的 10 个键）。"""

    name: str
    cmd: tuple[str, ...]
    inputs: tuple[str, ...]
    nail: str
    reuse: str
    stage: str
    timeout_s: int
    exit_ok: tuple[int, ...] = (0,)
    blocking: bool = True
    emits: tuple[str, ...] = ()
    needs_runtime: tuple[str, ...] = ()


def _parse_gate(name: str, table: dict[str, Any], where: str) -> GateSpec:
    """把一张门表解析成 GateSpec（缺键 / 未知键 / 类型错都抛 ConfigError）。"""
    legal = {f.name for f in GATE_FIELDS}
    unknown = sorted(set(table) - legal)
    if unknown:
        raise ConfigError(
            f"门 [{name}] 出现未知键 {unknown}（在 {where}；合法键：{sorted(legal)}）"
            f" —— 拼错了就报错，不静默忽略"
        )
    values: dict[str, Any] = {}
    for spec in GATE_FIELDS:
        if spec.name not in table:
            if spec.name in GATE_REQUIRED:
                raise ConfigError(
                    f"门 [{name}] 缺键 {spec.name}（在 {where}；该键必填，期望 {_kind_human(spec.kind)}）"
                )
            values[spec.name] = spec.default
            continue
        raw = table[spec.name]
        if not _matches(raw, spec.kind):
            raise ConfigError(
                f"门 [{name}] 键 {spec.name} 必须是{_kind_human(spec.kind)}（在 {where}；拿到 {raw!r}）"
            )
        if spec.choices and raw not in spec.choices:
            raise ConfigError(
                f"门 [{name}] 键 {spec.name} 取值必须是 {list(spec.choices)} 之一（在 {where}；拿到 {raw!r}）"
            )
        values[spec.name] = raw

    if not values["cmd"]:
        raise ConfigError(f"门 [{name}] 的 cmd 不许为空数组（在 {where}；argv 数组至少一条）")
    if not values["nail"].strip():
        raise ConfigError(f"门 [{name}] 的 nail 不许为空（在 {where}；判据随件走，没有钉子不许进门）")
    if values["timeout_s"] <= 0:
        raise ConfigError(f"门 [{name}] 的 timeout_s 必须 > 0（在 {where}；拿到 {values['timeout_s']}）")
    if not values["exit_ok"]:
        raise ConfigError(f"门 [{name}] 的 exit_ok 不许为空数组（在 {where}）")

    return GateSpec(
        name=name,
        cmd=tuple(values["cmd"]),
        inputs=tuple(values["inputs"]),
        nail=values["nail"],
        reuse=values["reuse"],
        stage=values["stage"],
        timeout_s=values["timeout_s"],
        exit_ok=tuple(values["exit_ok"]),
        blocking=values["blocking"],
        emits=tuple(values["emits"]),
        needs_runtime=tuple(values["needs_runtime"]),
    )


@dataclass
class Config:
    """一份已校验的 `pipeline.toml`。所有路径解析为 `Path`（相对 `repo_root`）。"""

    path: Path
    repo_root: Path
    meta: dict[str, Any]
    paths: dict[str, Path]
    cards: dict[str, Path]
    resource: dict[str, Any]
    workers: dict[str, Any]
    exit_codes: dict[str, Any]
    events: dict[str, Any]
    reports: dict[str, Path | Any]
    seal: dict[str, Any]
    gates: dict[str, GateSpec] = field(default_factory=dict)

    # -- 查表 / 解析 --------------------------------------------------------
    def resolve(self, rel: str) -> Path:
        """把一个相对路径解析为相对 `repo_root` 的绝对路径（绝对路径原样用）。"""
        p = Path(rel)
        return p if p.is_absolute() else (self.repo_root / p)

    def all_gates(self) -> dict[str, GateSpec]:
        """主文件 `[gates.<名>]` + `gates.d/*.toml` 合读；同名冲突 → ConfigError（设计 §⑤.1）。"""
        merged: dict[str, GateSpec] = dict(self.gates)
        gates_dir_raw = self.meta.get("_gates_dir")
        if gates_dir_raw:
            gdir = self.resolve(gates_dir_raw)
            if gdir.is_dir():
                for gate_file in sorted(gdir.glob("*.toml")):
                    spec = _load_gate_file(gate_file)
                    if spec.name in merged:
                        raise ConfigError(
                            f"门名冲突：{spec.name!r} 同时在主文件 [gates.{spec.name}] 与 "
                            f"{gate_file} 里声明（设计 §⑤.1：同名冲突 → 拒跑并点名）"
                        )
                    merged[spec.name] = spec
        return merged


def _load_gate_file(gate_file: Path) -> GateSpec:
    """读一个 `gates.d/<名>.toml`：单个 `[gate]` 表；缺 `name` 时用文件名（去扩展名）。"""
    try:
        raw = tomllib.loads(gate_file.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"门文件不是合法 TOML：{gate_file}：{exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("gate"), dict):
        raise ConfigError(f"门文件必须含一个 [gate] 表：{gate_file}")
    table = dict(raw["gate"])
    name = table.pop("name", None) or gate_file.stem
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"门文件的 name 必须是非空字符串：{gate_file}")
    return _parse_gate(name, table, where=str(gate_file))


def config_path(explicit: str | Path | None = None) -> Path:
    """当前生效的配置路径：显式给 > 环境变量 `PIPELINE_TOML` > 当前目录 `pipeline.toml`。"""
    if explicit is not None:
        return Path(explicit)
    raw = os.environ.get(ENV_OVERRIDE, "").strip()
    return Path(raw) if raw else Path.cwd() / CONFIG_FILENAME


def load(path: str | Path | None = None) -> Config:
    """读并**严格校验**一份 `pipeline.toml`，返回 `Config`。任何不合法都抛 `ConfigError`。"""
    cfg_path = config_path(path)
    if not cfg_path.is_file():
        raise ConfigError(
            f"配置不存在：{cfg_path}（期望一份含 [meta]/[paths]/[cards]/[gates]/[workers]/[exit_codes] 的 TOML；"
            f"先跑 `pipe init` 铺一份）"
        )
    try:
        raw = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"配置不是合法 TOML：{cfg_path}：{exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"配置顶层必须是 TOML 表：{cfg_path}")

    unknown_sections = sorted(set(raw) - set(SECTION_SPECS) - {"gates"})
    if unknown_sections:
        raise ConfigError(
            f"配置出现未知段 {unknown_sections}（在 {cfg_path}；合法段：{sorted(SECTION_SPECS) + ['gates']}）"
            f" —— 拼错都不允许"
        )

    values: dict[str, dict[str, Any]] = {}
    for section, spec in SECTION_SPECS.items():
        table = raw.get(section)
        present = table is not None
        if not present:
            if spec.required:
                raise ConfigError(f"配置缺段 [{section}]（在 {cfg_path}；该段必填）")
            table = {}
        if not isinstance(table, dict):
            raise ConfigError(f"[{section}] 必须是 TOML 表（在 {cfg_path}；拿到 {type(table).__name__}）")
        legal = {f.name for f in spec.fields}
        unknown = sorted(set(table) - legal)
        if unknown:
            raise ConfigError(
                f"配置出现未知键 {unknown}（在 {cfg_path} 的 [{section}]；合法键：{sorted(legal)}）"
                f" —— 拼错了就报错，不静默忽略"
            )
        filled: dict[str, Any] = {}
        for fspec in spec.fields:
            if fspec.name not in table:
                # 段缺失时只填「有默认值」的键；必填无默认的键留给下游（如 resource.port_band）。
                if present and fspec.required:
                    raise ConfigError(
                        f"配置缺键 {section}.{fspec.name}（在 {cfg_path}；该键必填，期望 {_kind_human(fspec.kind)}）"
                    )
                if fspec.default is not _MISSING:
                    filled[fspec.name] = fspec.default
                continue
            value = table[fspec.name]
            if not _matches(value, fspec.kind):
                raise ConfigError(
                    f"配置键 {section}.{fspec.name} 必须是{_kind_human(fspec.kind)}"
                    f"（在 {cfg_path}；拿到 {value!r}）"
                )
            if fspec.choices and value not in fspec.choices:
                raise ConfigError(
                    f"配置键 {section}.{fspec.name} 取值必须是 {list(fspec.choices)} 之一"
                    f"（在 {cfg_path}；拿到 {value!r}）"
                )
            filled[fspec.name] = value
        values[section] = filled

    # -- gates 段：gates_dir（必填）+ 内联 [gates.<名>] -----------------------
    gates_table = raw.get("gates")
    if gates_table is None:
        raise ConfigError(f"配置缺段 [gates]（在 {cfg_path}；该段必填，至少含 gates_dir）")
    if not isinstance(gates_table, dict):
        raise ConfigError(f"[gates] 必须是 TOML 表（在 {cfg_path}）")
    if "gates_dir" not in gates_table:
        raise ConfigError(f"配置缺键 gates.gates_dir（在 {cfg_path}；该键必填）")
    gates_dir = gates_table["gates_dir"]
    if not isinstance(gates_dir, str):
        raise ConfigError(f"配置键 gates.gates_dir 必须是字符串（在 {cfg_path}；拿到 {gates_dir!r}）")
    inline_gates: dict[str, GateSpec] = {}
    for gname, gtable in gates_table.items():
        if gname == "gates_dir":
            continue
        if not isinstance(gtable, dict):
            raise ConfigError(f"[gates.{gname}] 必须是 TOML 表（在 {cfg_path}）")
        inline_gates[gname] = _parse_gate(gname, gtable, where=f"{cfg_path} [gates.{gname}]")

    # -- schema_version 主版本闸（骨架设计 §⑤.3） ---------------------------
    schema_version = values["meta"]["schema_version"]
    major = schema_version.split(".", 1)[0]
    if major != SUPPORTED_SCHEMA_MAJOR:
        raise ConfigError(
            f"配置 schema_version={schema_version!r} 的主版本 {major!r} 不受支持"
            f"（框架要 {SUPPORTED_SCHEMA_MAJOR}.x；迁移命令：pipe init --upgrade）"
        )

    # -- 跨字段：默认值填充 ------------------------------------------------
    if values["meta"]["project_name"] is None:
        values["meta"]["project_name"] = values["meta"]["project_id"]
    if values["events"]["source_uri"] is None:
        values["events"]["source_uri"] = f"pipe://{values['meta']['project_id']}"

    # -- 路径解析 ----------------------------------------------------------
    repo_root_raw = values["meta"]["repo_root"]
    repo_root = Path(repo_root_raw)
    if not repo_root.is_absolute():
        repo_root = (cfg_path.parent / repo_root).resolve()

    def _resolve(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else (repo_root / p)

    evidence_dir = _resolve(values["paths"]["evidence_dir"])
    values["events"]["ndjson_path"] = (
        _resolve(values["events"]["ndjson_path"]) if values["events"]["ndjson_path"]
        else evidence_dir / "events.ndjson"
    )
    values["reports"]["sarif_dir"] = (
        _resolve(values["reports"]["sarif_dir"]) if values["reports"]["sarif_dir"]
        else evidence_dir / "sarif"
    )
    values["reports"]["junit_dir"] = (
        _resolve(values["reports"]["junit_dir"]) if values["reports"]["junit_dir"]
        else evidence_dir / "junit"
    )

    cfg = Config(
        path=cfg_path,
        repo_root=repo_root,
        meta=dict(values["meta"], _gates_dir=gates_dir),
        paths={k: _resolve(v) for k, v in values["paths"].items()},
        cards={k: _resolve(v) for k, v in values["cards"].items()},
        resource=values["resource"],
        workers=values["workers"],
        exit_codes=values["exit_codes"],
        events=values["events"],
        reports=values["reports"],
        seal=values["seal"],
        gates=inline_gates,
    )

    # -- 跨字段：default_model 必须逐字命中 model_allowlist（设计 §2.1 #26）--
    allow = cfg.workers["model_allowlist"]
    default_model = cfg.workers["default_model"]
    if not allow:
        raise ConfigError(f"配置键 workers.model_allowlist 不许为空（在 {cfg_path}）")
    if default_model not in allow:
        raise ConfigError(
            f"配置键 workers.default_model={default_model!r} 必须逐字命中 model_allowlist={allow}"
            f"（在 {cfg_path}）"
        )

    # -- 跨字段：exit_codes.table_version 必须与内置表版本一致（可选收紧）----
    # 设计允许外部表（table_path）；给了外部表就不强绑内置版本，只要求给了版本号。
    return cfg
