# framework —— 可带走的管线

核心库 + 薄 CLI + 模板仓。项目专有值全部外置到 `pipeline.toml`。
「为什么这样设计」看 `PIPELINE.md`；「字段/命令到底是什么」看 `--help` 与 `pipeline.schema.json`。

## 跑一下（不用先装包）

在 `framework/` 目录里：

```
python cli/main.py --help
python cli/main.py gate   --config examples/minimal-notes/pipeline.toml
python cli/main.py doctor --config examples/minimal-notes/pipeline.toml
python cli/main.py gate   --config examples/minimal-notes/pipeline.toml --json
```

或跑框架自己的测试：

```
python -m pytest tests -q
```

## 装成命令（可选）

```
pip install -e .
pipe --help
```

## 铺一个新项目

```
pipe init --dir /path/to/new-project
cd /path/to/new-project && pipe gate
```

## 布局

```
src/framework/   核心库（config / gates / exit_codes + 五个薄壳：ledger invariants claim land trace）
cli/main.py      薄 CLI
templates/       `pipe init` 铺出的模板（minimal）
examples/        一个非本项目的最小示例仓
tests/           框架自己的测试（含反例钉子）
pipeline.schema.json   配置的 JSON Schema 2020-12
```
