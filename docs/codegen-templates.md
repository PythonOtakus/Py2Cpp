# Codegen C++ 模板：七宏（`BEGIN` / `END` / `EVAL` / `Exec` / `ECHO` / `INCLUDE` / `TYPE`）

> **状态**：`templates/**` 为 `@native` 叶子真相源（`expand_py2cpp_template` / `stdlib_mirror_codegen` / inject paste）；旧 `src/codegen/*_cpp.py` **已删除**  
> **受众**：维护 `templates/**`、`*_gen.py`、编写 `@native` 叶子 C++ 的开发者  
> **关联**：[参考手册 §8 生成风格](./参考手册.md#85-protocol-与-sfin-约束)、[编码规范 §9.4 Native 原子化](./编码规范.md#94-native-原子化基础设施)、用户译器 `inlineRange`（`src/passes/inlineRange.py`）

**定案**：**7 个作者向宏**——`PY2CPP_BEGIN` / `PY2CPP_END` / `PY2CPP_EVAL` / `PY2CPP_EXEC` / `PY2CPP_ECHO` / `PY2CPP_INCLUDE` / `PY2CPP_TYPE`。另有 IDE 辅助宏（`IGNORE`、`INJECT_CLASS`、`BEGIN_SCOPE` 等）见 [§3.4](#34-宏对照表)。**整文件**模板的注释与 include guard 由 ``stdlib_mirror_codegen.finalize_codegen_file_text`` / ``expand_whole_file_template`` 在 Python 侧包壳，**不再**使用模板内宏。**不实现** `SET` / `STMT` / `SYM` / `MACRO` / `RAW` / `loop.*` / 草案 `EMIT`；见 [§14](#14-已弃用宏勿使用) 与 [§16](#16-七宏定案)。

---

## 0. `codegen/` 与 `emit/` 分工

| 包 | 何时用 | 典型模块 |
|----|--------|----------|
| `src/codegen/` | 展开 `templates/**`、写 runtime 固定头/traits、umbrella 聚合 | `expand_py2cpp_template`、`umbrella_gen`、`protocol_traits_gen`、`delegate_gen`、`stdlib_mirror_codegen` |
| `src/emit/` | 遍历 AST 生成用户/标准库 C++ 正文 | `call_emit`、`loops_emit`、`class_emit`、`layout_emit`（编排写盘） |

**灰区**：`layout_emit` 在 `emit/` 但调用 `codegen.expand_template`；`protocol_traits_gen` 引用 `emit/compile_diagnostic_emit` 诊断文案。改路径时两边 import 一并更新。

**命名**：构建期生成器以 `*_gen.py`（`umbrella_gen`、`protocol_traits_gen`、`delegate_gen`）；AST 侧以 `*_emit.py`。

---

## 1. 背景与动机

Py2Cpp 标准库中大量 `@native` 实现写在仓库根 `templates/**`（`+*.inl` / `-*.inl` / 镜像 `.h`）：经七宏展开与 inject paste 写入 `generated/runtime/py2cpp/**/*.inl`。（历史曾用 `src/codegen/*_cpp.py` f-string，已全部迁出。）

| 痛点 | 说明 |
|------|------|
| **clangd 不可解析** | f-string 里的 C++ 对 IDE 是字符串，无补全、无跳转、难发现括号/分号错误 |
| **循环难写** | 重复 C++ 行常靠手写 `for _ in range(n): lines.append(f'…')`，与模板正文分离 |
| **与译器语义分裂** | 用户侧 `for i in range(n)` 由译器/`inlineRange` 展开；codegen 侧却另写一套 Python 循环 |

本方案在 **codegen 预展开阶段** 引入与 CPython 等价的「转 Python 再执行」模型，使模板源文件接近真实 C++，同时 **循环**（`for` / `range`）与 **条件**（`if` / `elif` / `else`）与用户 Python 侧同一套 f-string / 编译期求值心智。

---

## 2. 目标

1. **模板源**：仓库根 `templates/**`（相对路径与后缀与 `generated/runtime/py2cpp/**` 一致，见 [§8](#8-目录与路径镜像)）为 **合法 C++ 骨架** + `PY2CPP_*` 宏孔洞，供 clangd 粗解析。
2. **展开语义**：`PY2CPP_BEGIN` / `END` / `EVAL` 块 **逻辑等价** 于将其降为下方 Python 并在 **codegen 时** 用 CPython 执行，收集发射的 C++ 行。
3. **表达式/语句**：宏参数内允许 **任意合法 CPython 表达式或语句**（非自定义 mini-语言）。
4. **输出**：展开后的纯 C++ 经 `kr_to_allman` → 现有 `paste_cpp_to_inl_target` 流水线 → `generated/*.inl`；**MSVC 只编译展开结果**，不含 `PY2CPP_*`。
5. **边界与分支**：
   - `for` / `range`：编译期可求界 → 完全展开；运行时界 → 回退 C++ `while`。
   - `if` / `elif` / `else`：编译期可求值条件 → `exec` 时死分支消除（不发射）；运行时条件 → 回退 C++ `if` / `else if` / `else`。

---

## 3. 宏与对照关系

### 3.1 模板写法（`for` 示意）

```cpp
PY2CPP_BEGIN( for i in range(10) )

cout << "i: " << PY2CPP_EVAL(i) << endl;

PY2CPP_END
```

### 3.2 模板写法（`if` / `elif` / `else` 链）

`PY2CPP_BEGIN` 参数除 `for …` 外，支持完整 CPython **`if` / `elif` / `else` 头语句**（带冒号语义，参数内可省略末尾 `:`，展开器规范化后 `ast.parse`）。

按类型分派多路 C++（编译期 `typ` 为字面量时只发射命中分支）：

```cpp
PY2CPP_BEGIN( if typ == SQLITE_INTEGER )
  sqlite3_bind_int(stmt, PY2CPP_EVAL(idx), PY2CPP_EVAL(val));
PY2CPP_END
PY2CPP_BEGIN( elif typ == SQLITE_TEXT )
  sqlite3_bind_text(stmt, PY2CPP_EVAL(idx), PY2CPP_EVAL(txt), -1, SQLITE_TRANSIENT);
PY2CPP_END
PY2CPP_BEGIN( else )
  sqlite3_bind_null(stmt, PY2CPP_EVAL(idx));
PY2CPP_END
```

逻辑等价的 Python（自动生成并 `exec`）：

```python
if typ == SQLITE_INTEGER:
  __py2cpp_echo(f'sqlite3_bind_int(stmt, {idx}, {val});')
elif typ == SQLITE_TEXT:
  __py2cpp_echo(f'sqlite3_bind_text(stmt, {idx}, {txt}, -1, SQLITE_TRANSIENT);')
else:
  __py2cpp_echo(f'sqlite3_bind_null(stmt, {idx});')
```

**链式规则**：紧跟在前一个 `PY2CPP_END` 之后的 `PY2CPP_BEGIN( elif … )` / `PY2CPP_BEGIN( else )` 与前一 `if` 合并为同一 Python `if` 链（再一次性 `exec`）；**禁止**孤立 `elif` / `else`（无前导 `if`）。

块内可嵌套 `PY2CPP_BEGIN( if … )`（栈式展开）；`if` 体内可嵌套 `PY2CPP_BEGIN( for … )`，反之亦然。

### 3.3 逻辑等价的 Python（`for`，codegen 自动生成并执行，作者不必手写）

```python
__py2cpp_code: list[str] = []

def __py2cpp_echo(s: str) -> None:
  __py2cpp_code.append(s)

for i in range(10):
  __py2cpp_echo(f'cout << "i: " << {i} << endl;')
```

### 3.4 宏对照表

| 模板 | 展开侧 |
|------|--------|
| `PY2CPP_BEGIN( for … )` | 参数为完整 `for` 语句（`ast.parse` 为 `ast.For`），原样嵌入生成的 Python |
| `PY2CPP_BEGIN( if … )` | 参数为 `if` 测试表达式或完整 `if cond:` 行（`ast.If`，`orelse` 为空） |
| `PY2CPP_BEGIN( elif … )` | 须紧接 `if` / `elif` 链；参数为 `elif cond:`；与前一分支合并为同一 `if` 链 |
| `PY2CPP_BEGIN( else )` | 须紧接 `if` / `elif` 链；参数为 `else` 或 `else:` |
| `PY2CPP_BEGIN( def fn_Name(…) )` | 注册构建期 helper（不向 `generated/` 发射 C++）；helper 名 ``fn_`` + PascalCase；**形参** ``in_`` + PascalCase（如 ``in_Items``）；体内可嵌套 `BEGIN(for|if)`、`Exec` |
| `PY2CPP_END` | 结束当前 `for` / `if` / `def` 分支体；亦配对 ``PY2CPP_IGNORE`` / ``PY2CPP_INJECT_CLASS`` 块尾 |
| `PY2CPP_EVAL(expr)` | C++ 行内 **CPython 表达式**；构建期可求值的常量 → 与译器 `ir` 一致的 **C++ 字面量**（如 `"abc"` → `PyStr("abc")`）；其余 → f-string `{expr}` 或 C++ 标识符 |
| `PY2CPP_EXEC(stmt)` | **独立一行** CPython 语句或已注册 `def` 调用；构建期 `exec` / `eval` 内联 |
| `PY2CPP_ECHO(expr)` | 构建期 **CPython 表达式** → 求值为 `str` / `list[str]` 后**原样粘贴**（整行、多块或行内片段；``expr`` 在 registry 的短名 → 限定 C++ 类型）；IGNORE 内 ``#define ctx_* …`` 供 clangd |
| `PY2CPP_INCLUDE("path")` | 相对当前模板目录展开另一片段；`~` 文件仅内联、不落盘 |
| `PY2CPP_TYPE(Name)` | 短名 → 限定 C++ 类型（``_type_registry``）；模板写 ``PY2CPP_TYPE(PyStr)``；clangd 经 ``#define PY2CPP_TYPE(Type) PY2CPP_TYPE_##Type`` 展开 |
| `PY2CPP_IGNORE` | 与 ``PY2CPP_END`` 配对；块内 **仅 IDE/clangd**（``#include``、类壳、``using``、``#define ctx键``）；展开时整段剔除 |
| `PY2CPP_INJECT_CLASS(CppClass)` | 仅 ``+<stem>.h``；块内 C++ 注入类体尾部 |
| `PY2CPP_BEGIN_SCOPE` / `PY2CPP_END_SCOPE` | 按模板路径套 ``namespace py2cpp::…`` |
| `PY2CPP_NAMESPACE` | 仅 clangd ``~macro/<rel>.h``；paste 段勿用 |
| 块内无宏纯 C++ 行 | `BEGIN(for|if)` 体内经 f-string 包装；**不在** `BEGIN(def)` / `Exec` 路径则保持原样 |

与手写 f-string 的对照（`test/sql/test_sqlite.py` 末尾草图）：

```python
for i in range(10):
  print(f'cout << "i: " << {i} << endl;')
```

差别：`print` → `__py2cpp_echo`；`PY2CPP_EVAL(i)` → `{i}`；由工具从模板自动生成 Python，**不要求**在 `templates/**` 里维护平行 f-string。

更多与 `templates/sql/+sqlite.inl` / `templates/+io.inl` 对照的完整示例见 [§15 具体示例](#15-具体示例对照仓库现行-_cpppy)。**七宏单文件对照表**：[`templates/~test/~syntax_showcase.inl`](../templates/~test/~syntax_showcase.inl)（由 `src/tests/test_expand_py2cpp_template.py` 展开验证）。

---

## 4. 展开器算法

### 4.1 流水线位置

```text
templates/<mirror>.inl          # 镜像 generated/runtime/py2cpp/<mirror>.inl
  expand_py2cpp_template.py     # 扫描 → Python exec → C++ 文本 → 按镜像写 generated/
        ↓
expand_py2cpp_template.py               # 扫描 PY2CPP_* → 生成 Python → exec
        ↓
kr_to_allman（brace_style.py）          # Allman 大括号
        ↓
templates/** 的 SQLITE_IMPL 等常量
        ↓
stdlib_inject_emit.paste_cpp_to_inl_target
        ↓
generated/runtime/py2cpp/**/*.inl
```

### 4.2 单块 / 单链展开步骤

1. **扫描** `PY2CPP_BEGIN( … )` 与配对 `PY2CPP_END`；**嵌套**按栈处理；**`if` 链**在扫描层合并相邻 `if` / `elif` / `else` 块。
2. **解析** `BEGIN` 参数（去掉外层括号，必要时补 `:`）：
   - `for …` → `ast.For`
   - `if …` / `elif …` / `else` → `ast.If`（链上除末分支外 `orelse` 为空；末分支可为 `else`）
   - 其它语句 → 构建期错误
3. **变换 body**（每个分支体独立）：
   - 将 `PY2CPP_EVAL(e)` 替换为 f-string 插槽 `{e}`；
   - 对剩余 C++ 文本做 f-string 转义（`{` / `}` → `{{` / `}}`，反斜杠与引号按 f-string 规则）。
   - **独立一行** `PY2CPP_EXEC(…)` 在 INCLUDE 树展开后执行（表达式内联返回 C++ 字符串；赋值等 `exec`）。
   - 全文中的 `PY2CPP_ECHO(expr)`（**可行内**；`expr` 为完整 CPython 表达式）在块展开后求值并粘贴。
4. **拼接 Python**（`for` 单块或 `if` 链示例）：

   ```python
   __py2cpp_code = []
   def __py2cpp_echo(s): __py2cpp_code.append(s)
   # for：BEGIN 的 for + 变换后的 body
   # if 链：if / elif / else 各分支 body 依次拼接
   ```

5. **分支策略**（见 §5）：
   - 条件 / `range` 界在 `ctx` 中**可静态求值** → `exec` 完整 Python（死分支自然不 `__py2cpp_echo`）。
   - **含运行时符号** → 不 `exec` 该 `for` / `if` 链；回退为 C++ 控制流 + 体内 `PY2CPP_EVAL` 已替换为 C++ 表达式。
6. **`'\n'.join(__py2cpp_code)`** 替换原 `BEGIN…END`（及合并的 `elif` / `else` 块）区域。
7. 对全文无 `PY2CPP_*` 残留后，交 `kr_to_allman`。

### 4.3 `PY2CPP_EVAL` 替换示例

**运行时 C++ 表达式**（`ctx` 中的标识符 / 片段，或含变量的算术）：

```cpp
sqlite3_bind_int(stmt, PY2CPP_EVAL(i + 1), v);
```

生成的 Python 片段：

```python
__py2cpp_echo(f'sqlite3_bind_int(stmt, {i + 1}, v);')
```

**构建期 Python 常量 → C++ 字面量**（与 `analysis.ir` 中 `str_cpp_from_literal` / `format_cpp_float` 等一致，等价于在 `*_gen.py` 侧直接写该字面量）：

| `PY2CPP_EVAL(…)` 内表达式（构建期可求值） | 展开结果示例 |
|------------------------------------------|--------------|
| `"abc"` | `PyStr("abc")` |
| `42` | `42` |
| `True` / `False` | `true` / `false` |
| `1.5` | `1.5f` |
| `b"\x01\x02"` | `bytes_from_literal(…)` |

```cpp
static_assert(Encoder_check<Impl>::value, PY2CPP_EVAL("missing encode"));
// → static_assert(..., PyStr("missing encode"));
```

**`ctx` 键名**（`PY2CPP_ECHO(n)` 或 `PY2CPP_EVAL(n)` 在 `BEGIN(for)` 体内且 `n` 为 `"params.__len__()"`）按 **C++ 片段**粘贴。**勿**用 `PY2CPP_EVAL` 粘贴 `ctx` 字符串——独立行/行内预生成片段一律 `PY2CPP_ECHO(...)`；`PY2CPP_EVAL` 仅用于 **Python 字面量**（`"msg"`、`42`、`True`）或 **`BEGIN` 体内的循环变量/算术**。

### 4.4 `PY2CPP_EXEC` 示例（块内 CPython 语句）

```cpp
PY2CPP_BEGIN( for i in range(3) )
  PY2CPP_EXEC(if i == 0: __py2cpp_echo('// first'))
  buf[PY2CPP_EVAL(i)] = PY2CPP_EVAL(i + 1);
PY2CPP_END
```

- `PY2CPP_EVAL`：表达式 → f-string 片段。
- `PY2CPP_EXEC`：整行 CPython → 进入当前 `for` / `if` 体（或顶层 `exec` 命名空间）。

### 4.5 `PY2CPP_ECHO` 示例（`*_gen.py` 注入预生成片段）

参数为 **完整 CPython 表达式**，构建期求值后粘贴（`str` 或 `list[str]`）：

```cpp
PY2CPP_ECHO(umbrella_body_before)
PY2CPP_ECHO(a + b)
PY2CPP_ECHO(items[0])
```

**行内后缀**（init-list、声明续行等）：

```cpp
  PyFoo() : _ctx(0), _destroy_fn(0)PY2CPP_ECHO(vtable_inits)
  {
  }
```

`ctx["vtable_inits"]` 可为 `", _fn_next(0)"`；亦可用 `PY2CPP_ECHO("".join(f", _fn_{m}(0)" for m in vtable))` 等在 `*_gen.py` 侧预计算。

`umbrella_gen.build_py2cpp_umbrella_header` 将 include 列表等写入 `ctx["umbrella_body_before"]`，展开时原样插入，**无需**在模板内写 Python 循环。

---

## 5. 编译期求值 vs 运行时回退

### 5.1 `for` / `range`

| 情况 | 策略 |
|------|------|
| `range` 上下界在 `ctx` 中可求值为 `int` | 与 CPython 一致：`exec` 完全展开循环体，输出多条 C++ 语句 |
| 边界含运行时符号（如 `n` 仅为 C++ 标识符字符串） | **不在 codegen `exec` 里跑** `range(n)`；**回退** 为 C++ 循环骨架 |

回退形态（与现有手写风格对齐）：

```cpp
int i = 0;
while ((i < n))
{
  /* body：PY2CPP_EVAL 已替换为 C++ 表达式，保留循环变量 i */
  i = (i + 1);
}
```

**边界求值**建议复用 `inlineRange.py` 中 `_parse_inline_range_bound` / `_const_int_expr` 等思路，避免 codegen 与用户译器两套 `range` 语义。

### 5.2 `if` / `elif` / `else`

| 情况 | 策略 |
|------|------|
| 链上各条件在 `ctx` 中可求值为 `bool`（字面量、`==` / `is` 于常量、`ctx` 内 `int` 等） | `exec` 整条 `if` 链；未命中分支 **不发射** C++ |
| 任一条件含运行时 C++ 符号（如 `typ == SQLITE_INTEGER` 中 `typ` 为变量名） | **不 `exec` 该链**；回退 C++ `if` / `else if` / `else` |

回退形态（示意）：

```cpp
if ((typ == SQLITE_INTEGER))
{
  sqlite3_bind_int(stmt, idx, val);
}
else if ((typ == SQLITE_TEXT))
{
  sqlite3_bind_text(stmt, idx, txt, -1, SQLITE_TRANSIENT);
}
else
{
  sqlite3_bind_null(stmt, idx);
}
```

**条件求值**建议复用 `static_reflect.py` 中 `_const_compare_result` / `fold_static_reflect_tree`（与 `inlineRange` 内 `_simplify_const_ifs` 同源），在 codegen 侧判断「能否静态求值」；**禁止**为 codegen 单独发明比较语义。

`ctx` 约定：

| `ctx` 值类型 | 在 `if` / `for` 中 |
|--------------|-------------------|
| `int` / `bool` 等 Python 标量 | 参与 CPython 求值与死分支消除 |
| `str` | **C++ 片段或标识符**，插入回退 C++ 或 f-string（不参与 Python 比较求值） |

### 5.3 嵌套

| 嵌套 | 策略 |
|------|------|
| `for` 内含 `if` | 外层可 `exec` 时内层按 §5.1 / §5.2 各自判定；回退时保留 C++ 嵌套块 |
| `if` 内含 `for` | 同上 |
| 相邻 `if` 链 + 独立 `for` | 扫描顺序处理；`elif` 只与前邻 `if` 链合并，不跨块 |

---

## 6. 与 `inlineRange` 的关系

| | `inlineRange`（用户 Python） | `PY2CPP_BEGIN/END`（codegen 模板） |
|--|------------------------------|-------------------------------------|
| 时机 | 译器 pass，用户模块 AST | bootstrap / 注入前，`templates/**` 模板 |
| 循环语义 | CPython `for` + `range` | **同一套**：展开器生成的 Python 里的 `for` |
| 条件语义 | 编译期 `if` 折叠（`inlineRange` 等） | **同一套**：展开器生成的 `if` / `elif` / `else` + `exec` 或 C++ 回退 |
| 发射 | 译器 `visit_*` → C++ AST | `__py2cpp_echo` 收集字符串 → 粘贴进 `.inl` |
| 失败 | 译期 `ValueError` | 模板解析/exec 失败 → 构建期异常 |

二者互补：**用户代码**不走 `PY2CPP_*`；**native 叶子**用本方案减少 f-string 维护成本。

---

## 7. clangd 与 MSVC 分工

| 层 | 内容 |
|----|------|
| **模板源** | 仓库根 `templates/**`（镜像 `generated/runtime/py2cpp/**`）+ 生成 `~macro/<rel>.h` |
| **桩宏**（仅 IDE） | 各模板专属 ``~macro/<rel>.h`` 含 ``PY2CPP_IGNORE`` 等桩 + ``PY2CPP_NAMESPACE``（模块全限定名）+ 可选 ``BEGIN_SCOPE``/``END_SCOPE``；``compile_commands`` 对模板 TU ``-include`` 该头 |
| **MSVC** | 只编译 **展开后** 的 `generated/**/*.inl`，无 `PY2CPP_*` |

可选：`build*.bat` 结束时自动运行 `scripts/gen_compile_commands.py`，将 ``generated/**`` 与 ``templates/**`` 写入根目录 ``compile_commands.json``（模板 TU 强制带 ``-I generated/runtime``）。

**clangd 找不到 `PyBytes` / `py2cpp/...` 头**：

1. **include 根**：`compile_commands` 须含 ``-I generated/runtime``（``templates/`` 不在 ``generated/`` 下时 ``discover_include_dirs`` 单独扫不到；``gen_compile_commands`` 已补）。
2. **模板自身 `#include`（``PY2CPP_IGNORE``）**：凡 ``templates/**/*.inl`` / ``*.h`` 中仅供 clangd 的 ``#include``、类壳、``using`` **必须**包在 ``PY2CPP_IGNORE`` … ``PY2CPP_END`` 内（展开/inject 时整段剔除，**不落盘** ``generated/``）。paste 后上下文已含模块头时 **禁止** 裸写重复 ``#include "py2cpp/…"``。规范见 [§8.3.1](#831-py2cpp_ignore-依赖头clangd-完整性)。
3. **bootstrap**：须已生成 ``generated/runtime/py2cpp/**``；否则先 ``python main.py py2cpp\__init__.py -o generated --no-main``。
4. **`~macro/`**：含任意 ``PY2CPP_*`` 的 ``templates/**/*.inl`` / ``*.h``（不含 ``~macro/``）由 ``gen_compile_commands.py`` 生成 ``templates/~macro/<rel>.h``（镜像 rel，如 ``text/+str.h`` → ``~macro/text/+str.h.h``；内含桩宏；含 ``BEGIN_SCOPE`` 时另生成 scope 宏）。``compile_commands`` 对模板 ``.inl`` / ``.h`` TU ``-include`` 该头。

---

## 8. 目录与路径镜像（定案）

模板 **统一放在仓库根** `templates/`；**相对路径 + 后缀** 与展开写入的 `generated/runtime/py2cpp/**` **一一对应**（镜像 `py2cpp/` 子树，不含 `runtime` 前缀）。

| 模板源 | 展开输出 |
|--------|----------|
| `templates/sql/sqlite.inl` | `generated/runtime/py2cpp/sql/sqlite.inl` |
| `templates/io/io.inl` | `generated/runtime/py2cpp/io/io.inl` |
| `templates/text/str.inl` | `generated/runtime/py2cpp/text/str.inl` |

**规则**：

1. **路径镜像**：`templates/<rel>.inl` ↔ `generated/runtime/py2cpp/<rel>.inl`（`<rel>` 为 `py2cpp/` 下的模块路径，与今日 `paste_cpp_to_inl_target(tr, "sql/sqlite", …)` 的模块键一致）。
2. **`~` 前缀（仅 INCLUDE）**：文件名以 `~` 开头（如 `templates/~helpers.inl`、`templates/sql/~bind.inl`）**不**单独生成对应 `generated/` 文件，**仅供** `PY2CPP_INCLUDE` 在构建期展开并内联进父模板输出。
   - **codegen 完整实现**（``operators.h``、``char.h``、``member_access.h`` 等）：登记在 ``inject_specs.CODEGEN_STANDALONE_TEMPLATE_RELS``（**无** ``+`` 前缀、无 ``py2cpp/<rel>.py``、不参与 mirror/paste）；由 ``layout_emit`` 等 ``expand_template`` 直接写盘。
   - **`+` 前缀（inject 片段）**：文件名须为 **单扩展名** ``+<stem>.inl`` 或 ``+<stem>.h``（排除 ``+stem.inl.h`` 等）。**不**镜像落盘；推断规则：父目录 + ``+`` 后 stem → 模块 rel（``util/+memory.inl`` → ``util/memory``）。分两条路径（详见 [§8.3](#83-注入模板命名与路径定案)）：
   - **`+<stem>.inl`（paste_after）**：``discover_module_paste_after_templates`` → 译期 paste 进对应模块 ``.inl`` 尾部（或 ``PASTE_AFTER_IN_MODULE_MODULES`` 内模块套 namespace 写入）。
   - **`+<stem>.h`（类头 inject）**：``discover_class_header_inject_templates`` → ``PY2CPP_INJECT_CLASS`` 块展开后注入 **同名** ``generated/.../<stem>.h`` 类体尾部。
   - **codegen 专用 ``+*.inl``**：登记在 ``inject_specs.CODEGEN_INJECT_TEMPLATE_RELS``（无 ``py2cpp/<rel>.py``、不参与 paste_after）；由 ``templates/**`` 直接 ``expand_template`` 拼进聚合产物（如 ``operators.inl``）。
   **须**在 ``py2cpp/`` 存在同名模块（codegen 专用条目除外）。paste 段 ``using namespace`` 与 ``BEGIN_SCOPE`` 规则见下。
4. **`-` 前缀（paste_before inject）**：文件名以 `-` 开头（如 `templates/system/-time.inl`）**不**镜像落盘；由 `discover_module_paste_before_templates` 扫描，在译 Python 体 **之前** paste 进模块 `.inl`（与旧 `PASTE_BEFORE_SPECS` + `templates/**` 同语义）。推断规则同 `+`（`system/-time.inl` → `system/time`）。
   **paste 段 C++ 命名**：目标模块 ``.inl`` preamble 有 ``using namespace py2cpp::…``；**类外成员**写 ``Class::method``；**模块级自由函数**须包在 ``PY2CPP_BEGIN_SCOPE`` … ``END_SCOPE`` 内再写短名（否则会变成全局 ``::fn`` 与头文件声明冲突）；跨模块写全限定名或同级段（``window::UIWindow``）。
5. **无前缀**：与 §1 镜像规则相同；`expand_mirror_to_generated` 处理 ``*.inl`` 与 ``*.h``（跳过 ``~macro/``、``~test/``、``~`` / ``+`` / ``-`` 文件名）。**须**有对应 `py2cpp/<rel>.py`。``STDLIB_MIRROR_CODEGEN_RELS``（现行 ``util/tuple``）额外包 guard / 注释壳。
6. **`PY2CPP_INCLUDE(path)`**：`path` 为 **相对当前模板文件所在目录** 的路径（支持 `../`、`./`、同目录文件名）；规范化后须落在 `templates/` 树内。示例：
   - `templates/sql/sqlite.inl` 内 `PY2CPP_INCLUDE("~bind.inl")` → `templates/sql/~bind.inl`
   - 同文件内 `PY2CPP_INCLUDE("../~helpers.inl")` → `templates/~helpers.inl`
   - `templates/io/io.inl` 内 `PY2CPP_INCLUDE("../sql/~bind.inl")` → 跨子目录引用
   - 路径字符串使用正斜杠 `/`（与仓库内路径一致）；`~` 仅表示「INCLUDE-only、不落盘」文件名前缀，与 `..` 无关。
7. **已完成迁移**：叶子 C++ 写在 `templates/**`；由 `expand_py2cpp_template` / `+`·`-` inject 发现 paste 进 `generated/runtime/py2cpp/**`。
8. **类级 ``.inl`` paste（遗留）**：``CLASS_PASTE_SPECS`` / ``CLASS_PASTE_TEMPLATE_SPECS`` 已清空；``io``、``web/socket``、``text/str`` 等均改为 ``+<stem>.inl`` paste_after 或 ``+<stem>.h`` 类头 inject。类名与模块 stem 不一致时仍可用 ``CLASS_PASTE_TEMPLATE_SPECS`` + ``CLASS_PASTE_MODULE_REL`` 在类 emit 时 paste，但模块级尾 paste **优先** ``+`` 命名。

```text
Py2Cpp/                              # 仓库根
  templates/
    ~macro/                           # 生成：``<rel>.h``（桩宏 + 可选 BEGIN_SCOPE）
    ~test/                           # 译器单测：~syntax_showcase.inl（七宏对照）+ ~snippet.inl
    ~helpers.inl                     # 跨模块共享；仅 INCLUDE（如 sql 内 ../~helpers.inl）
    -math.inl                      # paste_before → math.inl（根级 -stem）
    operators.h                  # codegen 完整实现：operators.h 主体
    operators.inl                 # codegen 完整实现：operators.inl + 标量 format
    +io.inl                         # paste_after → io.inl（TextIOWrapper 等）
    system/
      -time.inl                   # paste_before → system/time.inl 首部
      -environ.inl
    util/
      +memory.inl                   # paste_after → util/memory.inl
      StackArray.h                        # mirror codegen
      tuple.h / tuple.inl                  # mirror codegen
    text/
      +bytes.inl                      # paste_after → text/bytes.inl
      +str.h                          # 类头 inject → text/str.h
      +str.inl                        # paste_after → text/str.inl（format / % / fromBuf 等）
    sql/
      +sqlite.inl                     # paste_after → sql/sqlite.inl
    ui/
      +layout.inl                    # paste_after → ui/layout.inl
      +app.inl
      +window.inl                    # 含 Win32 主题
      +widget.inl
    io/
      -file.inl                   # paste_before → io/file.inl（含 path 子模块 C 层）
      io.inl                         # 可 ../sql/~bind.inl
    web/
      +socket.inl                   # paste_after → web/socket.inl（TcpSocket）
  generated/runtime/py2cpp/          # MSVC 只编此处展开结果
    sql/sqlite.inl
  src/codegen/
    expand_py2cpp_template.py        # 扫描 templates/ → 写 generated 镜像（跳过 ~ / + / -）
    inject_template_emit.py          # expanded_inject_template（+*.inl paste）
    template_module_bindings.py      # 镜像 / + 模板 ↔ py2cpp 模块校验
    templates/sql/+sqlite.inl                    # paste_after → sql/sqlite.inl
    brace_style.py                   # 已有：kr_to_allman
```

可选：`build*.bat` 结束时自动运行 `scripts/gen_compile_commands.py`，将 ``generated/**`` 与 ``templates/**`` 写入根目录 ``compile_commands.json``。

`stdlib_inject_emit.py` / `inject_specs.py` / `inject_discovery.py`：`+*.inl` 由发现 + `expanded_inject_template` paste；``util/tuple`` 由 ``expand_mirror_to_generated`` 写 ``templates/util/tuple.{h,inl}``；其它模块同路径镜像或 `-*.inl` paste_before。

### 8.1 `ctx` 命名空间（模板变量）

由 `templates/**` 的 `render_template(ctx)` 传入，例如：

| 键 | 含义 |
|----|------|
| `n` | 循环上界（int 或 C++ 标识符字符串） |
| `buf_size` | 栈缓冲长度字面量 |
| 其他 | `PY2CPP_EVAL` / `PY2CPP_EXEC` 中出现的 Python 名；`PY2CPP_ECHO` 的键名由 `*_gen.py` 填入 |

`ctx` 中值为 `int` / `bool` / `float` 时在 Python 侧可直接参与 `range` 或作为 `PY2CPP_EVAL` 字面量；值为 `str` 时表示 **C++ 标识符或片段**（如 `"params.__len__()"`），经 `PY2CPP_EVAL(n)` 原样插入。**勿**把需 `PyStr("…")` 的 Python 字符串常量放进 `ctx`——应写 `PY2CPP_EVAL("…")` 或在 `*_gen.py` 侧调用 `str_cpp_from_literal`。

### 8.2 非镜像模板：译期 `render`（无单一 `generated/*.inl`）

部分 codegen **不**对应「一个 runtime 模块 → 一个 `generated/runtime/py2cpp/<rel>.inl`」：

| 类别 | 现行 | 定案 |
|------|------|------|
| 按用户 `@delegate` 生成子类 | `delegate_gen.emit_delegate_class` → 用户 `.h` / `.cpp` | 静态骨架迁 `templates/~delegate.inl`（或 `templates/delegate/~base.inl`）；**译器** `translate_file` 内仍调 `render` / `emit_delegate_class` 拼 **当次** 委托类型 |
| 万能头 `minimal.h` | `umbrella_gen.build_py2cpp_umbrella_header(stdlib_modules, …)` | 保留 Python 组装（动态 include 列表 + MSVC 块插入点），**不**强行镜像为单 `.inl` |
| 成员访问宏 | `member_access_cpp` 预处理器 `##` | 保留独立头模板或 `templates/**`；与七宏无关 |
| 异常前向声明 | `exceptions_cpp.emit_exception_forward_decls(tr)` | 译器写流，非 paste `.inl` |

**`~` 非镜像模板**规则：

1. 文件名仍可用 `~` 前缀（如 `templates/~delegate.inl`），表示 **INCLUDE-only / 由展开器或译器消费、不单独落盘** `generated/runtime/py2cpp/…`。
2. **runtime 固定部分**（`PyCallable` / `PyDelegate` 基类模板）：`expand_template("~delegate.inl")` 或 `build_delegate_header` 读模板 → `generated/runtime/py2cpp/delegate.h`（与今日 `stdlib_mirror_codegen` 路径一致）。
3. **译期可变部分**（每个 `@delegate` 的具体 `class X : public PyDelegate<…>`）：**不**进镜像 `.inl`；`translator` 在生成用户模块时调用 `delegate_gen.emit_delegate_class(info, lines=…)`（或等价 `render_delegate_class`），与今日行为一致。
4. 若骨架迁模板后，`delegate_gen.py` 缩为：

```python
def build_delegate_header(...) -> str:
  return wrap_guard(expand_template("~delegate.inl"), guard=..., generated_at=...)
```

`emit_delegate_class` **仍留在** `delegate_gen.py`（或 `emit/delegate_emit.py`），**不**要求作者手写 `PY2CPP_BEGIN(for user_delegates)`——用户委托集合在翻译前未知。

与 §16.7 流水线关系：§16.7 的「写入 `generated/.../<mirror>.inl`」仅适用于 **路径镜像** 模板；`~delegate.inl` 等走 **header 构建** 或 **译器 render**，跳过镜像写盘步骤。

### 8.3 注入模板命名与路径（定案）

**原则**：模板 rel 与目标生成物 **同名同域**——要写进 ``generated/runtime/py2cpp/text/str.h`` 的类体片段用 ``templates/text/+str.h``；要写进 ``text/str.inl`` 的模块级实现用 ``templates/text/+str.inl``；要写进全局 ``operators.inl`` 用根目录 ``templates/+operators.inl``。避免 ``~<功能>_<部件>.inl`` 与目标模块名脱节。

| 形态 | 示例路径 | 镜像到 `generated/`？ | 模块 rel 推断 | 消费方 / 粘贴位置 |
|------|----------|-------------------------|---------------|-------------------|
| 镜像 ``*.inl`` / ``*.h`` | ``text/str.inl`` | 是（整文件） | 路径去后缀 | ``expand_mirror_to_generated`` |
| ``~`` INCLUDE-only | ``sql/~bind.inl`` | 否 | — | ``PY2CPP_INCLUDE`` 父模板内联 |
| ``+<stem>.inl`` paste_after | ``text/+str.inl`` | 否 | ``text/str`` | 模块 ``.inl`` **尾部**（``emit_stdlib_module_paste_after``） |
| ``+<stem>.h`` 类头 inject | ``text/+str.h`` | 否 | ``text/str`` | 模块 ``.h`` 内 **类体尾部**（``class_decl_emit``） |
| ``-stem.inl`` paste_before | ``system/-time.inl`` | 否 | ``system/time`` | 模块 ``.inl`` **首部** |
| codegen 完整 ``*.h`` / ``*.inl`` | ``operators.h`` / ``operators.inl`` | 否 | 无 ``py2cpp`` 模块 | ``CODEGEN_STANDALONE_TEMPLATE_RELS``；``layout_emit.write_primitive_type_headers`` 内 ``expand_template`` |
| 根级 ``+<stem>.inl`` | ``+io.inl`` | 否 | ``io`` | 模块 ``.inl`` **尾部**（``io`` 包根无 ``io/io.py`` 时用根目录 ``+io.inl``） |

**校验**：``validate_template_module_bindings`` 要求 paste_after / 类头 ``+`` 模板对应 ``py2cpp/<module_rel>.py``；``CODEGEN_INJECT_TEMPLATE_RELS`` **豁免** 该校验。

#### `+<stem>.h` 类头 inject（``PY2CPP_INJECT_CLASS``）

1. **文件**：``templates/<域>/+<stem>.h``，与 ``generated/runtime/py2cpp/<域>/<stem>.h`` 同名。
2. **块格式**：``PY2CPP_INJECT_CLASS(CppClass)`` … ``PY2CPP_END``；宏行不落入生成物；块内走完整模板展开（``PY2CPP_TYPE``、``BEGIN``/``END`` 等）。
3. **默认插入点**：目标 ``CppClass`` 类体 **末尾**（各 access 段与 ``emit_special_public`` 之后、闭合 ``};`` 之前）。同文件多个块按出现顺序拼接。
4. **clangd 假壳**（推荐）：

```cpp
PY2CPP_IGNORE
#include "py2cpp/text/str.h"
#include "py2cpp/util/tuple.h"

class PyStr
{
PY2CPP_END

PY2CPP_INJECT_CLASS(PyStr)
  PyStr(PyArray<PyChar>&& data);
PY2CPP_END

PY2CPP_IGNORE
};
PY2CPP_END
```

5. **发现**：``discover_class_header_inject_templates()`` 扫描 ``+<stem>.h``（单点扩展名）；``class_header_inject.py`` 缓存展开结果。

#### `+<stem>.inl` 模块 paste_after

1. **职责**：模块级 **实现** 片段（成员函数、自由函数、``#include`` 等），paste 在译器写完该模块 Python 体之后。
2. **命名空间**：目标 ``.inl`` preamble 常有 ``using namespace py2cpp::…``；**类外成员**写 ``Class::method``；模块级自由函数包 ``PY2CPP_BEGIN_SCOPE`` … ``END_SCOPE``（见 §8 规则 4）。
3. **clangd**：文件首 ``PY2CPP_IGNORE`` 内 ``#include`` 目标模块头及实现体依赖的其它 ``py2cpp/…`` 头（例 ``sql/+sqlite.inl``、``text/+bytes.inl``、``text/+str.inl``）；系统/第三方头（``<stdio.h>``、``sqlite3.h``、Win32 等）若生成物亦需则 **留在 IGNORE 外**。

#### §8.3.1 ``PY2CPP_IGNORE`` 依赖头（clangd 完整性）

**目的**：模板 TU 在 IDE 内可独立通过 clangd 语法检查；展开写盘时不重复 include、不夹带假壳。

| 模板种类 | IGNORE 块内容 | 系统头位置 |
|----------|---------------|------------|
| ``+<stem>.inl`` paste_after | ``#include "py2cpp/<module>.h"`` + 实现用到的其它 ``py2cpp/…`` | 块外（生成物需要时） |
| ``-<stem>.inl`` paste_before | 同上 | 块外 |
| mirror ``<rel>.inl``（``util/tuple`` 等） | ``#include "py2cpp/<rel>.h"``（模板 ``.h`` 尚未 ``#include`` 同名 ``.inl``，无环） | 块外 |
| ``+<stem>.h`` 类头 inject | 模块头 + 可选 ``class CppClass {`` / 闭合 ``};`` 假壳 | 块外或 IGNORE 内（仅 IDE） |
| ``~`` INCLUDE 片段（类体内） | 模块头 + 类壳 / 前向声明 | — |
| codegen 独立片段（``+str_operator_*.inl``） | ``#include`` + ``class PyStr {`` … ``};`` | ``<stdio.h>`` 等可放 IGNORE 内 |

**范例**（``sql/+sqlite.inl``，多依赖头）：

```cpp
PY2CPP_IGNORE
#include "py2cpp/sql/sqlite.h"
#include "py2cpp/text/str.h"
#include "py2cpp/util/list.h"
#include "py2cpp/core/optional.h"
PY2CPP_END

#include <stdint.h>
#include <string.h>
#include <utility>
#include "sqlite3.h"
```

**禁止**：在 IGNORE 外写 ``#include "py2cpp/…"`` 若 paste 后目标 ``.inl`` 已通过模块 ``.h`` / preamble 提供同名类型（会重复 include）。**须**改模板后重跑 ``scripts/gen_compile_commands.py``（或 ``build.bat``）刷新 ``~macro/``。

#### §8.3.2 ``PY2CPP_TYPE`` / ``PY2CPP_EVAL``（clangd 可展开）

**模板写法**：``util`` / ``core`` / ``text`` 下已在 ``_type_registry`` 注册的类**须** ``PY2CPP_TYPE(短名)``（如 ``PY2CPP_TYPE(PyStr)``、``PY2CPP_TYPE(PyIterResult)<Y,R>``）；**禁止**手写 ``py2cpp::core::iter_result::PyIterResult`` 等全限定名（译期 **T24**）。亦接受无参 token ``PY2CPP_TYPE_PyStr``。**动态 C++ 片段**（``ctx_Base``/``ctx_Qualified``/…）一律 ``PY2CPP_ECHO(ctx_*)``；IGNORE 内 ``#define ctx_* …`` 供 clangd，构建期 ``ctx`` 粘贴。**``BEGIN(for)`` 名称列表**循环变量用 ``var_*`` + PascalCase（如 ``var_Name``），IGNORE 内 ``#define var_Name …`` 作 clangd 占位；``PY2CPP_ECHO(var_Name)`` 在循环体内展开。registry 短名自动限定。**禁止** ``PY2CPP_TYPE(PY2CPP_EVAL(name))``（展开器报错，见 [§14](#14-已弃用宏勿使用)）。模板 ``ctx`` 键统一 ``ctx_`` + PascalCase（如 ``ctx_MakeFn``、``ctx_ProtocolName``），与生成 C++ 标识符区分。

**自动桩**（``gen_compile_commands.py`` → ``templates/~macro/<rel>.h``）：

| 机制 | ``~macro`` 桩 | 效果 |
|------|---------------|------|
| ``PY2CPP_TYPE(PyStr)`` | 先 ``#define PY2CPP_TYPE_PyStr …``（每个注册短名），再 ``#define PY2CPP_TYPE(Type) PY2CPP_TYPE_##Type`` | clangd 预处理后得限定 C++ 类型 |
| ``PY2CPP_ECHO(…)`` | ``#define PY2CPP_ECHO(...) __VA_ARGS__`` | IGNORE 内 ``#define ctx_* …``（行内范例或整块空宏）时 clangd 展开；构建期 ``eval(expr)`` → registry 或 ``ctx`` 粘贴 |
| ``PY2CPP_EVAL(expr)`` | ``#define PY2CPP_EVAL(...) __VA_ARGS__`` | 保留括号内文本；构建期展开时字符串/数值常量经 ``ir`` 转为 ``PyStr("…")`` 等字面量 |

范例：

```cpp
PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
#include "py2cpp/text/str.h"
#define ctx_Cls ValueError
#define ctx_Base Exception
PY2CPP_END

PY2CPP_ECHO(ctx_Cls)() = default;
explicit PY2CPP_ECHO(ctx_Cls)(const PY2CPP_TYPE(PyStr)& msg) : PY2CPP_ECHO(ctx_Base)(msg) {}
```

**动态异常 convert ctor**：``explicit Exception(const PY2CPP_ECHO(var_Name)& o);``（IGNORE 内 ``#define var_Name ValueError``；``BEGIN(for var_Name in exception_type_names)``）。

**``PY2CPP_ECHO``**：须在 IGNORE 内为每个 ``ctx_*`` 键提供 ``#define``——行内片段写范例 C++（如 ``#define ctx_Base PyIterator``），**整行/多块**预生成片段（``ctx_PublicMethods``、``ctx_IsInstanceBody``、``ctx_AppendImpls`` 等）写**空宏** ``#define ctx_PublicMethods`` 即可。IGNORE 内 ``#define ctx_*`` 集合须与模板中 ``PY2CPP_ECHO(ctx_*)`` 键集合**一致**（双向，译期 **T25**）；``BEGIN(if ctx_*)`` 展开期布尔键不在此列。见 ``core/~protocol_erase_spec.inl``、``core/~exception_group_dynamic_impl.inl``。

**勿**在 IGNORE 外手写 ``#define ctx_Cls …``（会落盘到 ``generated/``）。

#### codegen 专用 ``+operators.h`` / ``+operators.inl``

1. **无** ``py2cpp/operators.py``；产物为 ``generated/runtime/py2cpp/operators.{h,inl}``，由 ``layout_emit.write_primitive_type_headers`` 展开 ``+operators.h`` / ``+operators.inl``（含 int64/float64、chr/ord、标量 format 等）。
2. 登记 ``CODEGEN_INJECT_TEMPLATE_RELS``；**不**进入 ``discover_module_paste_after_templates``。
3. ``module_rel_from_template_rel("+operators.inl")`` 返回 ``None``（宏头 **无** ``PY2CPP_NAMESPACE``）。

#### 迁移范例（``text/str``）

| 旧路径 | 新路径 | 说明 |
|--------|--------|------|
| ``~class_header/str_format_header.inl`` 等 | ``text/+str.h`` | 声明：`format`` / ``__mod__`` / ``PyArray&&`` 构造等 |
| ``text/~str_format_runtime.inl`` | ``text/+str.inl`` | 实现：format 替换、``%``、标量构造 |
| ``text/~str_array_by_value.inl`` | （同上合并） | ``PyStr(PyArray<PyChar>&&`` |
| ``text/~str_span.inl`` | （同上合并） | ``fromBuf`` |
| ``~operators/scalar_format.inl`` | ``+operators.inl``（format 段） | 与 divmod/pow/repr 等合并于同一 ``+operators.inl`` |
| ``io/~text_io_wrapper.inl`` | ``+io.inl`` | ``TextIOWrapper`` 等写入 ``io.inl`` 尾部 |
| ``web/~socket_tcp.inl`` | ``web/+socket.inl`` | ``TcpSocket`` 写入 ``web/socket.inl`` 尾部 |
| ``exceptions_cpp`` ``Exception`` / convert ctor | ``core/+exceptions.h`` + ``~exception_convert_ctor_decls.inl`` | 类头 inject；声明循环 INCLUDE |
| ``exceptions_cpp`` convert ctor impl | ``core/+exceptions.inl`` | paste_after → ``core/exceptions.inl`` |
| ``weak/~ref_class.inl`` | 内联 ``core/refcount.h`` | ``PyWeakRef`` 不再单独 ``~`` 文件 |

类级 ``CLASS_PASTE_SPECS`` / ``CLASS_PASTE_TEMPLATE_SPECS`` **已清空**；``text/str``、``io``、``web/socket`` 统一用 ``+`` 命名。

#### ``~macro`` 宏头（clangd）

- 凡 ``templates/**/*.inl`` / ``*.h``（不含 ``~macro/``）且含 ``PY2CPP_*``，由 ``scripts/gen_compile_commands.py`` 生成 ``templates/~macro/<rel>.h``（镜像 rel：``text/+str.h`` → ``~macro/text/+str.h.h``）。
- ``compile_commands`` 对模板 ``.inl`` / ``.h`` TU ``-include`` 该头；桩含 ``PY2CPP_INJECT_CLASS``、``PY2CPP_IGNORE`` 等。
- **勿手改** ``~macro/`` 下文件；改模板后重跑 ``gen_compile_commands.py`` 或 ``build.bat``。

---

## 9. 展开示例

### 9.1 常量界（完全展开）

**输入**

```cpp
PY2CPP_BEGIN( for i in range(3) )
  buf[PY2CPP_EVAL(i)] = PY2CPP_EVAL(i + 1);
PY2CPP_END
```

**输出**

```cpp
buf[0] = 1;
buf[1] = 2;
buf[2] = 3;
```

### 9.2 运行时界（回退 C++ 循环）

**输入**（`ctx = {"n": "n"}`，`n` 为 C++ 变量名）

```cpp
PY2CPP_BEGIN( for i in range(0, n) )
  sqlite3_bind_int(stmt, PY2CPP_EVAL(i + 1), PY2CPP_EVAL(vals[i]));
PY2CPP_END
```

**输出（示意）**

```cpp
int i = 0;
while ((i < n))
{
  sqlite3_bind_int(stmt, (i + 1), vals[i]);
  i = (i + 1);
}
```

（具体回退格式以 `expand_py2cpp_template.py` 与 `kr_to_allman` 实现为准。）

### 9.3 编译期 `if`（死分支消除）

**输入**（`ctx = {"typ": 1, "SQLITE_INTEGER": 1, "SQLITE_TEXT": 3, ...}`）

```cpp
PY2CPP_BEGIN( if typ == SQLITE_INTEGER )
  bind_int();
PY2CPP_END
PY2CPP_BEGIN( elif typ == SQLITE_TEXT )
  bind_text();
PY2CPP_END
PY2CPP_BEGIN( else )
  bind_null();
PY2CPP_END
```

**输出**（仅命中第一分支）

```cpp
bind_int();
```

### 9.4 运行时 `if`（回退 C++ 链）

**输入**（`ctx` 中 `typ` 为 C++ 变量名 `"typ"`）

```cpp
PY2CPP_BEGIN( if typ == SQLITE_INTEGER )
  sqlite3_bind_int(stmt, PY2CPP_EVAL(idx), PY2CPP_EVAL(val));
PY2CPP_END
PY2CPP_BEGIN( elif typ == SQLITE_TEXT )
  sqlite3_bind_text(stmt, PY2CPP_EVAL(idx), PY2CPP_EVAL(txt), -1, SQLITE_TRANSIENT);
PY2CPP_END
```

**输出（示意）**

```cpp
if ((typ == SQLITE_INTEGER))
{
  sqlite3_bind_int(stmt, idx, val);
}
else if ((typ == SQLITE_TEXT))
{
  sqlite3_bind_text(stmt, idx, txt, -1, SQLITE_TRANSIENT);
}
```

### 9.5 `if` 内嵌 `for`（编译期）

**输入**

```cpp
PY2CPP_BEGIN( if n > 0 )
PY2CPP_BEGIN( for i in range(2) )
  buf[PY2CPP_EVAL(i)] = PY2CPP_EVAL(i + 1);
PY2CPP_END
PY2CPP_END
```

**输出**（`ctx = {"n": 3}`）

```cpp
buf[0] = 1;
buf[1] = 2;
```

（`ctx = {"n": 0}` 时输出为空。）

---

## 10. 安全与约束

| 项 | 约定 |
|----|------|
| **执行环境** | 仅构建期、仅信任源树模板；`exec` 使用受限 `__builtins__`（无 `open`/`import` 等） |
| **嵌套** | `BEGIN` 可嵌套；`if` / `elif` / `else` 仅允许链式相邻合并，禁止孤立 `elif` / `else` |
| **错误** | `ast.parse` / `exec` 失败 → 带模板文件路径与行号的构建错误 |
| **禁止** | 手改 `generated/` 绕过展开；在业务 `py2cpp/` 或用户测试中使用 `PY2CPP_*` |

---

## 11. 测试计划

| 层 | 路径 | 内容 |
|----|------|------|
| 译器单测 | `src/tests/test_expand_py2cpp_template.py` | `for`/`if` 链、`ECHO`/`Exec`/`EVAL` 分工、`BEGIN(def)` |
| 译期规范 | `src/tests/test_template_conventions.py` | bootstrap 全树 T* 规则（见 §11.1） |
| 集成 | 试点 `templates/sql/sqlite.inl` → `generated/.../sql/sqlite.inl` + `build.bat sql/test_sqlite` | 展开后 SQLite 行为与改前一致 |

### 11.1 译期 T* 规则表（bootstrap / `include_stdlib`）

**入口**：`python main.py py2cpp\__init__.py -o generated --no-main` 时，`check_template_conventions(strict=…)` 扫描 `templates/**`（含 `~test/`；跳过 `~macro/`）。`--no-strict` 关闭；T6 孤立 `~` 文件为 **stderr 警告** 不阻断。

**实现**：`src/codegen/template_conventions.py` + `template_scan.py`；单文件展开仍保留 `expand_template()` 即时断言。

| ID | 类别 | 规则 |
|----|------|------|
| **T1** | 命名 | 镜像 `*.inl`/`*.h` 文件名不得以 `~` / `+` / `-` 开头 |
| **T2** | 命名 | inject 须为单扩展名 `+<stem>.inl` 或 `+<stem>.h` |
| **T3** | 命名 | paste_before 须为 `-<stem>.inl`（单扩展名） |
| **T4** | 绑定 | mirror / `+` / `-` 模板（非 codegen 专用）须对应 `py2cpp/<module_rel>.py` |
| **T6** | 绑定 | 孤立 `~` 片段（无 hook / INCLUDE 引用 / module_rel）→ **warning** |
| **T8** | INCLUDE | 路径用 `/`、落在 `templates/` 内、目标存在 |
| **T9** | 绑定 | 同一模块不得有两个 paste_after `+*.inl` |
| **T10** | 宏 | §14 弃用宏（含 `PY2CPP_DYNAMIC_TYPE`、`PY2CPP_INLINE_ECHO` 等） |
| **T11** | 结构 | `PY2CPP_BEGIN`/`END`、`IGNORE`、`INJECT_CLASS` 配对 |
| **T12** | 结构 | 禁止孤立 `elif` / `else` |
| **T13** | 结构 | `PY2CPP_BEGIN_SCOPE`/`END_SCOPE` 配对 |
| **T14** | 命名 | `BEGIN(def fn_PascalCase(in_PascalCase…))` |
| **T16** | 命名 | `BEGIN(for var_PascalCase in …)` |
| **T17** | 宏 | 禁止 `PY2CPP_TYPE(PY2CPP_EVAL(…))` |
| **T18** | 容器 | 禁止 STL 容器头 / `std::vector<` 等 |
| **T19** | inject | `+/-` 模板：`#include "py2cpp/…"` 须在 `PY2CPP_IGNORE` 内 |
| **T20** | inject | `+/-` 模板：`#define ctx_*` 须在 `PY2CPP_IGNORE` 内 |
| **T21** | 宏 | paste/镜像模板禁止 `PY2CPP_NAMESPACE`（仅 `~macro` 桩） |
| **T22** | inject | `+<stem>.h`：须 `IGNORE` 内 `class C {` … `PY2CPP_END` → `INJECT_CLASS(C)`（可重复同名）→ `IGNORE` + `};`；文件首行 `PY2CPP_IGNORE` 且含 `namespace py2cpp` |
| **T25** | 命名 | `ctx_*` 键须 `ctx_` + PascalCase；IGNORE `#define ctx_*` 与 `PY2CPP_ECHO(ctx_*)` 键集合**双向一致**（`BEGIN(if ctx_*)` 除外）；`*_gen.py` 传入的 `ctx` 字典键同名 |
| **T23** | 包壳 | **禁止**模板内 `#pragma once` 与手写 include guard（`#ifndef`/`#define …_H`/`#endif // …`）；整文件 guard 由 `finalize_codegen_file_text` / `expand_whole_file_template` 在 Python 侧包壳 |
| **T24** | 类型 | **禁止**手写 `py2cpp::core|util|text::…::TypeName` 全限定类型；须 `PY2CPP_TYPE(短名)`（`using namespace py2cpp::core::exceptions` 等 **namespace** 行除外；`concur`/`io` 等其它域仍可用全限定名） |

**`_type_registry` 扩展**（`expand_py2cpp_template._STD_TYPES`）：除 `PyStr`/`PyList`/异常等外，模板常用类型含 `PyArray`/`PyArray2D`/`PyArray3D`、`PyIterResult`、`PyNone`、`PyCoroutine`、`PyOptional` 等；未注册短名在展开期仍会报错。

---

## 12. 实施顺序（建议）

1. ~~`expand_py2cpp_template.py` + 单测~~（已落地）
2. ~~``~macro/<rel>.h`` + 模板目录 clangd 配置~~（已落地）
3. ~~`templates/sql/+sqlite.inl` 等试点~~（`*_cpp.py` 已全部迁出）
4. 运行时界 / 运行时条件回退 + 复用 `inlineRange` / `static_reflect` 求值工具（按需继续加强）
5. 新叶子一律写 `templates/**`，勿再引入 `src/codegen/*_cpp.py`

---

## 13. 暂不实现

- 在 **用户可见** Python 代码或 `py2cpp/` 标准库中使用 `PY2CPP_*`。
- 用本方案替代译器内 `inlineRange` pass。
- 模板内嵌套任意 C++ 模板元编程（仅文本级展开 + C++11 输出）。
- `match` / `while` / `try` 作为 `PY2CPP_BEGIN` 头（首版仅 `for` + `if` / `elif` / `else`）。

---

## 14. 已弃用宏（勿使用）

下列符号曾在设计稿或 Jinja 对照表中出现，**不实现、展开器不识别、文档与模板勿引用**。

| 弃用 | 替代 |
|------|------|
| `#include <vector>` / `<map>` 等 STL 容器头；`std::vector` / `std::map` 等 | **禁止**（`expand_template` 报错）；用 `PyList` / `PyDict` 或定长数组 |
| `PY2CPP_TYPE(PY2CPP_EVAL(…))` | **禁止**；动态 C++ 片段用 IGNORE `#define ctx_*` + `PY2CPP_ECHO(ctx_*)` |
| `PY2CPP_DYNAMIC_TYPE(base, name)` | **已删除**；用 IGNORE `#define ctx_*` + `PY2CPP_ECHO(ctx_*)` |
| `PY2CPP_INLINE_ECHO(base, name)` | **已删除**；用 IGNORE `#define ctx_*` + `PY2CPP_ECHO(ctx_*)` |
| `PY2CPP_STMT` | 独立一行 `PY2CPP_EXEC(…)`；或 `BEGIN(def)` 体内任意 Python |
| `PY2CPP_SET` | `PY2CPP_EXEC(x = …)` 或 `PY2CPP_EVAL(…)` |
| `PY2CPP_SYM` | `PY2CPP_TYPE(…)` |
| `$KEY$` / `$STR_PYSTR$` / `$INDEX_ERROR_THROW$` 等 | `PY2CPP_TYPE(…)` 或模板内全限定 C++；抛错写 `throw PY2CPP_TYPE(IndexError)();` |
| `PY2CPP_MACRO` / `PY2CPP_CALL` | `BEGIN(def …)` + `Exec(helper(…))` |
| `PY2CPP_RAW` / `BEGIN(raw)` | 无宏纯 C++ 行；预生成大块用 `PY2CPP_ECHO(key)` |
| `loop.index` / `loop.last` 等 | `EVAL(i + 1)`；`BEGIN(def)` 内 Python `for` |
| `PY2CPP_EMIT`（草案） | 模板内 **直接写 C++**（与现行 `io/-file.inl`、`text/+str.inl` 一致） |
| `PY2CPP_FILE_META` | 整文件 guard/注释由 ``expand_whole_file_template`` / ``finalize_codegen_file_text`` 在 Python 侧包壳 |
| `PY2CPP_EMIT_CTX` | `PY2CPP_ECHO(key)` |

Jinja2 的 `extends` / `block` / `autoescape`、FILTER 链等 **不做**。片段复用：`INCLUDE` + `BEGIN(def)`；类型名：`PY2CPP_TYPE`。

---

## 15. 具体示例（七宏 · 对照仓库现行模板）

以下示例采用 [§16 七宏定案](#16-七宏定案)：**仅** `BEGIN` / `END`、`EVAL`、`Exec`、`ECHO`、`INCLUDE`、`TYPE`。模板内 **直接写 C++**（`copyToSpan`、`__getitem__` 等），勿用已弃用的 `EMIT` / `STMT`（见 [§14](#14-已弃用宏勿使用)）。

每条说明三块：**模板源**（`templates/**`，clangd 可读）、**等价手写 Python**（`exec` 路径，展开器生成）、**展开后 C++**（`generated/runtime/py2cpp/**`）。

### 15.1 入门：`BEGIN` + `EVAL`（`test/sql/test_sqlite.py` 草图）

**模板** `templates/misc/demo.inl`：

```cpp
PY2CPP_BEGIN( for i in range(10) )
cout << "i: " << PY2CPP_EVAL(i) << endl;
PY2CPP_END
```

**等价手写 Python**（作者不必写，展开器生成）：

```python
for i in range(10):
  __py2cpp_echo(f'cout << "i: " << {i} << endl;')
```

**展开后 C++**：

```cpp
cout << "i: " << 0 << endl;
cout << "i: " << 1 << endl;
// … 直至 9
```

---

### 15.2 `_sql_bind_int_list`：运行时界 → C++ `while` 回退

现行 `templates/sql/+sqlite.inl` 用手写 `while`：

```cpp
static void _sql_bind_int_list(sqlite3_stmt* stmt, const PyList<PyInt>& params) {
  int n = params.__len__();
  int i = 0;
  while ((i < n)) {
    int v = params.__getitem__(i);
    if (sqlite3_bind_int(stmt, i + 1, v) != SQLITE_OK) {
      _sql_throw_operational();
    }
    i = (i + 1);
  }
}
```

**模板写法**（`n` 在 `ctx` 中为 C++ 标识符 `"n"`，不 `exec` `range(n)`）：

```cpp
static void _sql_bind_int_list(sqlite3_stmt* stmt, const PY2CPP_TYPE(PyList)<PY2CPP_TYPE(PyInt)>& params) {
  int n = params.__len__();
  PY2CPP_BEGIN( for i in range(0, n) )
  if (sqlite3_bind_int(stmt, PY2CPP_EVAL(i + 1), params.__getitem__(i)) != SQLITE_OK) {
    _sql_throw_operational();
  }
  PY2CPP_END
}
```

说明：`EVAL(i+1)` 在回退路径为 C++ `(i + 1)`；`params.__getitem__(i)` 为模板内 **直接 C++**（与 `templates/sql/+sqlite.inl` 一致）。

---

### 15.3 `_sql_pystr_to_cbuf`：编译期小界完全展开

现行 `while ((i < n))` 拷贝 `PyChar` → `char`（`templates/sql/+sqlite.inl` 同类逻辑）。

**模板**（`n` 为运行时变量 → **回退** `while`）：

```cpp
static void _sql_pystr_to_cbuf(const PY2CPP_TYPE(PyStr)& s, char* buf, int cap) {
  int n = s.__len__();
  if (n >= cap) {
    n = cap - 1;
  }
  PY2CPP_BEGIN( for i in range(0, n) )
  buf[PY2CPP_EVAL(i)] = (char)(unsigned char)pychar_to_byte(s.__getitem__(i));
  PY2CPP_END
  buf[n] = '\0';
}
```

若桩函数在 `ctx` 中固定 `n = 3`（编译期界）：

```cpp
PY2CPP_BEGIN( for i in range(3) )
buf[PY2CPP_EVAL(i)] = (char)(unsigned char)pychar_to_byte(s.__getitem__(i));
PY2CPP_END
```

**展开后**：

```cpp
buf[0] = (char)(unsigned char)pychar_to_byte(s.__getitem__(0));
buf[1] = (char)(unsigned char)pychar_to_byte(s.__getitem__(1));
buf[2] = (char)(unsigned char)pychar_to_byte(s.__getitem__(2));
```

---

### 15.4 SQLite 列类型分派：`BEGIN(if/elif/else)` 链

**常量**（`templates/~codegen/constants.inl`，仅 `INCLUDE`、不落盘）：

```cpp
PY2CPP_EXEC(SQLITE_INTEGER = 1)
PY2CPP_EXEC(SQLITE_TEXT = 3)
PY2CPP_EXEC(SQLITE_BLOB = 4)
PY2CPP_EXEC(SQLITE_TRANSIENT = "SQLITE_TRANSIENT")
```

**模板**（`templates/sql/~bind_by_type.inl` 或主 `sqlite.inl` 内联）：

```cpp
PY2CPP_INCLUDE("../~codegen/constants.inl")

PY2CPP_BEGIN( if col_type == SQLITE_INTEGER )
  sqlite3_bind_int(stmt, PY2CPP_EVAL(idx), PY2CPP_EVAL(val));
PY2CPP_END
PY2CPP_BEGIN( elif col_type == SQLITE_TEXT )
  sqlite3_bind_text(stmt, PY2CPP_EVAL(idx), PY2CPP_EVAL(txt), -1, SQLITE_TRANSIENT);
PY2CPP_END
PY2CPP_BEGIN( elif col_type == SQLITE_BLOB )
  sqlite3_bind_blob(stmt, PY2CPP_EVAL(idx), PY2CPP_EVAL(blob), PY2CPP_EVAL(blob_len), SQLITE_TRANSIENT);
PY2CPP_END
PY2CPP_BEGIN( else )
  sqlite3_bind_null(stmt, PY2CPP_EVAL(idx));
PY2CPP_END
```

**构建期 `ctx`**（仅影响 `col_type` 是否可静态求值）：

```python
ctx = {
  "idx": "idx",
  "val": "val",
  "txt": "txt",
  "blob": "blob",
  "blob_len": "blob_len",
  "col_type": 1,  # 编译期：只展开 INTEGER 分支
}
```

**展开后**（`col_type == 1`）：

```cpp
sqlite3_bind_int(stmt, idx, val);
```

**运行时回退**（`ctx["col_type"] = "col_type"`）：

```cpp
if ((col_type == SQLITE_INTEGER))
{
  sqlite3_bind_int(stmt, idx, val);
}
else if ((col_type == SQLITE_TEXT))
{
  sqlite3_bind_text(stmt, idx, txt, -1, SQLITE_TRANSIENT);
}
else if ((col_type == SQLITE_BLOB))
{
  sqlite3_bind_blob(stmt, idx, blob, blob_len, SQLITE_TRANSIENT);
}
else
{
  sqlite3_bind_null(stmt, idx);
}
```

---

### 15.5 末元素逗号 / `bind` 序号：`EVAL` 或 `BEGIN(def)` + `Exec`

七宏**无** `loop.last` / `loop.index`。等价写法：

**A. 编译期 `range(k)` + `EVAL` 表达式**（初始化列表逗号，`ctx` 提供 `OPS = ["A","B","C","D"]`）：

```cpp
static const char _sql_select_hdr[] = {
PY2CPP_BEGIN( for i in range(4) )
  PY2CPP_EVAL(OPS[i])PY2CPP_EVAL("" if i == 3 else ",")
PY2CPP_END
};
```

**等价 Python**：

```python
for i in range(4):
  __py2cpp_echo(f'{OPS[i]}{"" if i == 3 else ","}')
```

**展开后**：

```cpp
static const char _sql_select_hdr[] = {
  'A', 'B', 'C', 'D'
};
```

**B. `sqlite3_bind` 1-based 序号**（`EVAL(i + 1)`，无需 `loop.index`）：

```cpp
PY2CPP_BEGIN( for i in range(0, n) )
  if (sqlite3_bind_int(stmt, PY2CPP_EVAL(i + 1), vals.__getitem__(i)) != SQLITE_OK) {
    _sql_throw_operational();
  }
PY2CPP_END
```

**C. 复杂逗号/分支** → `BEGIN(def)` 注册 helper，`Exec` 调用（见 §15.9 / §16.3）。

---

### 15.6 `PY2CPP_TYPE` 限定类型名

``templates/+operators.inl`` 示例：

```cpp
inline PY2CPP_TYPE(PyStr) repr(PyInt v) {
  char buf[32];
  snprintf(buf, sizeof(buf), "%d", (int)v);
  return PY2CPP_TYPE(PyStr)(buf);
}
```

展开后 `PY2CPP_TYPE(PyStr)` → `py2cpp::text::str::PyStr`（见 `expand_py2cpp_template._type_registry` / `stdlib_layout.cpp_stdlib_class`）。

抛错只写 C++ 侧语句，**禁止**把整句塞进 `TYPE`：

```cpp
throw PY2CPP_TYPE(IndexError)();
```

→ `throw py2cpp::core::exceptions::IndexError();`（`throw` / `()` / `;` 为模板 C++，不经 `EVAL`）。

---

### 15.7 `io/-file.inl`：`copyToSpan` 直接写 C++

现行 `templates/io/-file.inl` 在模板内 **直接写 C++**（勿用已弃用草案 `PY2CPP_EMIT`）：

```cpp
void py_open(const PY2CPP_TYPE(PyStr)& path, const PY2CPP_TYPE(PyStr)& mode) {
  char pbuf[4096];
  char mbuf[16];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  mode.copyToSpan(PySpan<PyByte>((PyByte*)mbuf, (PyInt)sizeof(mbuf), 1));
  FILE* fp = fopen(pbuf, mbuf);
  // …
}
```

循环/分派仍可用 `BEGIN(for)` + `EVAL`；仅 **栈缓冲 + C API** 类叶子保持纯 C++ 可读性。

---

### 15.8 大块静态 C++：无宏纯文本

`SQLITE_IMPL` 中大量方法体无插值；不含 `PY2CPP_*` 的行即为纯 C++，clangd 直接解析（[§16.6](#166-静态-c-大块)）。

```cpp
void PySqliteConnection::commit() {
  if ((_closed) || (_db == 0)) {
    _sql_throw_operational();
  }
  sqlite3* db = _sql_db_ptr(_db);
  if (sqlite3_get_autocommit(db)) {
    return;
  }
  char* err = nullptr;
  if (sqlite3_exec(db, "COMMIT", nullptr, nullptr, &err) != SQLITE_OK) {
    if (err) {
      sqlite3_free(err);
    }
    _sql_throw_operational();
  }
}
```

字面量 `{{` / `}}`（初始化列表、lambda 等）**照常书写**；展开器只识别 `PY2CPP_*`，不对无宏行做 f-string 转义。需要循环/分派的位置单独用 `BEGIN(for)` / `BEGIN(if)` 插入。

---

### 15.9 `PY2CPP_INCLUDE`：共享片段与 `BEGIN(def)`

`templates/sql/~pystr_to_cbuf.inl`（`~` → **不**写入 `generated/`，仅内联）：

```cpp
static void _sql_pystr_to_cbuf(const PY2CPP_TYPE(PyStr)& s, char* buf, int cap) {
  int n = s.__len__();
  if (n >= cap) {
    n = cap - 1;
  }
  PY2CPP_BEGIN( for i in range(0, n) )
  buf[PY2CPP_EVAL(i)] = (char)(unsigned char)pychar_to_byte(s.__getitem__(i));
  PY2CPP_END
  buf[n] = '\0';
}
```

`templates/sql/~bind.inl`（helper，不向 `generated/` 单独落盘）：

```cpp
PY2CPP_BEGIN( def fn_BindInt(in_Stmt, in_Idx, in_V) )
  if (sqlite3_bind_int(in_Stmt, PY2CPP_EVAL(in_Idx), PY2CPP_EVAL(in_V)) != SQLITE_OK) {
    PY2CPP_EXEC(_sql_throw_operational())
  }
PY2CPP_END

PY2CPP_BEGIN( def fn_BindIntList(in_Stmt, in_Vals, in_N) )
  PY2CPP_BEGIN( for i in range(0, in_N) )
    PY2CPP_EXEC(fn_BindInt(in_Stmt, i + 1, in_Vals[i]))
  PY2CPP_END
PY2CPP_END
```

主模板 `templates/sql/sqlite.inl`：

```cpp
PY2CPP_INCLUDE("../~codegen/constants.inl")
PY2CPP_INCLUDE("~bind.inl")
PY2CPP_INCLUDE("~pystr_to_cbuf.inl")

static void _sql_bind_int_list(sqlite3_stmt* stmt, const PY2CPP_TYPE(PyList)<PY2CPP_TYPE(PyInt)>& params) {
  int n = params.__len__();
  PY2CPP_EXEC(fn_BindIntList(stmt, params, n))
}
```

`INCLUDE` 路径**相对当前模板文件目录**（`../`、`./`）；跨目录示例：`PY2CPP_INCLUDE("../~helpers.inl")`。

---

### 15.10 嵌套：`if` 包 `for`（编译期界）

**模板**：

```cpp
PY2CPP_BEGIN( if cap > 1 )
PY2CPP_BEGIN( for i in range(3) )
  buf[PY2CPP_EVAL(i)] = PY2CPP_EVAL(i + 1);
PY2CPP_END
PY2CPP_END
```

**`ctx = {"cap": 8}`** → 展开三节赋值；**`ctx = {"cap": 0}`** → 空输出。

**运行时回退**（`cap` 为 C++ 变量名）：

```cpp
if ((cap > 1))
{
  int i = 0;
  while ((i < 3))
  {
    buf[i] = (i + 1);
    i = (i + 1);
  }
}
```

---

### 15.11 `templates/sql/+sqlite.inl` 侧组装

```python
from src.codegen.expand_py2cpp_template import expand_template
from src.codegen.brace_style import kr_to_allman

def render_sqlite_impl() -> str:
  return kr_to_allman(
    expand_template(
      "sql/sqlite.inl",
      ctx={
        "col_type": "col_type",  # 或编译期字面量用于静态消除
      },
    )
  )

SQLITE_IMPL = render_sqlite_impl()
```

迁完后可改为 `expand_all_templates()` 直接写 `generated/runtime/py2cpp/sql/sqlite.inl`；`templates/sql/+sqlite.inl` 仅保留 inject 注册与 `_INCLUDES` 等外壳。

---

### 15.12 对照总表（七宏）

| 场景 | 现行 `templates/**` | 七宏 |
|------|-----------------|------|
| 固定次循环 | `for _ in range(k): lines.append(f'…')` | `BEGIN(for)` + `EVAL` |
| 运行时 `n` | 手写 `while ((i < n))` | `BEGIN(for i in range(0,n))` → 自动回退 |
| 类型分派 | 手写 `if/else` 或 Python 生成 | `BEGIN(if/elif/else)` 链 |
| 绑定序号 `i+1` | f-string `{i+1}` | `EVAL(i+1)` |
| 末元素无逗号 | `if i != n-1: emit comma` | `EVAL("" if i == k-1 else ",")` 或 `BEGIN(def)` + `Exec` |
| 限定 C++ 类型名 | f-string 拼限定名 | `PY2CPP_TYPE(…)` |
| 构建期常量 | `ctx` 或 Python 字面量 | `INCLUDE` + `Exec(SQLITE_INTEGER = 1)` |
| PyStr→缓冲 | f-string 嵌 helper | 模板内直接 `copyToSpan(PySpan<…>(…))` |
| 预生成大块 | `*_gen.py` 拼串 | `PY2CPP_ECHO(key)` + `expand_template(ctx)` |
| 无插值大段 | `kr_to_allman("""…""")` | **纯 C++ 行**（无任何 `PY2CPP_*`） |
| 跨模块复用 | Python 拼 `_STATIC_HELPERS` | `INCLUDE` + `BEGIN(def)` + `Exec` |
| 抛错 | f-string `throw …` | `throw PY2CPP_TYPE(IndexError)();` |

宏分工速查见 [§16.2 `EVAL` vs `ECHO` vs `Exec`](#162-分工eval-vs-echo-vs-exec)。

---

## 16. 七宏定案

构建期模板作者向宏 **固定为 7 个**（见文首）；[§14](#14-已弃用宏勿使用) 所列 **不实现**。实现见 `src/codegen/expand_py2cpp_template.py`。

### 16.1 七宏一览

| 宏 | 角色 |
|----|------|
| `PY2CPP_BEGIN( … )` / `PY2CPP_END` | 控制流与 `def` helper：`for` / `if` / `elif` / `else` / `def` |
| `PY2CPP_EVAL(expr)` | C++ 行内 **CPython 表达式**；构建期常量 → `ir` 字面量；否则 f-string 或 C++ 片段 |
| `PY2CPP_EXEC(stmt)` | **独立一行** CPython 语句或 `def` 调用；构建期 `exec` / `eval` |
| `PY2CPP_ECHO(expr)` | 构建期 CPython 表达式 → `str` / `list[str]` 原样粘贴（整行、多块、行内；registry 短名 → 限定类型） |
| `PY2CPP_INCLUDE(path)` | 相对路径展开子模板；`~` 仅内联 |
| `PY2CPP_TYPE(Name)` | 短名 → 限定 C++ 类型（``_type_registry``） |

### 16.2 分工：`EVAL` vs `ECHO` vs `Exec`

| | `PY2CPP_EVAL` | `PY2CPP_ECHO` | `PY2CPP_EXEC` |
|--|---------------|---------------|---------------|
| 输入 | CPython **表达式**（字面量或 `BEGIN` 体内循环/算术） | CPython **表达式**（求值为待粘贴 C++ 文本） | CPython **语句** 或 `def` 调用 |
| 机制 | 构建期常量 → `ir` 字面量；`BEGIN` 体内 → f-string | `eval(expr)` → `str` / `list[str]` 原样替换；registry 短名限定 | `exec` 命名空间执行 |
| 典型位置 | `"msg"`、`42`；`BEGIN(for)` 内 `{i}`、`{macro}` | `ctx_PublicMethods`、`ctx_Base`、`ctx_TplArgs`；名称列表循环 ``var_Name`` + ``ECHO(var_Name)`` | 独立一行（常量赋值、`fn_BindIntList(…)`） |
| 模板内 C++ API | 不适用——**直接写** `copyToSpan(…)`、`__getitem__(i)` | 不适用 | 不适用 |

**记忆口诀**：**EVAL** 算；**ECHO** 贴；**Exec** 跑；**叶子 C++** 无宏直写。

### 16.3 复用：`BEGIN(def)` + `Exec`

替代已弃用 `PY2CPP_MACRO` / `CALL`（§14）。`BEGIN(def fn_PascalName(in_…))` 注册构建期 helper：**helper 名** ``fn_`` + PascalCase；**形参** ``in_`` + PascalCase（如 ``fn_EmitLines(in_Items)``、``fn_EmitMsvcUndefMacros(in_Macros)``）。不向 `generated/` 发射 C++；`Exec(fn_BindIntList(...))` 在构建期内联 helper 体。完整示例见 [§15.9](#159-py2cpp_include共享片段与-begindef)。

### 16.4 常量与类型

`INCLUDE` + `Exec(SQLITE_INTEGER = 1)` 集中常量；`PY2CPP_TYPE` 只映射类型名。抛错：`throw PY2CPP_TYPE(IndexError)();`。

### 16.5 `BEGIN` 支持的语句头

`for` / `if` / `elif` / `else` / `def`；不做 `while` / `match` / `try`（§13）。

### 16.6 静态 C++ 大块

无 `EVAL` / `Exec` / `ECHO` / `BEGIN` 的行即为纯 C++。预生成大块：`PY2CPP_ECHO(key)`。

### 16.7 展开流水线

```text
INCLUDE 树 → 收集 BEGIN(def) → Exec 注入命名空间
  → 展开主模板（BEGIN + EVAL + Exec）→ ECHO 插入 ctx 片段
  → PY2CPP_TYPE → kr_to_allman → 写 generated/
```

### 16.8 三类 codegen 落盘

| 类 | 示例 | 输出 |
|----|------|------|
| A. 镜像 `.inl` | `sql/sqlite.inl` | `generated/runtime/py2cpp/...` |
| B. `+` inject | `util/+memory.inl` | 模块 `.inl` paste |
| C. `~` + `ECHO` | `minimal.h`、`~delegate_class.inl` | 固定头 / 内联片段 |
| D. 译期 render | `delegate_gen.emit_delegate_class` | 用户 `.h` / `.cpp` |

