# 自编译阶段目录（N6）

```text
C0(S) → stage1/ → C1
C1(S) → stage2/ → C2
C2(S) → stage3/ → C3
compare(stage2/manifest, stage3/manifest)
```

## 目录约定

```text
compiler/stages/
  driver/           # 手写垂直驱动（入库）
  fixtures/         # 冒烟 fixture（入库）
  stage1/
    bin/            # 可执行文件（可再生成，勿混进源码树）
    compiler/paw/   # 宿主 Mid 种子发射（emit-seed）
    c1_emit/        # C1 薄 emit 嵌套源码：frontend|hir|mid|passes|sema
    c2_thin/        # C1→C2 薄 reseed 产物（同嵌套布局）
    c3_thin/        # C2→C3 定点产物（同嵌套布局）
  stage2/ stage3/   # 完整阶段快照（manifest + seed）
```

- **源码与二进制分离**：`.exe` 一律进 `stage1/bin/`；`c1_emit` / `c*_thin` 只保留嵌套 `.h/.cpp`。
- **禁止平铺遗留**：勿在 emit 根目录再写 `lexer.cpp` 等扁平副本（会遮蔽 `#include "frontend/..."`）。
- **调试目录**：`*_dbg` 为临时，用完删除，勿入库。

## 命令

```bat
python tools/paw_bootstrap_stages.py init
python tools/paw_bootstrap_stages.py snapshot-seed
python tools/paw_bootstrap_stages.py manifest stage1
python tools/paw_bootstrap_stages.py compare stage2 stage3

tools\paw_stage1_c1_link.bat
tools\paw_c2_c3_thin_reseed.bat
```

生产热路径：`Syntax → HIR → MidIR`（见 `compiler/py/sema`、`compiler/py/mid`）。C1 产物写入 `stage1/` 后填入真实 manifest。
