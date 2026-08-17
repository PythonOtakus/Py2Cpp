# Py2Cpp 参考附录

本文件是 [SKILL.md](./SKILL.md) 的扩展查阅表；权威长文仍以仓库内文档为准：

- [docs/参考手册.md](../../../docs/参考手册.md)
- [docs/编码规范.md](../../../docs/编码规范.md)

---

## 1. 仓库布局

```text
Py2Cpp/
├── main.py                      # CLI（from src import Translator）
├── src/                         # 译器
│   ├── translator.py            # AST → C++ 主访问器
│   ├── compile.py               # -c 编译；test/ 默认不链 py2cpp.cpp
│   ├── constant/                # 静态表：模块/类/方法名、布局、umbrella、FFI、inject…
│   │   ├── stdlib_layout.py     # 逻辑模块路径 → #include / ::
│   │   ├── ffi_layout.py        # ffi/**/*.pyi → generated/runtime/ffi/；using Pyi_X = ::X
│   │   └── mixin.py             # @mixin 方法名契约
│   ├── tools/c_ffi_pyi.py       # libclang → ffi/**/*.pyi（CLI：ffi.bat / scripts/gen_c_ffi.py）
│   ├── analysis/
│   │   ├── runtime_symbols.py   # 包根 AST 推导符号 + PyRange 限定构造
│   │   └── stubs/               # AST loader（*_stubs.py）
│   ├── passes/                  # 预处理脱糖
│   ├── codegen/                 # expand_py2cpp_template / umbrella / protocol_traits / mirror
│   ├── emit/                    # AST 驱动生成（含 ffi_glue_emit）
│   └── tests/                   # 译器单元测试
├── py2cpp/                      # 标准库 Python 规格（按域分目录）
│   ├── __init__.py              # 包根 API、域再导出
│   ├── core/ util/ text/ io/ system/ concur/ test/ sql/ …
│   └── …
├── ffi/                         # 第三方 C FFI 声明面（.pyi；生成器产出，勿手改 AUTO-GENERATED）
├── templates/                   # C++ 注入 / 万能头模板（+*.h / +*.inl）
├── scripts/                     # MSVC / 翻译 / FFI 构建脚本
├── build_all.bat / build.bat / run.bat / demo.bat / ffi.bat
├── examples/
├── test/                        # 集成测试（misc/ lang/ sql/ ui/ … / fail/）
├── generated/                   # 翻译输出（勿手改）
│   ├── runtime/py2cpp/          # 标准库 .h / .inl / minimal.h / protocol_traits.h
│   ├── runtime/ffi/             # FFI 按需生成（不进 minimal.h bulk）
│   └── test/                    # 用户测试 .h / .cpp / .exe
└── docs/                        # 参考手册、编码规范、c-ffi-pyi.md …
```

**命名三层**（易混）：

| 层 | 含义 |
|----|------|
| 标准库 Python 包 | 仓库根 `py2cpp/`；`import py2cpp` |
| FFI 声明面 | 仓库根 `ffi/`；`from ffi.sqlite.sqlite3 import …` → C++ `ffi::…`（**不**挂 `py2cpp::`） |
| 译器 Python 包 | `src/`；`from src import Translator` |
| C++ 输出 | `generated/runtime/py2cpp/`（`namespace py2cpp::<域>::…`）与 `generated/runtime/ffi/` |

---

## 2. 翻译流水线（固定顺序）

`Translator.translate_file`（`src/translator.py`）：

| 阶段 | 入口 | 产出 |
|------|------|------|
| 1. 解析 | `ast.parse` | `ClassInfo`、模块函数列表 |
| 2. 预处理 passes | 见下表 | 改写 AST / 附加元数据 |
| 3. 分析 | `SemanticAnalyzer.analyze` | `method_sigs`、`ModuleAnalysis.includes` |
| 3b. 移动检查 | `check_moved_use`（`moved_use_check.py`） | 容器移动后再用 → 翻译期 `ValueError`（跳过 stdlib） |
| 4. 生成 | `_emit_*` / `visit_*` | `.h`、`.cpp`、`.inl`；bootstrap 时写 `py2cpp/minimal.h` |

### 2.1 Passes（`src/passes/`，顺序不可乱）

