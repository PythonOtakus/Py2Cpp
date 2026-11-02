# Paw 语法实现清单

更新 2026-11-02。  
汇总自 [syntax-migration.md](../syntax-migration.md)、[baseline.md](./baseline.md)、[debridge-roadmap.md](./debridge-roadmap.md)、[dual-impl.md](./dual-impl.md)、[compiler/bootstrap_profile.md](../../compiler/bootstrap_profile.md)。  
**规范细节仍以 `syntax-migration.md` 为准**；本文只回答「现在哪些已通 / 哪些未通」，并按实现轨分层。

## 0. 读表约定（三轨）

| 轨 | 含义 | 主要代码 |
|---|---|---|
| **C0 生产** | 宿主 `compiler/py`：Lexer→Parser→HIR→MidIR→emit；stdlib/tests/`*.paw` 主路径 | `compiler/py/**`、`src/**` |
| **C1 薄 seed** | `compiler/paw` 竖切 parser/emit：能自解析并发射 seed 语料 | `compiler/paw/frontend/parser.paw`、`mid/emit_cpp.paw`；门闩 `paw_stage1_c1_link.bat` |
| **规范拟定** | 表面已定案或仍为候选，不等于已全部接通语义/发射 | `docs/syntax-migration.md` |

状态码：

| 码 | 含义 |
|---|---|
| **已实现** | 生产路径可解析 + Mid/emit（或明确等价路径）可用；有门闩/语料覆盖 |
| **部分** | 表面可认或子集可用；语义/布局/穷尽性未齐，或仅 C0 全量、薄 seed 未覆盖 |
| **薄子集** | C0 全量已有，但 C1 薄 parser 仅竖切（其余进 Opaque / stub） |
| **未实现** | 规范有文或仍为候选，语义/前端未接通 |
| **已禁止** | `.paw` 禁旧写法；须用新表面 |

---

## 1. 已实现（C0 生产 · 主清单）

### 1.1 声明与对象模型

| 语法 | 状态 | 依据 |
|---|---|---|
| `class` / 嵌套类 / 继承（含 mixin 类头顺序） | 已实现 | baseline §2；syntax-migration 声明表 |
| `record` / `frozen` / `ordered record` / `ref class` / `final class` | 已实现 | A/B 批次；bootstrap_profile |
| `enum` / `enum …(flag=True)` / `type enum`（硬关键字） | 已实现 | debridge 硬关键字轮；禁 `@enum` |
| `union` / `variant` / `type union`（硬关键字） | 已实现 | 同上；禁 `@union` |
| `protocol` / `mixin` | 已实现（声明面） | syntax-migration；passes 迁 Mid「进行中」见 baseline §7 |
| `native class` / `native def`（无 `@native`） | 已实现 | debridge 表面硬切 |
| `delegate Name[T](...) -> R`（无体） | 已实现 | debridge 表面硬切 |
| `const x: T = v`（类/模块常量子集） | 部分→已实现（字面量/标量子集） | syntax-migration：非常量表达式求值未齐 |
| `import` / `from .… import` | 已实现 | bootstrap_profile |

### 1.2 函数与方法修饰

| 语法 | 状态 | 依据 |
|---|---|---|
| `def` / `async def` / `static def` / `static async def` | 已实现 | C0 表面落地；禁 `@staticmethod`、`async static` |
| `override` / `virtual` / `abstract` / `final` 作方法前缀 | 已实现 | 禁对应旧装饰器 |
| `property def` / `static property def` / `property Name:` 块 | 已实现 | C0 表面；debridge 节点分叉 |
| `@copyable` / `@uncopyable` / `@immutable` / `@serializable` / `@native_name` / `@boxing` / `@annotation` / `@descriptor` 等「保持」项 | 已实现 | syntax-migration；baseline 允许保留装饰器 |
| 同名 `def` overload（无 `@overload`） | 已实现 | `.paw` 禁 `@overload` |

### 1.3 类型表面（P0 完成）

