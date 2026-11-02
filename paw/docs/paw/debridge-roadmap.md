# 拆除 `materialize_ast` / 去 CPython AST 路线图

目标：生产路径 **MidIR → C++ emit**，删除 `compiler/py/mid/materialize_ast.py`；passes 不再消费 `ast.*`。

更新 2026-11-02。  
语法实现分层清单：[syntax-inventory.md](./syntax-inventory.md)。

## 阶段与退出条件

| 阶段 | 内容 | 退出条件 | 状态 |
|---|---|---|---|
| **P0 类型表面** | `list[T]` / `ref T` / `T?` / `T @Meta` / 裸箭头 / `Callable[arrow]` → `TypeSyntax` | `test_paw_type_parse.py` | **完成** |
| **P1 签名结构化** | `ParamDecl` + `parse_params` → FunctionDecl/HIR/Mid | `test_paw_debridge_p1_p3.py` | **完成** |
| **P2 语句/表达式** | Return/If/Elif/While/For/Match/Assign/AugAssign/Call/BinOp/下标/切片/list/set/dict/三元/`a @ b` | 同上；seed 函数体无 Opaque | **完成** |
| **P3 MidIR emit** | `compiler/py/mid/emit_cpp.py` + `tools/paw_mid_emit_seed.py` | seed 6/6 `can_emit_mid` | **完成** |
| **P4 passes 迁 MidIR** | translator 记录 `mid_emit_ok`；`_emit_mid_capable_modules` 旁路写出 | seed 旁路产物在 `out/**/mid_emit/` | **完成（旁路）** |
| **P5 删桥** | Mid emit 对齐 + 删物化 | seed 6/6 mid；stdlib **153/153**；MSVC 竖切 **6/6**；`PY2CPP_MID_PRIMARY=1` 跳过 AST emit | **完成**：已删 `materialize_ast.py`；生产树一律 `ast_from_mid`；`py2cpp`+`test`+`seed` mid_ok+直构全绿 |
| **P6 passes 迁 Mid** | 少读 `ast.*`；空树可回填；C0 Mid 定点 | discover MidImport；空树回填；`fixedpoint` stage1==stage2==stage3 | **完成（C0 定点）**；真·C1 驱动/全量 S 另列 |

## 表面语法（2026-11-01 已硬切）

| 表面 | 含义 | 禁旧 |
|---|---|---|
| `(A, B) -> R` / `T -> R` / `() -> None` | C 函数指针（≡ 旧 `Function[[…], R]`） | `Function[[…], R]` |
| `Callable[(A, B) -> R]` / `Callable[T -> R]` | PyCallable 槽 | `Callable[[…], R]` |
| `delegate Name[T](...) -> R` | 多播委托声明（无 def/无体；名须 `Delegate` 后缀） | `@delegate` + `def` |
| `native def f(...) -> T` | FFI/叶子声明（无代码块）；`native class` 保留体 | `@native` 装饰器；native 实现体 |

物化桥（C0）仍把箭头写成 `Function`/`Callable` Subscript 供旧 `type_parse_ast`；源码与 `.paw` 禁旧拼法（见 `src/frontend/api.py`）。

## 使用

```bat
REM 单元
python -m pytest host/tests/test_paw_type_parse.py host/tests/test_paw_debridge_p1_p3.py -q

REM seed MidIR 直 emit
python tools/paw_mid_emit_seed.py

REM seed Mid emit MSVC 竖切（验收 6/6）
tools\paw_mid_emit_msvc_seed.bat

REM 自举：C0 Mid-emit 定点闭环（stage1==stage2==stage3）
python tools\paw_bootstrap_stages.py fixedpoint
REM stage1 MSVC 竖切（验收 6/6）
tools\paw_stage1_msvc_seed.bat
REM C1 seed 驱动：smoke + 自解析 compiler\paw\*.paw
tools\paw_stage1_c1_link.bat

REM Py×Paw 双实现对照（D0：配对表 + emitEnum）
python tools/paw_dual_compare.py
# 方案：docs/paw/dual-impl.md

REM 去桥验收（seed mid-emit + Translator PRIMARY）
python tools/paw_debridge_accept.py

REM stdlib mid-emit 覆盖率
python tools/paw_mid_emit_coverage.py

REM 空 tree（translator 回填 / register_module_from_mid）；=0 关闭空树仍走 ast_from_mid
REM 未设置或 =1：全部 mid_ok 空树；=0 关闭
set PY2CPP_NO_MATERIALIZE=1

REM mid_emit_ok：生产 Mid emit、跳过 AST emit
REM 未设置：仅 compiler/paw/**；=1 全 mid_ok（含 stdlib/test）；=0 关闭
set PY2CPP_MID_PRIMARY=1

REM 关闭 translator MidIR 旁路写出
set PY2CPP_MID_EMIT=0
```

## 水位（stdlib）

以 `python tools/paw_mid_emit_coverage.py` 为准。2026-11-01：`py2cpp` **153/153（100%）** `mid_emit_ok`。

本轮抬升：类型 `A|B` / `T[:,:]` / `T[:N]` / `list[T,N]`、值下标多维与 `,`、表达式 `@`/`@=`、`lambda`、`*args`/`**kwargs`、隐式字符串拼接、f-string 词法、嵌套 `variant` opaque、`return a,b`。

本轮（接 100% 门闩）：`TryStmt` / `WithStmt` / `AssertStmt`；`new(f=v)` → 带返回类型的 IIFE；enum 成员 `...` 不再发射非法 `= ...`。

