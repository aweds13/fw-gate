# 最小模板仓（minimal）

这是 `pipe init` 铺出来的骨架：一个能直接跑 `pipe gate` 的最小项目。

## 目录

```
pipeline.toml      配置（唯一外置项目相关值的地方）
gates.d/tests.toml 一道门（跑本仓测试，出 JUnit XML）
ledger.toml        追溯矩阵（空骨架）
invariants.toml    不变式登记册（空骨架）
backlog.toml       排班表（空骨架）
card-template.md   卡规格模板（§0–§7）
src/notes/         你的代码
tests/             你的测试（含反例钉子）
.pipe/             运行产物（证据 / 日志 / 状态；被 .gitignore 忽略）
```

## 上手

```
pipe gate            # 跑门（并发 / 每门硬超时 / 三值判决）
pipe gate --json     # 机器可读的同一份结果
pipe doctor          # 金丝雀自检：对每道门真跑它的反例钉子
pipe card new --id T-1 --title 我的第一张卡 --domain src/notes/evidence.py
```

## 三件事要记住

1. **判据随件走**：每道门必须有一个**反例钉子**（`nail`）—— 一条喂进故意坏掉的样本、
   断言门会把它逮住的用例。钉子**通过** ⇒ 门有牙；钉子**失败** ⇒ 门失效（判据退化成注释）。
2. **三值判决**：门的结果只有 `pass` / `fail` / `inconclusive`。
   `inconclusive`（判不了，例如一条样例都没收集到）**绝不当成绿**，也**不等于** `not-run`（没跑）。
3. **项目相关值只写 `pipeline.toml`**：路径 / 端口 / 模型白名单都在那里，代码里不写死。