| 语法 | 状态 | 节点/依据 |
|---|---|---|
| `list[T]` / `dict[K,V]` / `set[T]` 等泛型应用 | 已实现 | `GenericApplyTypeSyntax` |
| `ref T` / `lazy T` / `lazy ref T` / `T?` | 已实现 | C0 表面；禁类型位 `@ref`/`@lazy` |
| `T @Meta` | 已实现 | `AttributedTypeSyntax` |
| 裸箭头 `(A,B)->R` / `T->R` / `()->None` | 已实现 | 禁 `Function[[…]]` |
| `Callable[(A,B)->R]` / `Callable[T->R]` | 已实现 | 禁 `Callable[[…]]` |
| `A \| B` 类型并 | 已实现 | `UnionTypeSyntax` |
| `T[:]` / `T[:,:]` / `T[:N]` / `list[T,N]` | 已实现 | debridge 水位 |
| `type Name = T` 别名 | 已实现 | 与 `type enum`/`type match` 分派 |

### 1.4 语句 / 表达式（P2 完成 · Mid 可结构化）

| 语法 | 状态 | 依据 |
|---|---|---|
| `return` / `pass` / `raise` / `assert` | 已实现 | P2；Try/With/Assert 水位 |
| `if` / `elif` / `else` | 已实现 | P2 |
| `while` / `for`（含 `range`、容器） | 已实现 | P2；**不支持 for-else**（syntax-migration） |
| `match` / `case`（运行时值匹配 · 已接子集） | 已实现 | 节点分叉；MSVC 竖切 `match→if/else` |
| 赋值 / 增强赋值 / 调用 / 二元运算 | 已实现 | P2 |
| 下标 / 切片 / 多维下标 `,` | 已实现 | `SubscriptExpr` / `SliceExpr` |
| list/set/dict 字面量 | 已实现 | P2 |
| 三元 `x if c else y` | 已实现 | `IfExp` |
| `a @ b` / `a @= b` | 已实现 | `MatMultExpr` |
| `lambda` / `*x`（已接子集） | 已实现 | `LambdaExpr` / `StarredExpr` |
| `*args` / `**kwargs`（emit 水位） | 部分 | debridge 水位「已抬升」；缓存键规范化等仍「另行实现」 |
| `try` / `except` / `else` / `finally` | 已实现 | `TryStmt` |
| `with E as t` | 已实现 | `WithStmt` |
| `global` / `nonlocal` | 已实现（节点） | 节点分叉；逃逸闭包整体仍禁 |
| `new(...)` / `new(f=v)` IIFE | 已实现 | debridge 水位 |
| f-string（词法+发射子集） | 部分 | debridge 水位「词法」；完整嵌套仍以语料为准 |
| 隐式字符串拼接 | 已实现 | debridge 水位 |
| `return a, b` | 已实现 | debridge 水位 |

### 1.5 生产覆盖水位（非语法项，但表示「能编译」）

| 项 | 状态 | 依据 |
|---|---|---|
| stdlib `mid_emit_ok` | **153/153** | debridge / baseline |
| `tests/` build-all | **155/155** | baseline §7 |
| seed Mid MSVC 竖切 | **6/6～8/8** | debridge |
| 删 `materialize_ast`；`ast_from_mid` | 已完成 | P5 |

---

## 2. 薄 C1 seed 轨（相对 C0 的子集）

`compiler/paw/frontend/parser.paw` 自述：**声明子集**（enum/class/record/import/def/const + Opaque）；完整宿主在 `compiler/py/frontend/parser.py`。

| 类别 | 薄 seed **已跑通** | 薄 seed **未覆盖 / stub** |
|---|---|---|
| 声明 | `enum`、`class`/`record`（含字段+方法）、`const`、`import`/`from`、`def`（含前缀）、装饰器类入口 | 完整 `union`/`protocol`/`mixin`/`variant`/`type enum` 语义展开、完整 property 块语法树 |
| 函数体发射 | assign / if-else / while / for-range / return / raise / match 子集 / call / 切片 / `new` kwargs / plus 等（D4–D7；真实 soft-skip≈0） | 与宿主 Mid 字节不等价；复杂 HIR 全量语句仍靠 C0 |
| 模块 | source/tokens/diagnostic/lexer/parser/check/emit_cpp/bind/nodes… | `param_parse` / `stmt_parse` / `type_parse` / `surface_rewrite` / `legacy_to_paw` / `ast_from_mid` / `structure` / `apply_mid_decls` 现为 **stub**（仅 docstring） |
| 自举 | D0–D7；**c2_thin ≡ c3_thin** | 生产仍宿主 Mid；模板仍 CPython |

