# 函数闭包、`global` / `nonlocal` 设计定案

本文档为 **Py2Cpp 译器实现规格**（定案，待实现）。用户可见摘要见 [参考手册 §6.6](./参考手册.md#66-global--nonlocal--嵌套-def-闭包)；写法约束见 [编码规范 §7.8](./编码规范.md#78-嵌套-def-闭包与-global--nonlocal)。

---

## 1. 目标与边界

### 1.1 目标

| 能力 | 说明 |
|------|------|
| **`global`** | 在函数/方法内声明后，读写绑定**已有模块级**注解变量 |
| **`nonlocal`** | 读写绑定**最近 enclosing 函数**作用域中的同名局部（非模块、非当前层新建） |
| **嵌套 `def` 闭包** | 函数体内的 `def inner(...)` 形成可调用闭包；**形参规则与模块级 `def` 完全一致** |
| **First-class 调用** | `inner(...)`、`f = inner`、`return inner`、传入 `Callable` 形参、存入容器字段 |

嵌套闭包函数须复用现有模块级函数的全部译器能力，包括但不限于：

- 默认实参、`T @ref` / `T @optional` / `T @lazy`
- `**kwargs: Options`（`expand_kwargs_options`）
- 同构可变参 `def f[*Ts](...)`、异构 pack `def f[T, *Us](...)`
- `@overload`、`@noexcept`、泛型约束、`type if` 分派
- 描述符形参、`@lazy` supplier 透传（与 [lazy 形参](./参考手册.md) 一致）

### 1.2 定案边界（用户确认）

| 项 | 定案 |
|----|------|
| **自引用** | ✅ 允许；`def outer(): def inner(k): return inner(k-1) ...` 等，内层在 `def inner` 执行完成后可绑定自身名 |
| **类方法内嵌套 `def`** | ✅；引用 `self` 时 capture 语义 **等价于** 今日委托 `lambda` 的 `[this]` |
| **语法范围** | **仅** 嵌套 `def`；**不** 将 `lambda` 提升为完整 `global`/`nonlocal` 闭包（`lambda` 仍限 §7.4 委托场景） |
| **`global x` 前提** | `x` **必须**已有模块级 `x: T = ...`（`AnnAssign`）；仅 `global x; x = 1` 且无模块声明 → **翻译期硬错误** |
| **类型推断** | ✅ `f = inner` 由译器推断 `PyCallable<Ret, Args...>`，规则与现有 `inc = lambda x: x + 1` 一致；亦可显式 `f: Callable[[A], R] = inner` |
| **逃逸 / 生命周期（首期）** | 外层 `return inner`、把 `inner` 存入容器/字段时，capture **暂按 C++11 lambda 语义**（引用捕获绑定到 enclosing 栈帧；**不**做 CPython cell / 堆延长）。用户须保证闭包不越过 defining 栈帧仍被调用；后续版本可升级为 heap cell |

### 1.3 暂不实现

- `lambda` 的 `global` / `nonlocal` / 自由变量 capture（除已有 `[this]` / 无 capture 委托用法）
- 无模块级注解的 `global` 创建新模块变量
- 闭包逃逸时的 **堆 cell / `RefCount` capture bag**（见 §1.2 首期限制）
- 内层 `def` 含 `yield` / `async def` 与闭包 capture **交叉**（生成器展开与闭包须分阶段设计；首期硬错误或单列 follow-up）
- 动态 `exec`、运行时改 `__globals__`
- 跨 TU capture 其它翻译单元 static local

---

## 2. Python 语义（静态子集）

### 2.1 `global`

```python
_counter: int = 0

def bump() -> None:
  global _counter
  _counter += 1
```

- `global` 仅出现在 **函数/方法体** 语句列表顶层（与 CPython 相同；在 `if`/`for` 内出现按 CPython 3 规则：整函数编译单元生效）。
- 读/写 `_counter` 均 lowering 为模块命名空间内的 C++ 变量（与现有 `module_constants` / 模块级 `AnnAssign` emit 同源）。
- **未**在模块级找到 `x: T = ...` → `TranslationError`（明确提示须先模块级注解）。

### 2.2 `nonlocal`

```python
def outer() -> Callable[[int], int]:
  n: int = 1

  def inner(x: int) -> int:
    nonlocal n
    n += x
    return n

  return inner
```

- `nonlocal x` 的 `x` 须在 **静态 enclosing 函数链** 上存在绑定（参数或局部 `AnnAssign` / `Assign` 首次绑定）；否则翻译期错误。
- 赋值 `x = ...` 在未声明 `nonlocal`/`global` 且外层已有 `x` 时：按 CPython，内层创建新 local；Py2Cpp **首期与 CPython 一致**（内层新 local，不自动 capture）。
- 读外层 `x` 且无 local 绑定：视为 **自由变量**，须 capture（见 §3）。

### 2.3 嵌套 `def` 与自引用

```python
def make_fact() -> Callable[[int], int]:
  def fact(n: int) -> int:
    if n <= 1:
      return 1
    return n * fact(n - 1)  # 自引用：fact 在 def 语句完成后可见
  return fact
```

- 内层函数名在 **内层 `def` 语句执行后** 才绑定到闭包对象（与 CPython 一致）。
- 自引用 lowering：闭包变量持有 `PyCallable` 槽位；内层函数体递归调用走 **同一 capture 环境** 上的 invoke，或 mangled 静态函数 + 环境指针（见 §4）。

### 2.4 形参 parity 示例

```python
@copyable
@dataclass
class Opt:
  tag: int = 0

def outer(seed: int) -> Callable[[int], int]:
  base: int = seed

  def inner(
    x: int,
    default: int @lazy = 0,
    **opts: Opt,
  ) -> int:
    nonlocal base
    if opts.tag:
      base += opts.tag
    return base + x + default

  return inner
```

内层 `inner` 的签名分析、kwargs 脱糖、`@lazy` prologue、调用点实参包装 **与模块级函数共用** `FunctionSig` / `expand_kwargs_options` / `lazy_param_emit` 路径。

---

## 3. 自由变量与 capture 分析

### 3.1 符号分类（每个嵌套函数）

对嵌套函数 `F`，分析其名称引用：

| 类别 | 条件 | Lowering |
|------|------|----------|
| **Local** | `F` 内形参、或 `F` 内首次赋值绑定 | 普通栈/local |
| **Global** | `global` 声明 | 模块级 C++ 变量 |
| **Nonlocal** | `nonlocal` 声明 | capture enclosing 绑定（引用） |
| **Free（implicit）** | 读 `x`，`x` 既非 local 也非 global/nonlocal，且 enclosing 链上有 `x` | 同 nonlocal：capture |
| **Builtin/import** | 解析为内建或 import 绑定 | 现有 `visit_Name` 路径 |

**Cell 合并**：同一 enclosing 变量被多个内层函数 capture 时，共享 **同一 capture 槽**（等价 CPython cell；首期可用「enclosing 栈变量引用」实现，不单独 heap 分配）。

### 3.2 `self` capture

类实例方法内的嵌套 `def`：

```python
class Box:
  v: int

  def method(self) -> Callable[[int], int]:
    def add(delta: int) -> int:
      self.v += delta
      return self.v
    return add
```

- 自由变量 `self` → capture 等价 **`[this]`**（与 `delegate_emit._emit_delegate_cpp_lambda` 一致）。
- 静态方法内嵌套 `def` 无 implicit `self`；若显式使用类名/静态成员走现有规则。

### 3.3 逃逸检测（首期：文档化限制，不硬禁）

以下用法 **允许编译**，但 lifetime 与 C++ 引用捕获相同：

```python
def outer() -> Callable[[], int]:
  n: int = 42
  def inner() -> int:
    return n
  return inner  # 返回后 outer 栈帧销毁 → n 悬空（UB）
```

首期 **不** 在译期禁止 `return inner` / `lst.append(inner)`；在文档与 §6 明确 **C++ lambda 语义**。回归测试 **避免** 依赖跨栈帧调用；后续 heap cell 版本再覆盖逃逸用例。

---

## 4. C++ Lowering 策略

### 4.1 命名

| Python | C++ 符号 |
|--------|----------|
| 模块 `def outer` | 现有 `outer` / 模块命名空间 |
| `outer` 内 `def inner` | `{outer}__{inner}` 或 `{outer}__inner__L{lineno}`（mangled，避免 ODR 冲突） |
| 多层嵌套 | 链式前缀 `{outer}__{mid}__{inner}` |

类方法内：`{Class}_{method}__{inner}`。

### 4.2 无 capture 闭包

若 `inner` **无** free/nonlocal/`self` capture：

- 生成普通 **静态函数** `{mangled}(args...) -> Ret`（与模块函数 emit 相同，仅命名 mangled）。
- 定义点：`PyCallable<Ret, Args...> inner = { ctx: nullptr, invoke: &{mangled}_thunk }` 或直接可调用对象包装（与自由函数 `PyCallable` 一致）。

### 4.3 有 capture 闭包

**Capture 环境**（栈上，首期）：

```cpp
struct outer__inner_env
{
  int& base;           // nonlocal / free
  Box* self;             // [this] 时为 this
  // 无 global 成员：global 直接读模块变量
};

// 定义点（outer 体内，inner def 语句）
outer__inner_env _env_inner { base, this };
PyCallable<int, int> inner {
  &_env_inner,
  &outer__inner_invoke<int>
};
```

**Invoke thunk**（模板化以支持内层泛型形参）：

```cpp
template<typename... Ts>
static int outer__inner_invoke(void* ctx, int x, Opt opts)
{
  auto& e = *static_cast<outer__inner_env*>(ctx);
  // lazy default / kwargs 已在 thunk 内或外层包装层处理
  return /* mangled body using e.base, e.self->v, x, ... */;
}
```

与现有设施对齐：

| 机制 | 复用点 |
|------|--------|
| 函数体 emit | `_emit_stdlib_module_function_body` / 模块函数 emit 抽公共 `emit_function_body(tr, func, sig, env?)` |
| `PyCallable` | `core/delegate.h`；`py_callable_lambda_invoke` / 新建 `py_callable_closure_invoke` |
| `@lazy` | `lazy_param_emit.emit_lazy_param_prologue` + `try_emit_lazy_call_arg` |
| `**kwargs: Opt` | `expand_kwargs_options` 已将 `def inner(**kw: Opt)` 脱糖为 `def inner(kw: Opt)` |
| 泛型 / variadic | 现有 `FunctionSig.func_ft`、`variadic_template_emit` |

### 4.4 定义点语句 emit

嵌套 `def inner(...): ...` 语句 **不** 展开内层 body 到外层（修复今日 `NodeVisitor` 误 inline 内层 body 的问题）：

```python
def outer():
  def inner(x: int) -> int:
    return x + 1
  return inner
```

生成（概念）：

```cpp
void outer()
{
  /* inner 无 capture： */
  PyCallable<int, int> inner { nullptr, &::inner_thunk };  // 或等价
  return inner;
}
```

有 capture 时先构造 `_env_*`，再绑定 `PyCallable`。

### 4.5 调用

| 形式 | Lowering |
|------|----------|
| `inner(a, b)` | 若变量类型为 `PyCallable<R, A, B>`：`py_callable_invoke(inner, a, b)` 或 `inner.invoke(inner.ctx, a, b)` |
| 传给 `Callable[[A], R]` 形参 | 按值传递 `PyCallable`（与委托 §7.4 一致） |
| 递归 `fact(n-1)` | `fact.invoke(fact.ctx, n-1)`；`fact` 为闭包变量 |

### 4.6 与 `lambda` 赋值规则一致

现有（参考手册 §7.4）：

```python
inc = lambda x: x + 1   # 推断 Callable / PyCallable
d += inc
```

嵌套 `def`：

```python
def outer():
  def inc(x: int) -> int:
    return x + 1
  f = inc          # f: PyCallable<int, int>（推断）
  return f
```

显式注解可选：`f: Callable[[int], int] = inc`。

---

## 5. 译器流水线

### 5.1 新增 / 改动 Pass

建议插入顺序（在 `expand_generators` **之后**、`expand_decorators` **之前** 或 analyze 之前）：

| 顺序 | Pass | 文件 | 作用 |
|------|------|------|------|
| — | `analyze_closures` | `passes/closures.py`（新） | 构建嵌套函数树；标注 global/nonlocal/free；capture 列表；逃逸标记（可选，首期仅 metadata） |
| — | （无 AST 改写或轻量改写） | — | 保留嵌套 `FunctionDef` 于外层 body；emit 阶段识别 |

**Analyze 阶段**：

- `SemanticAnalyzer`：为嵌套函数注册 `FunctionSig`（键：`(enclosing, mangled_name)` 或 `ClosureInfo` 表）。
- `visit_Global` / `visit_Nonlocal`：写入当前 `Scope` 的 `declared_global` / `declared_nonlocal` 集合。

**Emit 阶段**：

- `visit_FunctionDef`（语句位）：区分模块级 vs 嵌套；嵌套走闭包定义 emit。
- `visit_Name`：按 binding 类别选择 local / capture env 成员 / 模块变量。

### 5.2 关键源文件（实现时）

| 路径 | 改动 |
|------|------|
| `src/passes/closures.py` | 新建：symtable / capture 分析 |
| `src/analysis/closure.py` | 新建：`ClosureInfo`、`FreeVar`、`CaptureSlot` |
| `src/analysis/analyzer.py` | 嵌套函数签名注册 |
| `src/translator.py` | `visit_FunctionDef`、`visit_Global`、`visit_Nonlocal`；`_emit_body` 不再误 inline 嵌套 def |
| `src/emit/closure_emit.py` | 新建：env 结构体、thunk、`PyCallable` 包装 |
| `src/emit/call_emit.py` | `PyCallable` 变量调用分发 |
| `src/analysis/ir.py` | `Scope` 扩展：`globals`、`nonlocals`、`closure_node` |
| `src/passes/strict_style.py` | 可选 S 规则：禁止未声明 cross-scope 赋值混淆 |

### 5.3 测试矩阵（实现后）

| 文件 | 覆盖 |
|------|------|
| `test/lang/test_closure.py` | `global` 读写模块变量；`nonlocal` 多层；无 capture / 有 capture；`f = inner` 推断；`**opts`；`@lazy`；自引用递归；类内 `[this]` |
| `src/tests/test_closure_analysis.py` | capture 集、global 未声明报错、mangled 名 |

**首期不测**：跨栈帧 `return inner` 后调用（UB，仅文档警示）。

---

## 6. 与 CPython 3.13 差异摘要

| 项 | CPython | Py2Cpp（首期） |
|----|---------|----------------|
| `global x` 无模块 prior | 运行时在 module dict 创建 | **翻译期错误**（须 `x: T = ...`） |
| 闭包逃逸 lifetime | cell 堆对象 | **C++ 引用 capture / 栈 env**；逃逸 UB |
| `lambda` 闭包 | 完整 | **不支持**（仅委托场景） |
| 内层 `yield` + capture | 支持 | **暂不实现** / 硬错误 |
| `global`/`nonlocal` 在块内 | 函数级生效 | 同 CPython |

---

## 7. 文档与索引

| 文档 | 节 |
|------|-----|
| [参考手册 §6.6](./参考手册.md#66-global--nonlocal--嵌套-def-闭包) | 用户可见能力表 |
| [编码规范 §7.5](./编码规范.md#75-嵌套-def-闭包与-global--nonlocal) | 推荐写法与禁区 |
| [编码规范 §7.8](./编码规范.md#78-嵌套-def-闭包与-global--nonlocal) | 推荐写法与禁区 |
| [参考手册 §7.4](./参考手册.md#74-多播委托-delegate) | `PyCallable` / `Callable` 与 `lambda` 赋值 |
| [reference.md §2.1](../.cursor/skills/py2cpp-design/reference.md#21-passes) | Pass 顺序（实现后更新） |

---

## 8. 实现检查清单

```text
[ ] passes/closures.py + analysis/closure.py
[ ] visit_Global / visit_Nonlocal / visit_FunctionDef（嵌套）
[ ] 模块级 global 目标须存在 AnnAssign（硬错误）
[ ] 嵌套 def 形参 parity（kwargs / lazy / variadic / overload）
[ ] PyCallable 推断与调用（与 lambda 赋值一致）
[ ] self → [this] capture
[ ] 自引用递归
[ ] test/lang/test_closure.py + src/tests/test_closure_analysis.py
[ ] 参考手册 §6.6、编码规范 §7.8、reference Pass 表
[ ] 文档注明逃逸 = C++ lambda 语义（首期）
```
