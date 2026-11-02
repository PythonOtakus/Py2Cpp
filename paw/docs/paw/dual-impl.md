# 双实现对照（Python 参考轨 × Paw 自举轨）

目标：`compiler/py/**` 与 `compiler/paw/**` **路径一一对应**（`.py` ↔ `.paw`），用 dump/diff 证明语义等价。

更新 2026-11-02。

## 目录规则

```text
compiler/py/<rel>.py   ↔  compiler/paw/<rel>.paw
compiler/py/**/__init__.py  ↔  compiler/paw/**/__init__.paw
```

门闩：`python scripts/paw_dual_compare.py`（需 `c1_emit_*_run.exe` 与 `c1_seed_driver.exe`，见 `paw_stage1_c1_link.bat`）。

## 对照层级

| 层 | 内容 |
|---|---|
| tree_parity | 文件 1:1 |
| tokenize / parse dump | D1 |
| MidIR dump | D2：Py `bind+lower_to_mid` vs Paw `bindModule`→`lowerToMid`→`dumpMidModule`（enum 竖切） |
| emitEnum | D0 |
| **emit_cpp 规范化** | D4+：Py Mid `emit_cpp` vs Paw 宿主 Mid `emit_cpp.paw::emitEnum`（`c1_seed_driver --emit-enum-dump`） |

## 命令

```bat
python scripts/paw_dual_compare.py
scripts\paw_stage1_c1_link.bat
```

## 节奏

| 阶段 | 状态 |
|---|---|
| D0 emitEnum | 绿 |
| D1 tokenize/parse dump | 绿 |
| D2 MidIR dump（enum Color 竖切） | 绿 |
| D3 目录对称 / 1:1 | 绿 |
| D4 emit_cpp 能力对齐（enum Color） | 绿 |
| D4+ 取消 `emit_enum_min` | **绿**：门闩走宿主 Mid `emit_cpp.emitEnum`；薄 emit 全量 `emit_cpp.paw` 已通（深度上限+字符串感知） |
| D4++ 薄 `emit_cpp.emitEnum` 链跑 | **绿**：`c1_emit_thin_emitcpp_run`（plus/调用括号字符串感知、PyStr 索引 wrap） |
| D4+++ 薄 `emitModule` enum-only | **绿**：同 runner 链跑 `emitModuleHeader`/`Cpp`；`_emitStmtSeq` 截断已修（去易炸注释 + soft-skip 不中止） |
| D4++++ 薄 `emitModule` 含函数体 | **绿**：`fixture_foo`（foo/add1/pick）由薄 emit 写出并 `c1_emit_thin_foo_run` 链跑；修 hash 注释/`"("`` 吞体、`_cppParams` 早 continue |
| D5 parse→薄 emit→链跑 | **绿**：薄 parser 解析 `fixtures/fixture_foo.paw` → 薄 `emitModule` → `c1_emit_thin_foo_run`；`_extractFunction` 改 while/字段赋值可薄 emit；读入去 CRLF |
| D6 声明面 class/record/const/import/def | **绿**：`_appendClass` 调用可薄 emit；`c1_emit_parser` D6 + `fixture_syntax.paw` 薄 parse→emit（enum/class/record/def/import）；kwargs/类型 ctor IIFE |
| D7 薄 reseed C1→C2→C3 | **绿**：`c1_thin_reseed` 用薄 parser+emit 重发射 seed → `c2_thin`；`paw_c2_c3_thin_reseed.bat` → `c3_thin`；**c2≡c3**（同字节）；C2 span/parser 竖切绿 |
| compare-host-thin | **绿**：`python scripts/paw_bootstrap_stages.py compare-host-thin`（宿主 Mid vs `c1_emit` soft-skip=0；有则查 c2≡c3） |
| paw/sema 真 Mid（enum Color） | 绿（`bindModule`→`lowerToMid`→`dumpMidModule`） |
| nested c1_emit | **绿**：`c1_emit/<pkg>/…`（已解 `nodes.h` 撞名） |
| hir/mid/nodes 字段对齐 | **绿**：Class/Function/Import/… 已在 paw；`StmtSyntax`/`ParamDecl` 仍 py |
| 真 C1 全量 S / 模板离 CPython | 待（seed 薄定点已通；宿主 Mid/模板仍服务生产全量） |
