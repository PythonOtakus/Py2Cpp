# 条件类型与类型萃取（Py2Cpp 扩展）

> **状态**：G1 条件类型别名已实现（``type A[T, U = …] = … if … else …``）；类体内 type if 已实现。详见下文与 [参考手册 §5.2](./参考手册.md#52-泛型与-type-别名)。  
> **TypeNode IR**（结构化类型、存储变换、render）：见 [type-node.md](./type-node.md)。  
> **非 CPython**：语法与语义为 Py2Cpp 编译期类型系统扩展，CPython 3.13 无对应运行时行为。

---

## 1. 目标

在 **PEP 695 静态类型** 之上，提供类似 TypeScript 条件类型（``T extends U ? X : Y``）与 ``infer`` 的能力，用于：

- 从 ``list[T]``、``dict[K, V]``、``Pointer[T]`` 等**解包**内部类型参数；
- 在**注解**与**模块/类内别名**中复用解包结果（不必在每个函数里写 ``type if``）；
- 匹配失败时落到 **``Never``** 底类型，在需要存储的位置 **编译期拒绝**。

与已有 **[泛型 type if](./参考手册.md#泛型类型条件py2cpp-扩展非-cpython)** 的关系：

| 机制 | 用途 |
|------|------|
| **条件类型别名**（本文主规格） | 可复用的类型变换；注解 ``ListElemOf[T]`` / ``ValOf[T]`` 等 |
| **函数 type if** | 同一泛型函数体内的编译期分派 |
| **``T.Element`` / ``T.Value``**（type if 分支内，已实现） | ``list[...]`` 等匿名捕获的便捷写法；与条件别名**并存** |

---

## 2. 核心语法：捕获形参 + 三目别名

### 2.1 基本形式

```python
type ListElemOf[T, _V = ...] = _V if T is list[_V] else T
```

| 部分 | 含义 |
|------|------|
| ``T`` | **调用形参**：使用时只传 ``ListElemOf[list[int]]``、``ListElemOf[str]`` 等 |
| ``_V = ...`` | **捕获形参**：须 ``_`` 前缀；仅由 RHS 中 ``T is list[_V]`` 绑定，调用侧不传 |
| ``_V if T is list[_V] else T`` | **类型三目**：编译期求值，**不是**运行时 ``if`` |
| ``else T`` | 非 ``list[…]`` 时恒等回退 |

**实例化（规划）**：

| 写法 | 结果类型 |
|------|----------|
| ``ListElemOf[list[int]]`` | ``int`` → C++ ``PyInt`` |
| ``ListElemOf[list[Widget]]`` | ``Widget`` |
| ``ListElemOf[str]`` | ``str``（走 ``else``） |
| ``ValOf[dict[str, int]]`` | ``int``（匹配 ``dict[str, _W]`` 分支） |

### 2.2 捕获形参规则

1. **必须**写 ``= ...`` 才能声明为捕获形参（禁止隐式「模式里出现就算捕获」——意图须显式）。
2. 捕获名**不得**与别名其它形参、函数/类头形参同名；**不得**与模块内具体类型名冲突（若冲突则该名在模式中按**具体类型**匹配，见 §4）。
3. 调用侧**禁止**显式传入捕获形参：``ListElemOf[list[int], int]`` → 翻译期错误。
4. 捕获形参**不出现在** C++ 别名模板的「用户可见实参列表」；仅在条件求值时由编译器绑定，并参与生成的 ``using`` / 展开结果。

### 2.3 ``Never`` 与无 ``else``

```python
type StrictElem[T, _V = ...] = _V if T is list[_V] else Never
```

- ``Never``：底类型；落到变量、字段、参数、返回等**存储类型**时 ``static_assert`` 失败。
- **无 ``else``** 的三目：等价 ``else Never``（与函数 **type if** 无 ``else`` 一致）。

### 2.4 多捕获与链式三目

```python
type ValOf[T, _V = ..., _W = ...] = (
  _V if T is list[_V]
  else _W if T is dict[str, _W]
  else T
)
```

- 每个 ``= ...`` 形参只在其出现的模式分支中绑定。
- 链式 ``A if … else B if … else C`` 与 Python 三目结合律一致；**建议**多分支时用括号分行（如上）。

---

## 3. 标准库范本别名与命名规范

条件类型别名在 **G1** 已可在模块/类内定义；标准库宜在 ``py2cpp/core/``（或 ``py2cpp/typing.py``）集中导出**同一套名字**，业务模块只 **组合**、不另造同义萃取名。

### 3.1 统一命名规范

| 规则 | 约定 |
|------|------|
| **形态** | ``{Role}Of[T, Capture = ...] = … if T is Pattern else Fallback`` |
| **Role** | PascalCase **语义角色** + 固定后缀 ``Of``（一元解包）；**禁止**缩写公开名（``ElemOf``、``PtOf``） |
| **调用形参** | 恒为 ``T``：输入待萃取的**整型**（``list[int]``、``Pointer[U]``、泛形参 ``T`` 等） |
| **捕获形参** | 必须 ``_X = ...``（**下划线前缀** + 语义字母，见 §3.3）；**禁止**无下划线的 ``U``/``P`` 或裸 ``_`` |
| **Fallback** | 默认 ``else T``（恒等，非匹配时原样返回）；严格解包用 ``else Never`` 或省略 ``else`` |
| **实例化** | 只传非捕获实参：``ListElemOf[list[int]]``；**禁止** ``ListElemOf[..., int]`` |
| **组合** | 多层解包用别名嵌套：``type Inner[T] = ListElemOf[ListElemOf[T]]``；**勿**在标准库再发明 ``InnerElem`` / ``DeepElem`` |
| **领域扩展** | 模块内定义：``TaskPayloadOf``（``concur/task.py``）、``JsonDecoder.loadContainer``（``serde/json.py``） |
| **与 type if** | 函数**体内**分派仍用 ``if T is list[...]:`` + ``T.Element``；**注解 / 跨函数**优先 ``ListElemOf[T]`` / ``ValOf[T]`` |
| **与协议关联类型** | ``type Element = ...``（``@protocol`` 成员约束）≠ ``ListElemOf``；前者无 RHS，后者为条件别名 |

**C++ 生成名**：译器为每个条件别名生成 ``__py2cpp_type_cond_{Name}_{lineno}_pick`` + ``using {Name} = …``；用户代码与注解**只写 Python 别名名**，不写 pick 符号。

### 3.2 常用类型萃取一览

下表为 Py2Cpp 条件别名。**G1 已实现**；``py2cpp/util/types.py`` 导出恒等/严格变体；``KeyOf``/``PointeeOf`` 等未单独导出，分派用 type if 的 ``T.Key`` / ``T.Value`` / ``Pointer[…]`` 模式。

| 别名 | 匹配模式 | 捕获 | Fallback | 典型实例化 | 标准库 | 说明 |
|------|----------|------|----------|------------|--------|------|
| **``ListElemOf``** | ``T is list[_V]`` | ``_V`` | ``T`` | ``list[int]`` → ``int``；``str`` → ``str`` | ✅ | 同质 ``list`` 元素 |
| **``StrDictValueOf``** | ``T is dict[str, _V]`` | ``_V`` | ``T`` | ``dict[str, int]`` → ``int`` | ✅ | 字符串键 ``dict`` 值 |
| **``ValOf``** | ``list[_V]`` 或 ``dict[str, _W]`` | ``_V`` / ``_W`` | ``T`` | 多分支 list + str-dict | ✅ | 通用容器值萃取 |
| **``ListOnly``** | ``T is list[_V]`` | ``_V`` | ``Never`` | ``list[int]`` → ``int``；``str`` → 编译失败 | ✅ | 严格 list-only |
| **``KeyOf``** / **``ValueOf``** | ``dict[_K, …]`` / ``dict[..., _V]`` | ``_K`` / ``_V`` | ``T`` | — | 否 | 概念上与 ``T.Key``/``T.Value`` 等价；模块内自建 |
| **``PointeeOf``** | ``T is Pointer[_P]`` | ``_P`` | ``T`` | — | 否 | ``Pointer[T]`` 形参时 ``T`` 已是 pointee |
| **（组合）``Inner``** | ``ListElemOf[ListElemOf[T]]`` | — | — | ``list[list[int]]`` → ``int`` | 用户层 | 见 ``test/lang/test_type_if.py`` |
| **``TaskPayloadOf``** / **``GatherElemOf``** | ``Task[_R]`` / ``Task[list[_U]]`` | ``_R`` / ``_U`` | ``T`` | — | 模块内 | ``py2cpp/concur/task.py`` |
| **``TupleAt``** / **``ResultOf``** 等 | — | — | — | — | **G3** | 尚未实现 |

**已实现、非 ``*Of`` 的 type if 便捷属性**（仅 **函数 type if / 类 type if 分支内**）：

| 写法 | 容器 | 等价萃取（概念上） |
|------|------|-------------------|
| ``T.Element`` | ``list[…]`` / ``PyList<…>`` | ``ListElemOf[T]`` 在 list 匹配分支 |
| ``T.Key`` | ``dict[…]`` 第 0 参 | 模块内 ``KeyOf[T]``（未标准库导出） |
| ``T.Value`` | ``dict[…]`` 第 1 参 | ``StrDictValueOf[T]``（``dict[str, …]``）或 ``ValOf[T]`` |

### 3.3 捕获形参字母约定（须 ``_`` 前缀）

捕获形参**必须**写 ``_X = ...``（``X`` 为语义字母）。与 **type if** 模式内匿名 ``list[...]``（译器生成 ``_Ty0``）区分：后者是**模式占位**，前者是**别名头上的具名捕获**。

| 捕获名 | 语义 | 用于 |
|------|------|------|
| **``_V``** | 解包槽位：list **元素** 或 dict **值** | ``list[_V]``、``dict[..., _V]`` |
| **``_K``** | **K**ey | ``dict[_K, …]`` |
| **``_P``** | **P**ointee | ``Pointer[_P]`` |
| **``_W``** | 第二槽（多分支别名） | ``ValOf`` 中 dict 值，与 list 的 ``_V`` 并列 |
| **``_E``** / **``_I``** | **E**lement / **I**ndex（G3） | 迭代器、元组 NTTP |

**禁止**：无下划线捕获（``V = ...``）、裸 ``_ = ...``、与调用形参 ``T`` 同名。

### 3.4 恒等回退 vs 严格（``Never``）

| 策略 | RHS 末尾 | 适用 |
|------|----------|------|
| **恒等** | ``else T`` | 泛型 API：``def f[T](x: T) -> ListElemOf[T]``；非 list 时 ``ListElemOf[str]=str`` |
| **严格** | ``else Never`` 或无 ``else`` | 仅接受 list：``def g[T](xs: ListOnly[T])``；``ListOnly[str]`` 翻译失败 |

标准库导出 **``ValOf`` / ``StrDictValueOf`` / ``ListElemOf`` / ``ListOnly``**（``py2cpp/util/types.py``）；``KeyOf``/``PointeeOf`` 等按需模块内定义。

**``@union`` ADT**（``IterResult`` / ``Result`` / ``Optional`` 等）亦可在类体内写 ``type YieldValue = YieldType`` 等简单别名；变体字段、属性与 ``Cls[T].Alias`` 注解均可引用。``Result`` 模块另含 ``OkOf`` / ``ErrOf`` 条件别名。

### 3.5 标准库定义（``py2cpp/util/types.py``）

```python
type ValOf[T, _V = ..., _W = ...] = (
  _V if T is list[_V]
  else _W if T is dict[str, _W]
  else T
)
type StrDictValueOf[T, _V = ...] = _V if T is dict[str, _V] else T
type ListElemOf[T, _V = ...] = _V if T is list[_V] else T
type ListOnly[T, _V = ...] = _V if T is list[_V] else Never
```

**``@boxing`` 类**（如 ``Node[T]`` 已是 ``Node<T>*``）**勿**再包 ``Pointer[…]``；解包用类头形参 ``T``。

**``Json.loads``**：``JsonDecoder.loadContainer[T]()`` 集中 ``list[…]`` / ``dict[str, …]`` wildcard 分派。

---

## 4. 类型模式（``T is …``）与具体类型歧义

条件别名 RHS 与 **type if** 共用同一套**结构类型模式**（见 ``src/passes/type_if.py``）：

| 模式 | 匹配 | 捕获 |
|------|------|------|
| ``T is int`` | 精确 ``PyInt`` | 无 |
| ``T is list[int]`` | ``PyList<PyInt>`` | 无 |
| ``T is list[_V]`` | 任意 ``PyList<V'>`` | ``_V`` ← ``V'`` |
| ``T is list[...]`` | 任意 ``PyList<_Ty0>`` | 匿名 ``_Ty0``（已实现，type if） |
| ``T is dict[str, V]`` | ``PyDict<PyStr, V'>`` | ``V`` ← ``V'`` |
| ``T is Pointer[_P]`` | ``P'*``（``Pointer[P]`` 译法） | ``_P`` ← pointee |

**歧义规则**（模式槽位上的标识符）：

1. 若标识符是 **builtin / 在 scope 内的类 / 已 import 类型** → **具体类型**，参与精确匹配（``list[Widget]`` 只匹配 ``PyList<Widget>``）。
2. 若标识符是别名的 **捕获形参**（头上有 ``Name = ...``）→ 在模式中为**绑定槽**。
3. 否则在 **type if** 模式内（非别名头声明时）：可作为 **命名捕获** 扩展（``list[Elem]`` ≡ ``list[...]`` + 分支内 ``Elem``）；条件别名**不**依赖此捷径，以 §2 为准。

**禁止**：``T is list[T]``、``T is ...``、``list[_]``、``not T is int``（须 ``T is not int``）；``T in [list[U], …]`` 中**不可**含 ``...`` 或捕获形参。

---

## 5. ``...`` 的三义（须区分）

| 位置 | 含义 |
|------|------|
| ``type Element = ...``（协议/关联类型） | 实现类须提供 ``Element``；见 [编码规范 §6.2](./编码规范.md#62-类内-type-别名) |
| ``_V = ...``（别名头捕获默认） | **捕获形参默认**：调用时不传，由模式绑定 |
| ``list[...]``、``dict[str, ...]``（**type if** 模式内） | 匿名捕获 → ``_Ty0``、``_Ty1`` |

---

## 6. 与 ``T.Element`` / ``T.Value`` 的关系

**type if** 分支内（**已实现**）：

```python
elif T is list[...]:
  x: Box[T.Element] = ...
elif T is dict[str, ...]:
  x: Box[T.Value] = ...
```

``T.Element`` 映射到 ``PyList<…>`` 的第 0 模板实参；``T.Value`` 映射 ``PyDict<…>`` 的第 1 实参。

**条件别名**（规划）：

```python
type ListElemOf[T, _V = ...] = _V if T is list[_V] else T
# 注解中直接写 ListElemOf[T]，不必写 T.Element
```

两者在 ``list[…]`` 解包上**等价**；新代码优先 **条件别名**；标准库与测试可渐进迁移。

---

## 7. C++  lowering 策略

### 7.1 别名实例化

对用户写法 ``ListElemOf[Concrete]``（仅传非捕获形参）：

1. 将 ``Concrete`` 代入 ``T``，得到具体 C++ 类型 ``C``（如 ``PyList<PyInt>``）。
2. 对 RHS 三目做**编译期求值**：
   - 测试 ``C`` 是否匹配 ``T is list[U]`` 结构模式；
   - 匹配则绑定捕获形参 ``U`` 的 C++ 名，结果为 ``U`` 侧；
   - 否则求 ``else`` 分支（``C`` 或 ``Never``）。
3. 生成展开类型用于注解、``using``、模板实参。

### 7.2 泛型别名声明

模块/类内：

```python
type ListElemOf[T, _V = ...] = _V if T is list[_V] else T
```

生成（概念上）：

```cpp
template<typename T>
using ListElemOf = /* meta: 按 T 分派，匹配 list 时引入 typename U，否则 T */;
```

实现上复用 **type if** 的 ``pick<T, void>`` / 部分特化 machinery（``src/passes/type_if.py``），新增 ``src/passes/type_conditional.py`` 与 ``src/analysis/type_extract.py`` 做别名侧求值，**避免**在业务模块手写 ``enable_if``。

### 7.3 ``Never``

- Python 桩：``py2cpp/util/types.py`` 中 ``Never``（或 ``typing_extensions`` 风格声明）。
- C++：``PyNever`` 标记类型；任何需要对象存储的位置 ``static_assert(sizeof(PyNever)==0, ...)`` 或等价拒绝。

---

## 8. 实现分期

| 阶段 | 内容 | 主要文件 |
|------|------|----------|
| **G0** | ``Never`` + ``T.Element``/``Key``/``Value`` 在更多类型上下文（含别名展开钩子） | ``ir.py``、``translator.py``、``templates/core/+types.h`` |
| **G1** | 条件别名 + ``py2cpp/util/types.py``；``test/lang/test_type_if.py`` | ``type_conditional.py``、``type_extract.py`` |
| **G1.5**（可选） | type if 模式内命名捕获 ``list[Elem]``（与 ``list[...]`` 等价） | ``type_if.py`` |
| **G2** | 注解中的类型三目（非别名 RHS）；简化 ``Json.loads`` 等对 ``_type_if_concrete_bind`` 的依赖 | ``analyzer.py`` |
| **G3** | ``Pick``/``Omit``/``Extract`` 等映射类型（若仍需要） | 待定 |

**验证**：G1 完成后至少 ``build.bat lang/test_type_if`` 全绿（含 ``TypeAliasTests``）；动标准库别名时 bootstrap ``py2cpp/__init__.py``。

---

## 9. 校验与错误

| 违规 | 结果 |
|------|------|
| 调用 ``A[T, _V]`` 显式传入捕获形参 | ``TranslationError`` |
| 捕获形参非 ``_X``（无下划线或裸 ``_``） | ``TranslationError`` |
| 捕获形参未在 RHS 模式中出现 | ``TranslationError`` |
| RHS 非 ``IfExp`` 且非（将来 G2）允许的纯 ``Name``/``Subscript`` | ``TranslationError`` |
| 条件求值为 ``Never`` 但用于字段/参数/返回 | C++ ``static_assert`` / 翻译期错误 |
| ``T is not …`` 用于别名 RHS 三目 | 不支持；别名 RHS 仅 ``X if Cond else Y``，Cond 为 ``T is Pattern`` |
| 同一函数多条 **type if** 链 | 仍按现规硬错误（与本文无关） |

---

## 10. 编码规范要点

1. **解包优先用别名**：``ListElemOf[T]``、``ValOf[T]``；捕获写 ``_V``/``_W``，勿用 ``U``/``P``。
2. **指针**：``def f[T](p: Pointer[T])`` 时 ``T`` 已是 pointee；泛形参为 ``Pointer[U]`` 时在 type if 内分派或模块内自建 ``PointeeOf``。
3. **无 STL**；条件类型纯编译期，无运行时开销。
4. **文档同步**：实现落地后更新 [参考手册 §5.2](./参考手册.md#52-泛型与-type-别名)、[编码规范 §6.2](./编码规范.md#62-类内-type-别名) 的「已实现」表述。

---

## 11. 示例汇编

### 11.1 恒等回退

```python
type ListElemOf[T, _V = ...] = _V if T is list[_V] else T

def head[T](xs: T) -> ListElemOf[T]:
  ...
```

### 11.2 严格解包

```python
type ListOnly[T, _V = ...] = _V if T is list[_V] else Never

def only_list[T](xs: ListOnly[T]) -> int:
  ...
# ListOnly[str] → 编译失败
```

### 11.3 多分支（``ValOf``）

```python
type ValOf[T, _V = ..., _W = ...] = (
  _V if T is list[_V]
  else _W if T is dict[str, _W]
  else T
)
```

### 11.4 嵌套别名

```python
type ListElemOf[T, _V = ...] = _V if T is list[_V] else T
type Inner[T] = ListElemOf[ListElemOf[T]]   # list[list[int]] → int
```

### 11.5 与 type if 组合

```python
type ListElemOf[T, _V = ...] = _V if T is list[_V] else T

def dispatch[T](x: T) -> int:
  if T is int:
    return 1
  elif T is list[ListElemOf[T]]:
    return 2
  else:
    return 0
```

---

## 12. 相关文档与代码

| 资源 | 路径 |
|------|------|
| 泛型 type if（已实现） | [参考手册 §5.2](./参考手册.md#泛型类型条件py2cpp-扩展非-cpython)、``src/passes/type_if.py`` |
| 类内/模块 type 别名 | [编码规范 §6.2](./编码规范.md#62-类内-type-别名) |
| ``Pointer[T]`` → ``T*`` | [参考手册类型对照](./参考手册.md#52-泛型与-type-别名)、``analyzer.py`` |
| 集成测 | ``test/lang/test_type_if.py``（``TypeIfModuleTests`` / ``TypeAliasTests``） |
| 译器单测 | ``src/tests/test_type_conditional.py`` |

---

## 13. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-19 | §3.3：捕获形参须 ``_X = ...``（``_V``/``_P``/``_K``）；译器校验；测试与文档同步 |
| 2026-06-15 | 删除 ``ElementOf``/``KeyOf``/``ValueOf``/``PointeeOf`` 四元组；标准库改为 ``ValOf``/``StrDictValueOf``/``ListElemOf``/``ListOnly`` |