本轮（MSVC 6/6）：默认实参；`//`→`__floordiv__`；`PySlice<PyInt,PyInt>`+Unset；`match`→if/else；`s[i]`↔`PyChar`；list 默构+append；`in […]` 展开；括号 import；类型名/`new` 关键字 IIFE；`min`/`max` 三目；PyList 下标 for。

本轮（P5 接线）：Mid emit 嵌套命名空间 `compiler::paw::*` + 相对 `#include "compiler/paw/….h"`；产物 `{out}/compiler/paw/{stem}.*`；`PY2CPP_MID_PRIMARY=1` 时 translator 跳过该模块 AST 头/inl/实现并写生产路径；`compile.py` 自动链 `MidIR emit` 旁路 `.cpp`。

本轮（硬关键字）：`enum`/`union` → `TokenKind.KW_*`（不可作标识符）；`surface_rewrite`/`parser` 认 `KW_*`；`builtins.paw` 去掉 `def enum`/`def union`/`enum.mro`；`Rect.united`；`.paw` 禁 `@enum`/`@union`；`core/{optional,result,iter_result}.paw` 不再 `import union`。

本轮（P5 默认 PRIMARY / Mid→ClassInfo）：未设 env 时 `compiler/paw/**` 自动 Mid 生产写出 **且** 默认跳过物化；空树经 `register_module_from_mid` 登记 `ClassInfo`；`parse_module` 缓存键含物化模式；翻译 seed 时 `project_root` 升到仓库根（模块路径 `compiler/paw/<stem>`），PRIMARY 写生产路径且不再被 AST 入口覆盖；`PermFlag.Read`/`Seal.MAX` → `Py…::…`；裸 stem PRIMARY 落 `entry_output_dir`；`for Class in …: Class()` 认局部调用。

seed（`compiler/paw/*.paw`）保持 **8/8** mid-emit（含 `mid_emit`/`check`）+ stage1 MSVC 竖切同 stems。

## Mid emit → MSVC（seed）

验收：`tools/paw_mid_emit_msvc_seed.bat`（需 vcvars）→ **6/6**。

| 模块 | MSVC | 备注 |
|---|---|---|
| `span_tokens` | **绿** | enum/`new`/相对 import |
| `diagnostic` | **绿** | 跨模块 `PySourceSpan`、`new` IIFE |
| `source_manager` | **绿** | `list[T]`、`self`→`this->`、`range`、`__getitem__`、`__init__` 构造 |
| `lexer` | **绿** | 默认参、`//`、切片、`match`、`PyChar`、list append |
| `parser` | **绿** | 括号 import、`match` 枚举、`SourceSpan(…)` IIFE、PyList for、`min` |
| `syntax_nodes` | **绿** | 与上同竖切 |

已落地发射：相对 `#include`+`using`、`bool`、异常 `Py*Error`、`new`/类型名 IIFE、`decltype` 空 list、方法 `this->`、floordiv/slice/match/PyChar。

## 剩余工作（真·删桥 / 自举）

1. **P5**：已删 `materialize_ast`；`ast_from_mid` + `structure.py`
2. **P6**：默认空树；非 stdlib PRIMARY；Mid expand；stdlib PRIMARY 布局；**C0 Mid-emit 定点** `fixedpoint`（stage1==stage2==stage3）；stage1 MSVC 6/6
3. **C1 seed 驱动**：parse→薄 mid_emit→**链跑** … + **D7 `c1_thin_reseed`→`c2_thin`** 已绿（`tools\paw_stage1_c1_link.bat`）
4. **nested c1_emit / D4+–D7**：**绿** — 薄 emit 无真实 soft-skip；**D7：薄栈重种子 seed 语料**
5. **C1→C2→C3（seed 薄定点）**：**绿** — `c2_thin`≡`c3_thin`；`tools\paw_c2_c3_thin_reseed.bat`；C2 span/parser 竖切
6. **全量自举仍缺**：生产路径仍宿主 Mid；完整 S Paw 化；模板执行器离 CPython — 见 [parser-self-hosting.md](../parser-self-hosting.md)
7. **双实现对照**：见 [dual-impl.md](./dual-impl.md)；D0–D7 已绿

## 节点分叉（已落地）

| 表面 | Syntax 节点 |
|---|---|
| `list[T]` | `GenericApplyTypeSyntax` |
| `T[:]` | `GenericApplyTypeSyntax`（标记实参 `:`） |
| `arr[i]` / `a[i:j]` | `SubscriptExpr` / `SliceExpr` |
| `T @Meta` | `AttributedTypeSyntax` |
| `a @ b` | `MatMultExpr` |
| `name: T = v`（类体） | `FieldDecl` |
| `x if c else y` | `IfExp` |
| `match` / `case` | `MatchStmt` / `MatchCase` |
| 裸箭头 / `Callable[arrow]` | `CallableTypeSyntax`（`is_py_callable`） |
| `delegate` / bodyless `native` | `FunctionDecl.is_delegate` / `.is_native` |
| `property def` / `static property def` | `FunctionDecl.is_property`（+ `is_static`） |
| `property Name:` 块 | 展开为 get/set `FunctionDecl` |
| `A \| B` 类型并 | `UnionTypeSyntax`（与表达式 `|` 分叉） |
| `T[:,:]` / `T[:N]` / `list[T, N]` | `GenericApplyTypeSyntax`（切片维 / NTTP） |
| `a @ b` / `a @= b` | `MatMultExpr` / AugAssign `@=` |
| `lambda …:` / `*x` | `LambdaExpr` / `StarredExpr` |
| `try` / `except` / `else` / `finally` | `TryStmt` / `ExceptHandler` |
| `with E as t` | `WithStmt` / `WithItem` |
| `assert` | `AssertStmt` |
| `global` / `nonlocal` | `GlobalStmt` / `NonlocalStmt` |