门闩：`scripts/paw_stage1_c1_link.bat`、`compare-host-thin`、`paw_c2_c3_thin_reseed.bat`。

---

## 3. 未实现 / 部分 / 候选（规范有文）

### 3.1 明确未实现或首版拒绝

| 项 | 说明 | 出处 |
|---|---|---|
| `lazy class` 单例 + 生命周期检查 | 「尚未实现」 | syntax-migration §lazy-class |
| `@classmethod` | 不支持 | syntax-migration 方法表 |
| `for`…`else` | 不支持 | syntax-migration 控制流 |
| 裸 `raise`（无异常对象） | 当前不支持 | syntax-migration |
| 完整逃逸闭包 / 返回局部 lambda | bootstrap 禁止；L2 | baseline §4；bootstrap_profile |
| 机器码后端 / PEG 双前端 | L2 暂不 | baseline §4 |
| 模板执行器「任意 CPython」 | 未完成 | baseline §7；parser-self-hosting |
| `lazy` 缓存：`**kwargs` 键规范化、ref/lazy 形参缓存、virtual 方法缓存、async/generator 缓存等 | 首版拒绝或另行实现 | syntax-migration lazy 节 |
| const 任意常量折叠（如 `1+2` 作 const 初值） | 未齐 | syntax-migration 字段节 |
| final 字段「完整控制流确定赋值」 | 另行实现 | 同上 |
| 类型捕获 `type U` 的多项扩展（NTTP、可空解构等） | 首版限制 | syntax-migration type match |
| `inline if` / `__macro__` 进 inline | 首版不接受 `__macro__` | syntax-migration |
| 多行块 lambda 候选 A–D | **候选，未采纳为正式语法** | syntax-migration `#multiline-lambda-options` |
| `call`/`from` 多行回调；`as` 结果绑定 | 用户方案已记；**候选扩展** | syntax-migration `#call-from` |
| `type match` 语句 / 类型匹配表达式（编译期） | 推荐方案；静态求值「待实现」 | syntax-migration；与运行时 `match` 不同 |
| 完整 S：`src/translator` / analysis / codegen Paw 化 | 未通 | baseline §7；dual-impl |

### 3.2 已禁止的旧表面（`.paw` 不得再写）

| 旧写法 | 新写法 |
|---|---|
| `@enum` / `@union` / `@dataclass` / `@refcount` | `enum` / `union` / `record` / `ref class` |
| `@override` / `@virtual` / `@abstract` / `@final`（方法） | `override def` 等前缀 |
| `@staticmethod` / `@property` 族 / `@delegate` / `@native` | `static def` / `property …` / `delegate` / `native …` |
| `Function[[…], R]` / `Callable[[…], R]` | 裸箭头 / `Callable[arrow]` |
| 类型位 `@ref` / `@lazy`；`async static` | `ref T` / `lazy T`；`static async def` |
| `@overload` | 同名 `def` |

---

## 4. 节点分叉已落地（Syntax · 对照用）

完整表见 [debridge-roadmap.md §节点分叉](./debridge-roadmap.md)。摘要：泛型/`T[:]`、下标/切片、`T @Meta`、`@`/`@=`、`FieldDecl`、`IfExp`、`match`、箭头/`Callable`、`delegate`/`native`、`property`、`A|B`、`lambda`/`*x`、`try`/`with`/`assert`、`global`/`nonlocal`。

---

## 5. 维护

| 变更类型 | 应改 |
|---|---|
| 新表面硬切 / 禁旧 | `syntax-migration.md` + 本清单 §1/§3.2 |
| P 阶段完成 | `debridge-roadmap.md` + 本清单 §1.4/§1.5 |
| 薄 seed 能力 | `dual-impl.md` / `baseline.md` §7 + 本清单 §2 |
| bootstrap 允许集 | `compiler/bootstrap_profile.md` |

刷新语料计数：`python scripts/paw_inventory_corpus.py`。  
stdlib mid-emit：`python scripts/paw_mid_emit_coverage.py`。
