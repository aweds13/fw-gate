# minimal-notes（示例仓）

一个**与任何具体产品无关**的最小记事仓 —— 用来证明这套管线是**泛用**的：
它有自己的 `pipeline.toml`、自己的门与钉子，零处项目专有引用，却能过自己的判据。

## 跑一下

```
pipe gate   --config framework/examples/minimal-notes/pipeline.toml
pipe doctor --config framework/examples/minimal-notes/pipeline.toml
pipe gate   --config framework/examples/minimal-notes/pipeline.toml --json
```

（在 `framework/` 里也可以直接 `pipe --config examples/minimal-notes/pipeline.toml gate`。）

## 内容

- `src/notes/__init__.py` —— 领域代码（纯函数：`add` / `search`）。
- `tests/test_notes.py` —— 正常路径。
- `tests/test_nail_sample.py` —— **反例钉子**：空关键词必须被拒绝（通过 = 判据有牙）。
- `gates.d/tests.toml` —— 一道门，跑测试并出 JUnit XML。