**权威顺序以** `Translator.translate_file`（`src/translator.py`）**为准**。下表与之对齐（摘要；细节见 [参考手册 §4](../../../docs/参考手册.md#4-翻译流水线)）。

| 阶段 | 函数（摘） | 作用摘要 |
|------|------------|----------|
| 前检 | `check_s32_*` / `check_s44_*` | dataclass 必填字段、注解标记 |
| 展开 | `expand_dataclass` → `expand_class_id` → `expand_enum_mro` / `expand_union_mro` → **`expand_enum`** → **`expand_union`** → `expand_serializable` | 数据类 / 枚举 / 联合 / 序列化 |
| | `check_native_function_bodies` | `@native` 体须 `...` |
| | `expand_default_iter` → `expand_descriptors` → `expand_mixins` → `expand_proxy` → `expand_class_type_base` | 迭代默认、描述符、mixin、proxy |
| | `expand_field_properties` / `expand_property_value_references` | 字段 `@property` |
| | `expand_default_bool` → `expand_default_numeric_convert` → `expand_default_ne` | 默认协议 |
| | `expand_test_discovery` → `expand_kwargs_options` → `expand_static_reflect` | 测试发现 / kwargs / 静态反射 |
| 生成器前 | **`check_yield_from_for_style`（S38）** → **`check_yield_from_in_async_def`** | 须在 `expand_generators` **之前** |
| | **`expand_generators`** | `yield` → `*_generator`（**须在** `expand_decorators` **之前**） |
| | `expand_decorators` → `check_noexcept_functions` → `expand_copyable` → **`expand_move_state`** | 装饰器 / copyable / moved |
| | `expand_protocol` → `expand_member_access` → **`expand_descriptor_signatures`** → `expand_lazy_params` → `expand_final_ctor_inits` | 协议 / 访问 / 描述符签名 |
| 分析 | `SemanticAnalyzer.analyze` | 类型、签名、头依赖 |
| 后检 | `check_proxy_*` / `resolve_union_*` / `check_new_*` / `check_*_rules` / `check_*_style` / **`check_parallel_loops`** / **`check_moved_use`** | 静态约束（含 `prange`） |
| 生成 | `_emit_all` 等 | 写 `.h` / `.inl` / `minimal.h` |

协程相关：`coroutine_desugar.py`、`generator_emit.py`（由 `visit_Async*` / 生成器发射调用）。闭包捕获见 [closure.md](../../../docs/closure.md)（规划中，非上表已挂 pass）。

**生成顺序**：模块级描述符签名校验 helper（``is_descriptor_signature_helper``）在 ``_module_functions_emit_order`` 中排在普通模块函数之前，避免 MSVC「找不到标识符」。

新增 pass：在 `passes/` 实现 → 在 `translator.py` **按依赖**插入 → 同步本表与 [参考手册 §4](../../../docs/参考手册.md#4-翻译流水线) → 加回归测试。

**``select`` 路径**（**非**上表 AST pass）：``src/passes/selector_parse.py`` 仅作路径 DSL 解析；在 ``call_emit`` / ``visit_AnnAssign`` 触发。类型 walk + ``$`` 校验见 ``analysis/selector_types.py``；内联生成见 ``emit/selector_emit.py``。详规 [docs/selector.md](../../../docs/selector.md)；主文档 [参考手册 §7.9](../../../docs/参考手册.md#79-select译期路径选择)。

**``build`` DSL**（**非** AST pass）：``src/passes/build_parse.py``；``analysis/build_types.py``；``emit/build_emit.py``。详规 [docs/build.md](../../../docs/build.md)；主文档 [参考手册 §7.10](../../../docs/参考手册.md#710-build译期对象构造)。

### 2.2 分析器（`analysis/`）

| 模块 | 职责 |
|------|------|
| `analyzer.py` | 注解 → C++ 类型、`ModuleAnalysis`、头文件依赖、`finalize_module_headers` |
| `ir.py` | `ClassInfo`、`MethodSig`、`FuncTypeParams`、`INT_FIELDS`、`PROTOCOL_PARAM_ERASE` |
| `imports.py` | `from … import` → `using` / 绑定 |
| `import_resolver.py` | 模块发现、`__all__`、相对 import |
| `module_namespace.py` | 路径 → `namespace` 段、`inl` 是否套 namespace |
| `selector_types.py` | ``select("…")`` 路径 TypeGraph walk、``$`` 绑定作用域校验 |
| `build_types.py` | ``Type.build("…")`` DSL TypeGraph walk、``[:N]: $i`` 下标绑定校验 |

**缺少注解时的类型（勿与 `void*` 混谈）** — 详表 [参考手册 §5.3.1](../../../docs/参考手册.md#531-缺少注解时的-c-类型策略)：

| 场景 | C++ |
|------|-----|
| 普通无注解形参 | `T0`, `T1`… + `template`（`FuncTypeParams`） |
| `x: ComparableType` / `f[T: Bound](…)` | `T`/`T0` + `Bound_requires` |
| PEP 695 头 **不**绑定无注解 `left` | 须 `left: ItL` |
| 未注解字段 ∈ `INT_FIELDS` | `PyInt` |
| 其它未注解字段 | `void*` |
| `key=None` 等跳过 collect | `void*` |
| 模板 + `return expr`（可翻译） | `auto` + `decltype(…)` |
| 无 `return expr`（普通 / 模板） | 自动 **`void`**（`-> None` 可选） |
| 隐式 void dunder | `void`（勿 `-> None`） |

---

## 3. `codegen/` 与 `emit/` 分工

**判据**：

| 包 | 输入 | 产出 |
|----|------|------|
| `src/codegen/` | `templates/**`、静态表、`DelegateInfo` / `ExcTypeUnion` 等**构建期**元数据 | runtime 固定 `.h` / `.inl`、`protocol_traits.h`、`minimal.h`（umbrella） |
| `src/emit/` | AST、`ClassInfo`、模块分析 | 用户/标准库 `.h` / `.cpp` / `.inl` 正文；`layout_emit` 编排写盘 |

`layout_emit` 在 `emit/` 但会调用 `codegen.expand_template` / `umbrella_gen`；`protocol_traits_gen` 在 `codegen/` 但引用 `emit/compile_diagnostic_emit` 文案——属正常交叉。

### 3.1 `src/codegen/`（模板与 runtime 固定产物）

| 文件 | 职责 |
|------|------|
| `expand_py2cpp_template.py` | `PY2CPP_*` 七宏展开、`expand_template` / `expand_mirror_to_generated` |
| `template_scope.py` | 宏名与展开上下文 |
| `inject_template_emit.py` / `class_header_inject.py` | `+*.h` / `paste_after` 注入登记 |
| `stdlib_mirror_codegen.py` | mirror 包壳 + `STDLIB_CODEGEN_MODULES` 占位（`write_stdlib_codegen_*`） |
| `umbrella_gen.py` | `minimal.h` 聚合（原 `primitive_types_cpp.py` / 旧名「py2cpp.h」） |
| `protocol_traits_gen.py` | `@protocol` SFINAE 探测 + ctx → `~protocol_traits*.inl`（原 `protocol_emit.py`） |
| `delegate_gen.py` | `DelegateInfo` → ctx → `core/~delegate_class.inl`（原 `delegate_cpp.py`） |
| `exception_group_gen.py` | `ExcTypeUnion` → `core/~exception_group_*` |
| `brace_style.py` | Allman 大括号 |

已迁 `templates/**` 的模块（`operators`、`io`、`memory`、`time` 等）不再保留独立 `templates/**`；见 [codegen-templates.md](../../../docs/codegen-templates.md)。

### 3.2 `src/emit/`（AST 生成）

| 文件 | 职责 |
|------|------|
| `comprehensions_emit.py` | 列表/字典/集合推导与字面量（含 `*` 解包） |
| `fstring_emit.py` | f-string / `str.format` |
| `literal_*_lookup_emit.py` | 字面量容器/串内联查表 |
| `dunder_ops_emit.py` / `cmp_ops_emit.py` / `copy_move_emit.py` / `object_repr_emit.py` | 类运算符（含 ``__cmp__``）、拷贝移动、`__repr__` |
| `union_emit.py` / `enum_emit.py` | `@union` / `@enum` 类声明与实现 |
| `setitem_emit.py` | ``__setitem__`` 值参数重载 |
| `compile_diagnostic_emit.py` | ``static_assert`` / 编译期错误 UTF-8 文案 |
| `refcount_emit.py` | `@refcount` 类体编排（模板在 mirror `core/refcount`） |
| `class_decl_emit.py` / `class_emit.py` / `loops_emit.py` / `layout_emit.py` / `call_emit.py` / … | 类声明/方法体、循环、布局写盘、调用（含 ``assign`` / ``select`` 内联）、下标等 |
| `stdlib_inject_emit.py` | 标准库 `.inl` 粘贴时机 |
| `selector_emit.py` | ``receiver.select("…")`` → inline ``list[T]`` IIFE（无 C++ ``select`` 成员） |
| `build_emit.py` | ``Type.build("…")`` / ``list[T].build("…")`` → inline ``new`` + 循环 ``append`` |

### 3.3 译器自动生成 C++ 标识符

| API | 规则 |
|-----|------|
| `patterns.temp_name(prefix)` | 函数体临时局部：``__{prefix}{N}``；模块级单调计数 |
| `patterns.auto_template_type_param_name(leaf)` | 自动模板形参：``__T0``、``__Ts``…（用户 PEP 695 ``Ts`` 等**不变**） |
| `patterns.py2cpp_emit_symbol(*parts)` | 命名空间级辅助符号：``__py2cpp_vt_loop_*``（``__call__`` 展开包）、``__py2cpp_type_if_*``、``member_access`` 中 ``__py2cpp_get_*_no_match`` 等 |
| 用户 Python 局部/形参 | **不**加 ``__``；经 ``cpp_param`` / ``escape_cpp_param`` |
| 描述符返回改写 | 固定 ``__py2cpp_return`` |

---

## 4. 标准库模块（`constant` 发现）

``src/constant/`` 存放译器静态表（**不含** AST 扫描 loader、emit 算法、C++ 模板正文）。**AST loader** 在 ``src/analysis/stubs/``（``*_stubs.py`` + ``paths.py``；读 ``py2cpp/`` 源 + ``constant/`` 表，``@lru_cache``；**无** barrel re-export，消费方显式 ``from …stubs.<mod> import …``）。模块发现见 ``constant/stdlib_discovery.py``（遍历 ``py2cpp/**/*.py``，排除 ``reflect/``、域包空 ``__init__`` 等）→ ``STDLIB_REL_PATHS``；``constant/stdlib_modules.py`` 的 ``UMBRELLA_PREFIX_TIERS`` / ``UMBRELLA_PRIORITY_MODULES`` 定 bulk 域前缀顺序与少数拓扑例外。bootstrap 在 ``analyze`` 后由 ``stdlib_module_order.reorder_stdlib_modules_for_umbrella`` 按 ``ModuleAnalysis.includes`` 对每个 tier 拓扑排序，再写 ``py2cpp/minimal.h``。万能头顺序与 bulk 跳过见 ``constant/umbrella.py``；头文件破环动作与前向声明见 ``constant/header_fixups_data.py``（算法 ``analysis/header_fixups.py``）；``.inl`` 注入规格见 ``constant/inject_specs.py``（hook 构建 ``emit/stdlib_inject_emit.py``）；整模块 codegen 模块表 ``STDLIB_CODEGEN_MODULES`` → ``codegen/stdlib_mirror_codegen``（``write_stdlib_codegen_*``）。语言关键字 / dunder 方法名 / 标量 rename 见 ``constant/language.py``（``operator`` 映射见 ``constant/dunder_ops.py``；类型标记类名见 ``constant/type_markers.py``；命名 helper 留 ``analysis/patterns.py``）。``TRANSLATION_ONLY_FUNCS`` 由 ``stubs.builtin_stubs.load_translation_only_funcs()`` 从包根 ``__init__.py`` 推导；模块函数 C++ 名由 ``@globalCall`` AST 扫描（``stubs.class_stubs.lookup_module_function_cpp_name``）。翻译 bootstrap：``python main.py py2cpp/__init__.py -o generated --no-main``。

| 域 | Python 路径 | C++ 命名空间（典型） | 备注 |
|----|-------------|----------------------|------|
| core | `core/exceptions` | `py2cpp::core::exceptions` | 异常类型 |
| core | `core/refcount` | 全局 / 特殊 | `MODULES_WITHOUT_CPP_NAMESPACE` |
| core | `core/iter_result` | `py2cpp::core::iter_result` | `PyIterResult`、`resultDone` |
| core | `core/optional` | `py2cpp::core::optional` | `PyOptional`（`Optional[T]`） |
| core | `core/none` | `py2cpp::core::none` | `PyNone` |
| core | `core/result` | `py2cpp::core::result` | `PyResult<T,E>` |
| core | `core/object` | `py2cpp::core::object` | |
| core | `core/protocols` | `py2cpp::core::protocols` | traits 在 `core/protocol_traits.h`（全局 include） |
| core | `core/delegate` | 全局 / 特殊 | 用户 `@delegate` |
| util | `util/array` … `set` | `py2cpp::util::<mod>` | `set` → 段名 **`py_set`** |
| util | `util/memory` | `py2cpp::util::memory` | ``char[:]`` 原子 + ``*_ref``；``templates/util/+memory.inl`` |
| util | `util/tuple` | **全局** `PyTuple` | `templates/util/tuple.{h,inl}` |
| util | `util/span` | 全局 / 特殊 | |
| text | `text/str` | `py2cpp::text::str` | 最大模块；`Self._…` → `PyStr::_…` |
| text | `text/bytes` | `py2cpp::text::bytes` | |
| io | `io` | `py2cpp::io` | `open` → `py_open`；**须显式** `from py2cpp.io import …` |
| io | `io/file` | `py2cpp::io::file` | 原包根 `os` 能力 |
| io | `io/file/path` | `py2cpp::io::file::path` | `os.path` 函数 |
| io | `io/path` | `py2cpp::io::path` | `Path`（pathlib 子集） |
| system | `system/time` | `py2cpp::system::time` | `templates/system/-time.inl` |
| concur | `concur/task` | `py2cpp::concur::task` | |
| test | `test/unittest` | `py2cpp::test::unittest` | 集成测显式 ``from py2cpp.test.unittest import TestCaseMixin, …``（非包根 star） |
| serde | `serde/protocols` | `py2cpp::serde::protocols` | `EncoderType` / `DecoderType` |
| serde | `serde/json` | `py2cpp::serde::json` | 单文件 `JsonEncoder`/`JsonDecoder`；`dumps` / `loads` |
| ui | `ui/meta` … `ui/window` | `py2cpp::ui::<mod>` | Panel；``UIWindow`` Win32（``templates/ui/+window.inl``）；``__init__.py`` 勿 re-export 子模块 |

包根 `from py2cpp import *` 再导出 `core`/`util`/`text` 符号；**不**自动拉入 `io`。`deque` 空局部：`out: deque[T] = []`，勿 `Self()`（`return Self()` 仍用于 `-> Self` 早退）。

新增模块：写 `py2cpp/<域>/xxx.py`（自动发现）→ bootstrap → 若需打破字母序 bulk include，加入 `UMBRELLA_PRIORITY_MODULES`；破环见 `MODULE_HEADER_FIXUPS`。

---

## 5. 生成物约定（`generated/`）

| 产物 | 说明 |
|------|------|
| `runtime/py2cpp/minimal.h` | **万能头 / 测试 TU 主 include**（`UMBRELLA_HEADER`）；扁平 `#include` 子模块 + `operators.inl` |
| `runtime/py2cpp/<域>/*.h` | 类声明；模板类末尾或万能头外挂 `*.inl` |
| `runtime/py2cpp/util/range.h` | `PyRange`（`py2cpp::util::range::PyRange`；**不**在已删除的根 `py2cpp.h`） |
| `runtime/py2cpp/core/protocol_traits.h` | 全部 `@protocol` traits；**全局作用域** |
| `runtime/py2cpp.cpp` | 可选汇总 TU；**`test/` 链接时不要同时用** |
| `runtime/ffi/**` | FFI 按需写出（`#include "ffi/…"`）；**不**进 `minimal.h` bulk |
| `test/<module>.h/.cpp` | 用户测试翻译结果 |

### 5.1 头文件依赖（常见）

- `dict` / `str` 依赖 `protocol_traits.h`（即使不 include 完整 `protocols.h`）。
- `str.h` 与 `list.h` 曾循环 include；traits 已拆分，改 include 后须全量重编。
- `operators.inl` 须在 `minimal.h` 末尾（标量 `format`/`repr`）。
- `io.inl` 提供 `py_open`；`StringIO` 在 `io.py` + `io.inl`。

### 5.2 命名空间规则

| 场景 | C++ 结构 |
|------|----------|
| 用户 `test/foo.py` | `namespace test { … }` |
| 用户 `pkg/sub.py` | `namespace pkg { namespace sub { … } }` |
| 标准库 `py2cpp/util/list.py` | `namespace py2cpp { namespace util { namespace list { … } } }` |
| FFI `ffi/sqlite/sqlite3.pyi` | `namespace ffi { namespace sqlite { namespace sqlite3 { … } } }`（路径段 = 命名空间段） |
| 多数 `.inl` | 无 namespace 块；实现里写 `py2cpp::util::list::…` / `ffi::sqlite::sqlite3::…` |
| `tuple` / `delegate` / `refcount` | 见 `module_namespace.MODULES_WITHOUT_CPP_NAMESPACE` |

**勿**在 `namespace py2cpp { #include <utility> }` 内 include `protocol_traits.h`（会产生 `py2cpp::std::…`）。

### 5.3 C / CRT / 平台 FFI（`ffi/**/*.pyi`）

详规 [docs/c-ffi-pyi.md](../../../docs/c-ffi-pyi.md)；编码规范 §9.4。

| 项 | 约定 |
|----|------|
| 源 | 仓库根 `ffi/`（`ffi.bat` **自动生成**，禁止手写）；Zeus 旁路 `zeus/ffi/` |
| 布局 | Win32 → `ffi/windows/<stem>.pyi`；UCRT → `ffi/crt/<stem>.pyi`；第三方 → `ffi/<path>.pyi` |
| 范围 | **A+B**（第三方 + SDK + CRT）；**不含** C++ STL |
| 模板 | 可保留组合；**禁止**直导 A/B 头（译期 **T26**）；须 `#include "ffi/…"`；`#include <c_header>` 仅 glue |
| 禁止 | `from ffi… import *`；全量 Win32 进 `minimal.h`；手改 `AUTO-GENERATED` `.pyi`；批量删 UI 组合模板 |

回归：`python -m unittest src.tests.test_ffi_import`；`build.bat sql/test_sqlite`。

---

## 6. Python 名 → C++ 名（`ir.CPP_RENAME` 摘要）

注解与类名映射（完整表见 `src/analysis/ir.py`）：

| Python | C++ |
|--------|-----|
| int / float / bool | PyInt / PyFloat / PyBool |
| str / bytes / char | PyStr / PyBytes / PyChar |
| list / dict / deque / slice | PyList / PyDict / PyDeque / PySlice |
| tuple / range | PyTuple / PyRange |
| array / array2d / array3d | PyArray / PyArray2D / PyArray3D |
| IterResult / RefCount / Optional | PyIterResult / PyRefCount / PyOptional |
| zip / enumerate 步进值 | PyTuple / PyZipIterator / PyEnumerateIterator |
| open（io 模块） | **py_open**（函数名映射，非 CPP_RENAME） |

类名在 `.py` 里用 Python 风格（`class range`）；C++ 用 `CPP_RENAME` 或生成器硬编码。

---

## 7. 装饰器与翻译期标记

| 标记 | 处理位置 | 说明 |
|------|----------|------|
| `@dataclass` | `dataclass_expand` | 字段 + `new` 关键字构造 |
| `@enum` | `enum_expand` + `enum_emit` + `enum_match` | C++11 `enum class`；`...` / `flag=True`；`str`/`repr`；`match` 模式 |
| `@union` / `@variant` | `union_expand` + `union_emit` | Rust 式 ADT |
| `@copyable` | `copyable` | 值语义拷贝；测试用 `dst: T = src` |
| `@mixin` | `mixins` | 混入基类 |
| `@descriptor` | `descriptors` + `descriptor_signatures` | 字段/属性内联；函数形参/返回 ``T @Desc(...)`` → ``__set_<fn>_param_*`` / ``__set_<fn>_return``（模块 helper 先于调用方生成） |
| `@delegate` | `decorators` + 入口 `.h` | 多播委托 |
| `@decorator` / `@context` | `decorators` | 翻译期展开 |
| `@protocol` | `protocol` + `protocol_traits_gen` | SFINAE，非继承 |
| `@refcount` | 类标记 + `refcount` 生成 | `makeRefCount` |
| `@boxing` | 类标记 | `new` 堆节点（DictEntryUnsafe、DequeNodeUnsafe） |
| `@virtual` / `@override` | 方法装饰 | C++ virtual/override |
| `@overload` | 方法 | 同名重载集 |
| `@const` | 字段 | 类/静态常量 |
| `@optional` | 类型 | `PyOptional` |
| `@immutable` | 方法 | 不生成非 const 重载 |
| `@staticmethod` | 方法 | 静态成员 |

类型标记（非装饰器）：`Pointer[T]`、`Callable`、`Self`、`char`、`CStr`。

---

## 8. 语法与语句（译器入口速查）

在 `translator.py` 中扩展时优先搜索：

| 特性 | 入口（示例） |
|------|----------------|
| 赋值 / 注解赋值 | `visit_Assign`, `visit_AnnAssign` |
| return / pass / raise | `visit_Return`, `visit_Pass`, `visit_Raise` |
| for / async for | `visit_For`, `visit_AsyncFor` |
| while | `visit_While` |
| with / async with | `visit_With`, `visit_AsyncWith` |
| 函数调用 | `_emit_call_expr`, `visit_Call` |
| 比较 / 布尔 / 成员 | `_emit_compare`, `visit_Attribute` |
| 列表/字典/集合显示 | 字面量发射（推导式 → `comprehensions_emit`） |
| f-string | `fstring_emit.py` |
| match | `passes/match_case.py` |
| import | `imports.py`, `import_resolver.py` |
| 协程 | `coroutine_desugar.py` + `visit_AsyncFunctionDef` 相关 |

### 8.1 `range` 译法（勿恢复 range_shim）

| 写法 | 实现 |
|------|------|
| `for i in range(a, b, s)` | 原生 C++ for，**无** `PyRange` |
| `len(range(n))` | `_emit_range_len_expr` |
| `r = range(n)`、`for x in r` | `runtime_make_range_expr` → `(::py2cpp::util::range::PyRange)(n)` 等（两重载 ``__init__``；实现见 ``util/range.py``） |

### 8.1.1 `prange` / OpenMP（`py2cpp/concur/parallel`）

须 `from py2cpp.concur.parallel import prange`；``for i in prange(...)`` 由 ``prange_emit.py`` 发射（**非** ``@native``、无 C++ ``prange`` 函数）。两重载（对齐 ``range``）：``prange(stop, *, …)`` / ``prange(start, stop, step=1, *, …)``。

| 写法 | 实现 |
|------|------|
| `for i in prange(n)` / `prange(a,b,s)` | ``#pragma omp parallel for`` + 原生 ``for (int i=…)``（同 ``range`` 负 step 分支） |
| ``th``（默认 ``0``） | 并行阈值：``trip >= th`` 才发射 OpenMP；``th=0`` 恒并行；常量 trip/th 译期选路，否则 ``if (len…) { omp } else { for }`` |
| 循环体顶层 ``total += …`` 等 | ``reduction(+:total)``（``+/-/*/&/|/^``） |
| ``schedule`` / ``numThreads`` / ``chunkSize`` | 关键字须编译期常量；``static`` 省略 clause |
| ``--no-openmp`` | 译期不发射 pragma，降级为普通 ``range`` ``for`` |
| 编译 | 生成物含 ``#pragma omp`` 时 ``cl /openmp`` 或 ``-fopenmp``（``compile.py`` 自动探测） |

约束（``parallel_loop_check.py``）：禁止嵌套 ``prange``、``break``。


`len`、`print`、`zip`、`enumerate`、`iter`、`next`、`aiter`、`anext`、`reversed`、`repr`、`new` 等在 `py2cpp/__init__.py` 声明；具体发射在 `translator` + `operators.h`。

| 内建 | 发射要点 |
|------|----------|
| `enumerate` | `for i, x in enumerate(seq[, start])`：``seq`` 可 ``__len__``+``__getitem__(int)`` 时 → 索引 ``for`` + ``i = start + fi``（``_for_enumerate`` / ``_index_for_loop_plan``）；否则 ``EnumerateIterator<T>`` + ``PyTuple<int,T>`` |
| `zip` | ``ZipIterator`` + ``PyTuple`` 步进（无索引内联） |
| `new`（类体字段） | ``buf: char[:] = new(0)`` → 成员 ``_buf = PyArray<PyChar>(0)``（``_emit_field_default_initializer``）；裸 ``new()`` 无类型上下文报错 |
| `obj.attr`（模板形参） | 无法绑定 ``ClassInfo`` 时 → ``PY2CPP_GETATTR`` + 每 TU ``PY2CPP_DECLARE_GETATTR(attr)``；注解形参 → ``get_attr()`` |

### 8.3 Pythonic 字面量 → 内联 C++（查阅表）

**原则**：源码仍写规范 Python（`in`、`[]`、`match` 等）；脱糖/内联在译器或容器协议内完成，**勿**在业务模块手写 C 式扫串或重复 `splitExt` 语义（见 [编码规范 §7](../../../docs/编码规范.md#7-算法与-pythonic-控制流)）。

#### 8.3.1 元组字面量：禁止作「容器」

下列写法 **译期报错**（`NotImplementedError`）；**其它**元组用法不变（返回值、`divmod`、`"%d %d" % (a,b)` → `makeTuple`、`PyTuple` 变量下标、`template get<N>()` 等）。

| ❌ 不再支持 | ✅ 替代写法 | 内联 C++ 形态 |
|-------------|-------------|----------------|
| `x in (a, b, c)` | `x in {a, b, c}`（`s: set[T] = {a,b,c}`） | `PySet` + `__contains__` |
| | `x == a or x == b or x == c` | `(x==a || x==b || x==c)` |
| | `match x: case a: … case b: …` | `switch(x)`（`int`/`bool`/`char` 字面量模式） |
| `(a, b, c)[i]` | `tab: list[T] = [a, b, c]; tab[i]` | `PyList` + `__getitem__`；**常量 `i`** 可后续脱糖为 `switch` |
| | `match i: case 0: … case 1: …` | `switch(i)` |
| | `t: PyTuple<…> = (a,b,c); t.get<k>()` 或 `t[k]`（**变量**，非字面量） | `PyTuple` 聚合；常量下标 → `get<N>()` |

仍支持（不变）：

| 用法 | 内联 / 译法 |
|------|-------------|
| `(a, b)` 返回值、解包、`divmod` | `PyTuple<…>(a,b)` |
| `(int, int)` 类型注解 | `PyTuple<PyInt, PyInt>` |
| `t[i]`（`t` 为 `PyTuple` 变量） | `__getitem__` 或常量 `get<N>()` |
| `a < x < b` | `(a<x)&&(x<b)` |
| `x if c else y` | 三目 |
| `match` / `case` 字面量 | `switch` / `if` 链 |

#### 8.3.2 列表 / 成员 / 分支（非 dict，不变）

| Python | 推荐写法 | 当前 / 目标内联 |
|--------|----------|-----------------|
| `x in seq` | `x in lst` / `sub in s` | `seq.__contains__(x)` |
| `x: list[T] = [a,b,c]` | 带注解列表字面量 | `PyList` + `append` 初始化 |
| `[a,b,c][i]` | 链式字面量 | 常量 `i` 直接取元素；变长 `i` + 常量元素 → `static const T _tbl[]`（``literal_sequence_lookup``） |
| `x in [a,b,c]` | 链式字面量 | 常量元素 → `\|\|` 链 |
| `c in "abc"`（``char`` 码点） | 标准库/用户 | 逐码点 `c == PyChar('a')\|\|…`；**勿**写 `c in {97,98,99}` |
| 单码点 | `c == 32` | 勿 `c in {32}` |
| `x in "abc"`（``str`` 子串） | 链式字面量 | 同上或 `PyStr.find` |
| `"abc"[i]` | 链式字面量 | 常量 `i` → `PyChar`；变长 → `PyStr("...").__getitem__(i)` |
| `s[i] == '"'` / `!=` | ``str`` 下标 vs 单字符字面量 | ``PyChar(码点)`` 对 ``PyChar``（``visit_Compare`` / ``_try_emit_char_scalar_compare``）；勿 ``PyStr("…")``（MSVC C4805） |
| `s[i] in '"'` | 成员检测 | ``try_emit_str_literal_contains`` → ``PyChar`` 链（与 ``==`` 路径一致） |
| `"abc".find(sub)` / `.index` / `.rfind` / `.rindex` | 链式字面量 | 小表 + 常量子串 / ``char`` 针：`static const PyChar _h[]` + 循环；`.index`/`.rindex` 未命中 `throw ValueError` |
| `lst.index(y)` | 列表 API | `index()`；小表 + 常量 `y` → 可 `switch` |
| `for i in range(n)` | 标准库 | 原生 `for (int i=…)` |
| `not s` / `if s` | 编码规范 §3.1 | 隐式真假，勿 `len(s)==0` |

#### 8.3.3 字典字面量及相关 Pythonic 写法

**须有类型上下文**：`d: dict[K,V] = …` 或 `return` / 形参注解；**无**裸 `{k: v}` 表达式（见 [编码规范 §2.1](../../../docs/编码规范.md#21-对照表)）。

##### 8.3.3.1 内联映射字面量查表（`{a: x, b: y}[k]`、`{…}.get(k, z)`）

把**小映射字面量**当作一次性查表。裸 `{…}` 仍不可单独作表达式（`visit_Dict`）；**链式** ``{a:x,b:y}[k]`` / ``{…}.get(k,z)`` 在 ``visit_Subscript`` / ``visit_Call`` 脱糖（``literal_map_lookup``）。

| Python（字面量链式） | 当前 | 内联 C++ |
|----------------------|------|----------|
| `{a: x, b: y}[k]` | ✅ | 字面量键全为常量：`IIFE` + `if (k==a) return x;` … `throw KeyError` |
| `{a: x, b: y}.get(k, z)` | ✅ | 字面量键全为常量：嵌套三目 `(k==a ? x : (k==b ? y : z))` |
| `f({a: x, b: y}[k])` | ✅ | 同上（表达式内 IIFE/三目） |
| 字面量含非常量键或 `{**a, k: v}` | ✅ | IIFE 内临时 `PyDict` + `__setitem__`/`update` + `__getitem__`/`get` |
| `v: V = {a: x}.get(k, z)`（赋给注解变量） | ✅ | 仍可用链式 `.get` 内联；或 `tab: dict[K,V] = {…}` + `tab.get` |
| `return {a: x, b: y}[k]` | ✅ | 同 ``[k]`` 行 |
| 查找键 `k` 为变量 | ✅ | 与字面量键是否常量无关；脱糖形态见上（三目/IIFE 仍用运行时 `k`） |

与 **list 查表**对照：

| | list | dict |
|---|------|------|
| 字面量链式下标 | `[a,b,c][i]` ✅（§8.3.2；连续下标优先 `list`） | `{a:x,b:y}[k]` ✅（§8.3.3.1；稀疏键用 `dict`） |
| 字面量 + 方法 | — | `{…}.get(k,z)` ✅ |
| 目标零成本形态 | `switch(i)` / 常量 `get<i>()` | `switch(k)` / `(k==a?x:…)` |

**书写**：小表可用 `{a:x,b:y}[k]` / `.get(k,z)`；大表或需复用映射仍写 `tab: dict[K,V] = {…}`。与 §8.3.1 禁止 `(a,b,c)[i]` 不同——**元组字面量**不可作容器，**映射字面量**仅允许链式查表形态。

| Python | 规范写法 | 译器内联 / 生成 C++ |
|--------|----------|---------------------|
| 空映射 | `d: dict[K,V] = {}` / `d: Self = {}`（类内） | 声明 `PyDict<K,V>` + 空构造 |
| 键值字面量 | `d: dict[K,V] = {k1: v1, k2: v2}` | 逐对 `__setitem__(k, v)`（`emit_dict_literal`） |
| 合并映射 | `d: dict[K,V] = {**base, k: v}` | `base.update(…)` + `__setitem__`（`key is None` → `update`） |
| 字典推导 | `d: dict[K,V] = {k: v for k in it if cond}` | 空 `PyDict` + 循环内 `__setitem__`（`emit_dict_comprehension`） |
| 读键 | `d[k]` | `__getitem__(k)` |
| 安全读 | `d.get(k, default)` | `get` 方法（内部 `k in self`） |
| 写键 | `d[k] = v` | `__setitem__` |
| 删键 | `del d[k]` | `__delitem__` |
| 成员 | `k in d` / `k not in d` | `__contains__` / 取反 |
| 长度 | `len(d)` | `__len__()` |
| 迭代键 | `for k in d:` | `__iter__()`（用户/测试）；**dict 实现体**内 `copy`/`update` 等用 `range(len(_order))` 读 `_order[i]`（防递归，见编码规范） |
| 不可变 | `fd: frozendict[K,V] = {…}` | 临时 `PyDict` 填键值 → `initFromDict` |
| 空 dict 误用 | `{}` 单独作 set | **禁止**；set 用 `set()` 或 `{a,b}` |

与 **set** 字面量区分：`{a, b}` + `set[T]` 注解 → `PySet`；`{k: v}` + `dict[K,V]` → `PyDict`。

#### 8.3.4 dict 相关：常用但未实现 / 仅部分支持的 Pythonic 内联

下列写法在 CPython 里很常见；与 §8.3.3 **已实现** 项对照。内联列为**目标 C++ 形态**（译器脱糖或标准库补 API 后），**非**当前生成代码（除非注明 ✅）。

**A. 字面量形态与类型上下文**

| Python（常见） | 状态 | 说明 / 目标内联 |
|----------------|------|-----------------|
| 裸表达式 `{k: v}`、`f({1: 2})` 实参 | ❌ | `visit_Dict` 报错；须 `d: dict[K,V] = {…}` 或带 `-> dict[K,V]` 的 `return` |
| **`{a:x,b:y}[k]`、`{…}.get(k,z)`** | ✅ | 见 **§8.3.3.1**（常量键内联；非常量键/`**` → 临时 `PyDict`） |
| `return {k: v}`（函数无返回注解） | ❌ | 同左；有 `-> dict[K,V]` 时走注解赋值路径 ✅ |
| `dict()` / `dict(other)` 构造器一行式 | ⚠️ | 用 `d: dict[K,V] = {}` + `update` / `copy`；无「空 dict() 表达式」内联 |
| `dict(zip(keys, vals))` | ⚠️ | 无内建脱糖；手写循环 `__setitem__` 或 `dict.fromKeys` + 改值 |
| `dict.fromKeys(keys, v)` | ✅ 方法 | `PyDict::fromKeys`；非字面量，但替代 `{k: v for k in keys}` |
| 嵌套 `{1: {2: 3}}` | ⚠️ | 值侧子 `dict` 须各自带注解初始化；**无**递归字面量一次折叠为静态树 |
| `{**a, **b, **c}` 多重展开 | ✅ | 多次 `update`（`emit_dict_literal` 中 `key is None`） |
| `{**a, k: expr()}` 动态键/值 | ✅ 键值表达式 | 逐对 `__setitem__(visit(key), visit(val))`；**无**编译期小表优化 |
| `m = a \| {k: v}` / `a \| b` | ✅ | `__or__` / `__ior__`（`dict.py`）；右侧 `{…}` 仍须左侧有类型上下文 |
| 小映射编译期常量表 `{"red": 1, "green": 2}` | ❌ 脱糖 | 仍生成 `PyDict` + 逐 `__setitem__`；目标：`switch`/`constexpr` 查表（未做） |

**B. 推导式与解包**

推导式须与**同型字面量**共用左侧注解的完整 C++ 容器类型（``list``/``deque``/``frozenlist``、``set``/``frozenset``、``dict``/``frozendict``/``Counter`` 等）；不可变容器仍经临时可变兄弟 + ``init_from_*``，与字面量路径一致。

| Python | 状态 | 说明 / 目标内联 |
|--------|------|-----------------|
| `{k: v for k in keys}` | ✅ | 空 dict + 循环 `__setitem__` |
| `{k: v for k in keys if cond}` | ✅ | 同上 + `if` 包裹 |
| `{k: v for i in range(n)}` | ✅ | `range` 生成器 → 原生 `for` |
| `{k: v for i in a for j in b}` 嵌套 `for` | ✅ | 嵌套循环 + `__setitem__`（同列表推导） |
| `{k: v for k, v in pairs}` | ❌ | `for` 目标仅简单名 / `zip`·`enumerate` 元组；**无** `for k,v in d.items()` |
| `{k: v for k in d}`（遍历 dict 键） | ✅ | `d.__iter__()` |
| `{v: k for k, v in d.items()}` 反转 | ❌ | 依赖 `items()` + 元组解包 `for` |
| `{**d, k: v for k in keys}` | ❌ 语法 | Python 非法；须分两句 |
| 推导式 `async for` | ❌ | 推导式 pass 拒绝 `async for` |
| 推导式目标为 `dict`（嵌套 dict 作值） | ⚠️ | 值表达式若含 `{…}` 须单独注解赋值 |

**C. 遍历、视图与「字面量风格」API**

| Python | 状态 | 说明 / 目标内联 |
|--------|------|-----------------|
| `for k in d` | ✅ | `__iter__()` 键 |
| `for k in d.keys()` | ✅ | `keys()` 视图 + 迭代器 |
| `for v in d.values()` | ✅ | 测试 `DictViewTests` |
| `for item in d.items()` | ✅ | `PyTuple` 元素；**无** `for k,v in` 解包 |
| `for k, v in d.items()` | ❌ | `_for_iter` 仅 `ast.Name` 目标；目标：解包为 `get<0>()`/`get<1>()` |
| `for k, v in zip(d.keys(), d.values())` | ⚠️ | 可手写；**无**直接 `items()` 解包糖 |
| `len(d)` / `k in d` | ✅ | `__len__` / `__contains__` |
| `d.keys()` / `.values()` / `.items()` 多次遍历 | ✅ | 视图对象；**无**零拷贝「字面量快照」脱糖 |
| `reversed(d)` / `sorted(d)` | ❌ | 无 dict 专用内建；勿假设 C++ `std::map` |
| `all(d.values())` / `any(...)` | ❌ | 无 `dict` 专用内建；手写 `for` |
| `next(iter(d.values()))` | ⚠️ | `iter`/`next` ✅；组合需手写 |

**D. 合并、缺省与调用侧解包**

| Python | 状态 | 说明 / 目标内联 |
|--------|------|-----------------|
| `d.get(k, default)` / `d.setDefault` | ✅ | 方法体内 `in` + `__getitem__` |
| `d[k] if k in d else default` | ✅ | 三目 + `in` |
| `collections.defaultdict(factory)` | ❌ | 无标准库模块；目标：子类或译器脱糖（未做） |
| `d \|= other` / `d = a \| b` | ✅ | `__ior__` / `__or__` |
| `f(**mapping)` 调用解包 | ❌ | 无 `**kwargs` 调用展开（`@kwargs_options` 仅构造） |
| `Cls(**{k: v, ...})` 关键字构造 | ⚠️ | `@kwargs_options` / `new(k=v)`；**非**任意 `**dict` |
| `match x: case {"a": v}:` 映射模式 | ✅ | 字面量键 + ``__contains__`` / ``__getitem__``；``**rest`` 脱糖；``MatchOr`` **捕获名集合+类型**一致（不限键序） |
| `match x: case {k: v}:` 键捕获 | ❌ | 首期仅字面量键 |
| `match x: case [a, b]:` 序列模式 | ✅ | ``PyTuple`` → ``get<i>()``；``*rest`` 负索引；``MatchOr`` **捕获名集合+类型**一致（不限槽位顺序） |
| `match obj: case new(kw=…):` 用户类 | ✅ | 仅关键字；只读 ``@property`` → ``get_*()``；``MatchOr`` **捕获名集合+类型**一致（不限顺序）；勿 ``Cls(...)`` / ``Self(...)`` |
| `operator.itemgetter` / 解构 | ❌ | 无 `operator` 模块 |

**E. 其它容器互转（常被当作 dict 字面量前奏）**

| Python | 状态 | 说明 / 目标内联 |
|--------|------|-----------------|
| `frozendict({…})` / `fd: frozendict = {…}` | ✅ | 临时 `PyDict` → `initFromDict` |
| `dict(fd)` / `fd.copy()` | ⚠️ | 用 `copy` / 迭代构造；**无** `dict(mapping)` 内建 |
| `list(d)` / `[*d]` | ❌ / ⚠️ | 键列表须 `for k in d` + `append`；**无** `[*d]` 解包到 list |
| `set(d)`（键集合） | ⚠️ | `for k in d: s.add(k)`；**无** 一行内建 |
| `str.translate(table)` 中 `table: dict[int,int] = {…}` | ✅ | 注解 dict 字面量 + `makeTrans` 范本 |

**书写建议（在未实现项落地前）**

- 需要 **键值对遍历**：`for item in d.items():` 后用 `item` 的 `PyTuple` 下标（或先赋给具名元组变量再 `.get<0>()`），勿写 `for k, v in d.items()`。
- 需要 **一行建表**：`d: dict[K,V] = {k: v for k in keys}` ✅；勿 `dict(zip(...))` 除非接受手写循环。
- 需要 **合并**：优先 `a | b`、`{**a, k: v}`（带注解），勿裸 `{…}` 出现在表达式位置。
- 需要 **小常量查找表**：考虑 `match`/`switch`（标量键）或 `list` 并行数组 + 下标，勿依赖元组字面量容器（§8.3.1）。

---

## 9. CLI（`main.py`）

```text
python main.py <input.py> [-o DIR] [--no-stdlib] [--no-main] [--debug]
  [--openmp | --no-openmp]
  [-c] [--compiler auto|g++|clang++|cl|msvc] [--exe PATH] [--obj-only]
```

| 参数 | 含义 |
|------|------|
| `-o` | 输出根（默认 `generated/`） |
| `--no-stdlib` | 不翻译标准库 |
| `--no-main` | 不包装 main；runtime bootstrap 用 |
| `--debug` | 插入 `fprintf` 调用跟踪；``__debug__`` → ``true`` |
| `--openmp` / `--no-openmp` | ``prange`` 是否发射 OpenMP（默认开；``--no-openmp`` 降级为 ``range``） |
| `-c` | 翻译后编译 |
| `--compiler cl` | Windows 推荐 MSVC |
| `--exe` | 指定可执行文件路径 |

批处理（仓库根）：``build.bat PATTERN`` / ``run.bat PATTERN`` / ``demo.bat PATTERN`` — 分别匹配 ``test/**/test_*.py``、运行已编译测试 exe、``examples/**/*.py`` 翻译+编译+运行。

---

## 10. 测试矩阵

### 10.1 集成测试（`test/`）

| 文件 | 脚本 | 覆盖重点 |
|------|------|----------|
| `test/util/test_list.py` 等 | `build_all.bat` | list/dict/deque/set/range |
| `test/core/test_delegate.py` | `build_all.bat` | `@delegate` / `Callable` / `Function` |
| `test/text/test_str.py` | `build_all.bat` | str API、format / f-string、字面量内联 |
| `test/text/test_bytes.py` | `build_all.bat` | bytes |
| `test/misc/test_chr_ord.py` | `build_all.bat` | `chr` / `ord` / `byte` |
| `test/io/test_io.py` | `build_all.bat` | `with`、`py_open` |
| `test/io/file/test_file.py` | `build_all.bat` | ``os`` 磁盘 API（``getCwd``/``stat``/``listDir``/…） |
| `test/io/file/test_path.py` | `build_all.bat` | ``os.path``（``join``/``splitExt``/…） |
| `test/io/test_path.py` | `build_all.bat` | `Path`、`/` |
| `test/sql/test_sqlite.py` | `build.bat sql/test_sqlite` | ``py2cpp/sql`` DB-API（P0 已落地）；见 [sql-orm.md](../../../docs/sql-orm.md) |
| `test/sql/test_sql_orm.py` | `build.bat sql/test_sql_orm`（**设计中，P1**） | ``table[User]()`` + ``*Meta`` / ``all`` / ``get`` / ``append`` |
| `test/sql/test_sql_orm_genexp.py` | `build.bat sql/test_sql_orm_genexp`（**设计中，P2**） | ``extend`` / ``execute(e.assign…)`` / ``collect`` / ``remove`` + ``SqlQuery[T]`` |
| `test/sql/test_sql_orm_join.py` | `build.bat sql/test_sql_orm_join`（**设计中，P3**） | ``session.collect[RowT](Row(…) for o in orders for u in users if …)`` → ``SqlQuery[RowT]`` |
| `test/system/test_time.py` | `build_all.bat` | time / float64 / int64 |
| `test/perf/test_json_serde.py` | 手动 / 专用脚本 | 性能（默认跳过 `build_all.bat`） |
| `test/lang/test_dataclass.py` | `build_all.bat` | `@dataclass`、`new` |
| `test/lang/test_enum.py` | `build_all.bat` | `@enum`、`flag=True`、`match` 枚举模式 |
| `test/lang/test_kwargs_options.py` | `build_all.bat` | `@kwargs_options` |
| `test/lang/test_selector.py` | `build_all.bat` | ``select`` 路径 DSL（``:$``/``$``/``;``、filter、投影） |
| `test/lang/test_build.py` | `build_all.bat` | ``build`` 对象构造 DSL（``[:N] >``、``:$i``） |
| `test/lang/test_generator.py` | `build_all.bat` | `yield` |
| `test/lang/test_async.py` | `build_all.bat` | async/await |
| `test/concur/test_parallel.py` | `build.bat concur` | ``prange`` / OpenMP / reduction / 负 step |
| `test/ui/test_panel.py` | `build.bat panel` | ``UIPanelMixin`` / ``UIInvisibleMeta`` / ``UILabelMeta`` / ``RangeVar`` |
| `test/ui/test_widget.py` | `build.bat button` | ``ui/widget``：控件字段与 ``UIButtonMeta`` |
| `test/ui/test_window.py` | `build.bat ui\\window` | ``ui/window`` Win32 ``begin``/``draw``/``end`` |
| `test/ui/test_style.py` | `build_all.bat` | ``ui/style`` 默认值 |
| `examples/ui_panel_demo.py` | `demo.bat panel` | 交互 Win32 Panel 窗口（``run`` 阻塞至关闭） |
| `test/lang/test_decorator.py` | `build_all.bat` | `@decorator`、`@context` |
| `test/lang/test_friends.py` | `build_all.bat` | `friends=` |
| `test/lang/test_stack_array.py` | `build_all.bat` | 栈数组字面量 |
| `test/lang/test_protocol.py` | `build_protocol.bat` | `@protocol` 正向 |
| `test/lang/test_*.py`（其余） | `build_all.bat` | dunder / move / 空 main |
| `test/util/test_pool.py` | `build_all.bat` | pool 功能 + 微基准 |
| `test/import_tests/test_import.py` | `build_all.bat` | import / 命名空间 |
| `test/fail/test_*_fail.py` | `build_fail.bat` | 预期编译失败 |

**unittest 结构**（编码规范 §10）：`TestCaseMixin` + `@override def test(self)` + `main()` 里 `suite: TestSuite = new()` / `TextTestRunner`；``iterSubclasses(sortConst="_testTag")`` 按 ``static const`` 升序（``@mixin`` 展开，无运行时反射）。

### 10.2 推荐验证命令

```bat
python main.py py2cpp\__init__.py -o generated --no-main
build_all.bat
build_protocol.bat
```

按模式编译（子串或 `*` `?` 通配，跳过 `test\fail\` / `test\perf\`）：

```bat
build vararg
build lang\test_*variadic*
run vararg
run lang\test_*variadic*
build containers misc\test_range
```

等价手写单文件：

```bat
python main.py test\misc\test_containers.py -o generated -c --compiler cl --exe generated\test\misc\test_containers.exe
generated\test\misc\test_containers.exe
```

---

## 11. MSVC 排错（扩展）

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| `'cl' 不是内部或外部命令` | 未进 vcvars 环境 | `build_*.bat` 或 Native Tools Prompt |
| 翻译 Ok、链接旧符号 | 未重链 | 全量重编；`main.py -c` / `build_*.bat` 会自动删 `.obj` |
| LNK2005 | 同时链 `py2cpp.cpp` + 含实现的万能头 | `compile.py` 对 `test/` 已跳过 `py2cpp.cpp` |
| LNK2019 `py_open` | 缺 `io.inl` 或未链入 | 重译 runtime |
| `PyRange` 未声明 | 未 include `minimal.h`（或 `util/range`）或 namespace 尾块污染 | 用 `(::py2cpp::util::range::PyRange)(n)`；勿乱改 umbrella |
| `C2065: Args` | `protocol_traits` 中 `__mod__` 缺 `template<typename... Args>` | 修 `translator._emit_module_protocol_traits` |
| `py2cpp::std::pair` | traits 在 `namespace py2cpp` 内 include 标准头 | traits 保持全局 include |
| `PyTuple` 歧义 | 误写 `py2cpp::PyTuple` | C++ 类型为全局 `PyTuple`；Python 侧用 `tuple[...]` / `from py2cpp import *` 的 `tuple` |
| C1003 错误过多 | 前面头文件已坏 | 从第一条语义错误修起，勿只看最后一条 |

`build_all.bat` 的 `InitMSVC`：vswhere → `vcvars64.bat` → 回退固定 VS2022/2019 路径。

---

## 12. 编码规范速查（标准库 / 测试）

| 场景 | 推荐 |
|------|------|
| 空串 | `""` |
| 空 list | `x: list[T] = []` |
| 空 dict | `d: dict[K,V] = {}` |
| 同类新实例 | `Self()` |
| 用户类构造 | `obj: Cls = new(a=1)` |
| `@copyable` 拷贝 | `dst: Cls = src` |
| 下标 / in / len | 运算符，勿 `. __getitem__` |
| 文件真值 | `assertTrue(f)`，勿 `f.__bool__()` |
| 生成器步进 | `next(g)`（包根 `next`） |

---

## 13. 改动的文档同步

| 改动类型 | 更新文档 |
|----------|----------|
| 用户可见语法/标准库 API | `docs/参考手册.md` §6–10 |
| 标准库写法/测试范本 | `docs/编码规范.md` |
| ``select`` 路径 DSL / 分期 | `docs/selector.md`（详规）+ 参考手册 §7.9 + 编码规范 §7.5 |
| ``build`` 对象构造 DSL | `docs/build.md`（详规）+ 参考手册 §7.10 + 编码规范 §7.6 |
| ``alg`` 竞赛/游戏数据结构（设计稿） | `docs/alg.md`（详规 + P0–P4 分期；实现后同步参考手册 / 编码规范 §8.1） |
| Agent 流程/排错 | `.cursor/skills/py2cpp-design/SKILL.md`、本文件 |

---

*附录版本：2026-08-05（标准库域布局、译器 `src/`、废弃 `builtins/`）；实现变更以 `src/translator.py`、`constant/stdlib_layout.py`、`analysis/runtime_symbols.py` 与 `py2cpp/` 源码为准。*
