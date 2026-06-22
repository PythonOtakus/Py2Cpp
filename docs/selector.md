# 选择器（`select`）：字符串路径与译期内联规范

> **状态**：**G1 已实现**（``@dataclass`` / ``list`` struct backend；含 ``:$``/``$``/``;`` 同链绑定；``JsonDocument`` backend ⏳ G2）  
> **约束**：符合 [编码规范.md](./编码规范.md)；路径仅 **字符串字面量**；**无**新 Python 语法；**无** runtime 路径解释器；**无** C++ ``select`` 成员（与 ``assign`` 同级，译期专用）；**无** ``@protocol Selectable``（译器内置 backend 分派）。

---

## 1. 目标

在 **不引入新语法** 的前提下，用 **一条字符串路径** 从任意「可选中」对象上读取（首版只读）子结构，并由译器 **内联** 为 C++，适用于：

1. **持久化文档**（``JsonDocument[T]``、未来 ``YamlDocument[T]`` 等）——懒导航，不全量 ``load``。
2. **已物化对象**（``@dataclass`` / ``@serializable`` 实例）——直接成员/下标访问。
3. **序列容器**（``list[T]`` 等）——路径可 ``[-1]``、``[lo:hi]``、``{…}`` 过滤（大括号内为 **合法 Py2Cpp 表达式**）起头或中途切换。

与现有能力的关系：

| 已有 | ``select`` |
|------|------------|
| ``doc.teams[0].name`` 静态字段链 | 标量链等价于 ``select`` 返回 ``list[T]`` 的 **单元素** 情形 |
| ``JsonDocCursor.read_*()`` | 未来 Json backend；首版 struct 已内联 |
| ``obj.assign(w=1)`` 译期脱糖 | 同级魔法：``obj.select("…")`` 译期脱糖为导航+读 |

**不做**：runtime ``get(["a",0,"b"])``、非常量 path、f-string 路径、``select`` 写回/patch（另议）。

---

## 2. 用户 API

### 2.1 唯一调用形态

```python
names: list[str] = doc.select(".teams[0].name")
items: list[Member] = org.select(".teams[0].members[1:3]{.score > 0}")
active: list[Member] = org.select(".members{.score > 0 and .status == \"active\"}")
last: list[Team] = nodes.select("[-1]")
all_teams: list[Team] = org.select(".teams")
```

| 规则 | 说明 |
|------|------|
| **方法名** | ``receiver.select("…")`` |
| **参数** | **恰好一个**位置参数，且为 **字符串字面量** |
| **类上声明** | **不需要**；用户类**勿**手写 ``def select``（除非带真实方法体且与译器规则冲突，见 §5.2） |
| **C++** | **无** ``select`` 成员；调用点脱糖为 inline 表达式/语句块 |
| **返回类型** | **恒为** ``list[T]``；``T`` 由路径末步元素类型推导；左侧注解须为 ``list[T]``（译期校验） |
| **路径根** | **相对 ``receiver`` 根类型**；字符串内不写 ``doc`` / 变量名；**取 receiver 字段须以 ``.`` 起头**（见 §4.12） |

非常量 path（变量、拼接、f-string）→ **翻译期** ``TranslationError``。

### 2.2 与 ``assign`` 对照

| | ``assign`` | ``select`` |
|---|------------|------------|
| 用途 | 批量写字段 | 按路径读子结构 |
| 参数 | 关键字 / ``**opt`` | **字符串字面量** |
| 译器集合 | ``TRANSLATOR_ONLY_METHODS`` | 同集合扩展 ``"select"`` |
| C++ 成员 | 无 | 无 |
| 范本参考 | [编码规范 §7.4](./编码规范.md#74-kwargsoptions关键字选项)、``test/lang/test_kwargs_options.py`` | 本文 + ``test/lang/test_selector.py`` |

**返回语义（G1）**：无后处理时 **恒** ``list[T]``；带 ``@sort`` / ``@group`` / ``@count`` 时由**末步后处理**与左侧注解联合校验（见 §4.15）。

---

## 3. 译器 backend 分派（无 ``@protocol Selectable``）

**不**引入用户可见的 ``@protocol Selectable``；译器按 receiver 静态类型 **内置** backend（``src/emit/selector_emit.py`` + 后续 Json backend）。

### 3.1 能力分组（内部逻辑，非 runtime API）

| 能力 ID | 含义 | G1 struct emit |
|---------|------|----------------|
| **``NavField``** | 按名字进入对象字段 | ``recv.field`` |
| **``NavIndex``** | 整型下标（含 ``-1``） | ``.__getitem__(i)`` |
| **``NavSlice``** | 切片 ``[lo:hi]`` | ``for`` + ``append`` |
| **``NavFilter``** | ``{expr}`` | ``for`` + ``if expr`` + ``append`` |
| **``NavProject``** | ``.(a, b.c)`` + 可选后缀 | 多 ``append``（arm 末步同型） |
| **``MaterializeList``** | 产出 ``list[T]`` | **所有** ``select`` 路径（含单元素 ``append``） |

### 3.2 接收者 → backend（已实现 / 计划）

| receiver | 状态 |
|----------|------|
| ``@dataclass`` / 内存 struct | ✅ G1 |
| ``list[U]`` 根（``[-1]`` 等） | ✅ G1 |
| ``JsonDocument[T]`` | ⏳ G2 |
| 其它 | 翻译期报错 |

---

## 4. 路径字符串 DSL

路径在 **译期** 由 ``src/passes/selector_parse.py`` 解析为 **SelectorPlan / SelectorChainPlan IR**（与 JSON/YAML 无关）。

### 4.1 语法（EBNF 草案）

```text
bracket_item := INT | INT? ':' INT? (':' INT)? | STRING   # 见 §4.6 / §4.10

path     := top_path                                   # 顶层 ``','`` 多路径已废除；见 §4.9
top_path := root_step ( ('.' IDENT) | ('..' IDENT) | step_suffix )*
root_step :=
  | '?'? '.' IDENT                                 # receiver 字段；``?.x`` 可选根字段
  | '?'? '[' bracket_item (',' bracket_item)* ']'  # list 根下标/切片
  | '{' filter_expr '}'                            # list 根过滤
  | '.(' projection_arm (',' projection_arm)* ')' # receiver 根投影
  | '..' IDENT                                     # receiver 根递归下降
step_suffix :=
  | '[' bracket_item (',' bracket_item)* ']'   # 单/多下标或切片；见 §4.6
  | '.(' projection_arm (',' projection_arm)* ')'  # 多路径投影；见 §4.5
  | '{' filter_expr '}'            # 过滤；见 §4.4

bracket_item := INT | INT? ':' INT?

projection_arm := 相对 path 子串（可含 ``field`` / ``[…]`` / ``{…}`` / 嵌套 ``.(…)`` 等步，至 ``,`` 或 ``)``）

filter_expr :=
  从 ``{`` 与配对 ``}`` 之间子串提取，按 **Py2Cpp 表达式子集** ``ast.parse(mode='eval')``；
  须为合法 Py2Cpp 源码（与 [编码规范.md](./编码规范.md) 一致），**不是** JSON/mini-DSL。

IDENT    := [A-Za-z_][A-Za-z0-9_]*
```

**``{`` / ``}`` 配对**：解析 path 时按括号深度匹配；``filter_expr`` 内字符串字面量须正确转义（path 外层已是 Python 字符串，内层引号用 ``\"`` 等）。

### 4.2 示例

| 路径 | 说明 |
|------|------|
| ``".teams[0].name"`` | ``list[str]``，单元素 |
| ``".teams"`` | ``list[Team]``，枚举字段内全部元素 |
| ``".members[1:3]{.score > 0}"`` | 切片后过滤（简单比较） |
| ``".members{.score > 0 and .active}"`` | 复合布尔表达式 |
| ``".members{.score > threshold}"`` | 元素字段 + 调用点局部变量 |
| ``".items{.level >= 3 or .tag == \"vip\"}"`` | 链式比较 / 字符串字面量（path 内转义） |
| ``"[-1].children"`` | ``list`` 根：先末元素再字段（``[…]`` / ``{…}`` 可直接起头） |
| ``".items[-1].(name, id)"`` | 投影两字段（同后缀类型） |
| ``".f.(a.b, c).d"`` | 多路径：``f.a.b.d`` 与 ``f.c.d`` → ``list[d]`` |
| ``".f.(a.(x, y), b).d"`` | 嵌套投影 |
| ``".members[0, 1:3]"`` | 多下标/切片：``[0]`` 与 ``[1:3]`` 结果依次 ``append`` |
| ``".data['x']"`` | ``dict`` 字符串键下标 |
| ``".attrs['u', 'v']"`` | 多字符串键：依次 ``append`` 各键对应值 |
| ``".teams?[0].name"`` | 可选下标：teams 空则跳过 |
| ``".data?['x']"`` | 可选 dict 键：缺键则跳过 |
| ``"?.title"`` | 可选 **根** 字段：``Optional`` 无值则跳过 |
| ``".members{.score > 0}.(name, name)"`` | 过滤后投影（步序任意） |
| ``".teams[:].name"`` | list 全枚举（``[:]`` 通配）后取 ``name`` |
| ``".items[1:5:2]"`` / ``".items[::2]"`` | 切片步长 |
| ``".teams..name"`` | 递归下降：当前子树内所有 ``name`` 字段 |
| ``".teams[0, 1].name"`` | 多下标：``teams[0]`` 与 ``teams[1]`` 的 ``name`` |
| ``".(teams[0], teams[1]).name"`` | receiver 根投影 + 后缀（等价于上条） |

### 4.3 语义约束

- **字段名** 须在 **TypeGraph** 上存在（来自 ``@dataclass`` ``field_types`` / ``dataclass_field_specs``，与 ``@serializable`` 共用）。
- **根路径取 receiver 字段** 须以 ``.`` 起头（``".teams"``、``"?.title"``）；裸标识符起头（``"teams"``）为 **语法错误**；``[…]`` / ``{…}`` 仍可直接起头（见 §4.12）。
- **负索引** 与 Python 一致（``[-1]`` = 末元素）；JSON 数组 lazy 导航须与静态链 ``doc.teams[-1]`` **行为一致**（实现时可能扩 ``_array_index`` 或 emit 专用末元素循环）。
- **``dict[K,V]`` 非常量键**、``Union`` 分支选择：**暂不实现**（path 内 **字符串字面量** 键已支持，见 §4.10）。

### 4.4 过滤步 ``{expr}``（Py2Cpp 表达式）

大括号内 **不是** 独立 mini-DSL，而是与模块内其它代码 **同一套** Py2Cpp 表达式语法，译期从 path 子串 parse 为 AST 并 type-check。

| 项 | 规则 |
|----|------|
| **语法范围** | 任意 **合法 Py2Cpp 表达式**（[编码规范.md](./编码规范.md)：链式比较、``and``/``or``/``not``、括号、字段访问、字面量等；**无** STL、**无** 元组字面量容器等译器不支持形式） |
| **类型** | 在过滤上下文中须可推导为 **布尔**（``bool`` / 可用于 ``if`` 的真值语义，与 §3.1 一致） |
| **元素字段访问** | **``.`` 前缀**（``{.score > 0}``、``{.score}``）表示 **当前序列元素** 的字段/属性；译期 desugar 为元素成员访问；支持链式 ``.parent.name`` |
| **其它标识符** | **非** ``.`` 开头的标识符 **不** 表示元素字段，与 ``select`` 调用点 **同一作用域** 的普通表达式等价（如 ``len``、局部变量 ``threshold``、模块级名） |
| **emit** | 等价于对序列每项 ``if expr: append(...)`` 的内联展开；``{expr}`` 内自由名按调用点作用域 emit；lazy 文档 backend 在求值 ``expr`` 前按需 ``read_*`` 所需字段 |
| **与手写对照** | ``lst.select("{.score > threshold}")`` ≈ ``[x for x in lst if x.score > threshold]``（``threshold`` 为外层局部变量） |

**不支持**（翻译期报错，非降级）：

- ``filter_expr`` 内再嵌套未转义的 ``{``/``}``（与 path 括号配对冲突）
- 非布尔且无合理解释为过滤条件的表达式类型
- 引用在 ``select`` 调用点作用域内 **不存在** 或类型无法推导的标识符

### 4.5 投影步 ``.(arm, …)``（多路径选择）

从 **当前导航对象** 出发，并行求值多条 **相对子路径**；投影 **之后** 的路径步（后缀）作用于 **每条 arm**。各步（``field`` / ``[…]`` / ``{…}`` / 嵌套 ``.(…)``）**无固定顺序**，可任意混用。等价于多条共享前缀/后缀的静态链，结果 **按 arm 顺序** 写入 ``list[T]``。

| 项 | 规则 |
|----|------|
| **语法** | ``.(a.b, c)``；arm 为完整相对 plan（非仅单字段名） |
| **嵌套** | ``f.(a.(x, y), b).d`` → ``f.a.x.d``、``f.a.y.d``、``f.b.d`` |
| **后缀** | ``f.(a.b, c).d`` → ``f.a.b.d`` 与 ``f.c.d`` |
| **类型** | 各分支末步类型须相同 ``T``；``select`` 恒 ``list[T]`` |
| **emit** | 递归展开 + 多 ``append``（无 C++ ``select`` 成员） |

**示例**：

```python
vals: list[str] = root.select(".f.(a.b, c).d")
nested: list[str] = root.select(".f.(a.(x, y), b).d")
mixed: list[str] = team.select(".members{.score > 0}.(name, name)")
```

### 4.6 多下标 ``[i, lo:hi, …]``

同一 ``list`` 上 **逗号分隔** 多个下标或切片，依次 ``append`` 各段结果（与投影类似，但作用于序列下标而非 struct 字段）。

| 项 | 规则 |
|----|------|
| **语法** | ``members[0, 1:3]`` = ``members[0]`` + ``members[1:3]`` |
| **单段** | ``[1]`` / ``[1:3]`` 仍合法（无逗号时不构造 MultiBracket） |
| **类型** | 各段经后续路径步后末步类型须相同 |

### 4.7 list 通配与切片步长

| 项 | 规则 |
|----|------|
| **通配** | ``teams[:].name``：``[:]`` = 全枚举（``lo``/``hi`` 均为空） |
| **步长** | ``[lo:hi:step]``、``[::2]``；emit 为 ``for (si = lo; si < hi; si += step)``，默认 ``step = 1`` |
| **与多下标** | ``members[0, 1:3:2]`` 各段可独立带步长 |

### 4.8 递归下降 ``..field``

| 项 | 规则 |
|----|------|
| **语法** | ``teams..name``（双点 + 字段名） |
| **语义** | 自当前导航上下文起，在 **TypeGraph 子树** 内收集所有名为 ``field`` 的成员；穿越 ``struct`` 字段与 ``list``（list 自动枚举）；含嵌套 list 内同名字段 |
| **类型** | 各匹配路径末步类型须相同 ``T`` |
| **emit** | 每条匹配路径独立 ``append``（list 段插入隐式 ``[:]`` 枚举） |

### 4.9 多路径选取（无顶层 `,`）

**禁止**顶层 ``"path1, path2"`` 写法（翻译期报错并提示替代语法）。

| 需求 | 写法 |
|------|------|
| 同一 list 字段上多个下标/切片 | ``".teams[0, 1].name"``、``".members[0, 1:3]"``（§4.6 多下标） |
| 多条相对子路径 + 共享后缀 | ``".(teams[0], teams[1]).name"``、``".items.(name, id)"``（§4.5 投影） |

各分支末步类型须相同 ``T``；结果按分支顺序写入 ``list[T]``。

### 4.10 字符串键下标 ``['key']`` / ``['u', 'v']``

| 项 | 规则 |
|----|------|
| **语法** | ``field['x']``；多键 ``field['u', 'v']``（逗号分隔，同 §4.6 多下标形态） |
| **引号** | 单引号或双引号；支持 ``\\``、``\\"``、``\\'``、``\\n`` 等转义 |
| **容器** | 当前上下文须为 ``dict[K,V]`` / ``frozendict[K,V]``（首版键为 **path 内字面量**） |
| **类型** | 值为 ``V``；多键各段经后续路径步后末步类型须相同 |
| **emit** | ``.__getitem__(PyStr("key"))``；多键多 ``append`` |
| **混用** | 同一 ``[]`` 内 **不可** 混用字符串键与整型/切片 |

### 4.11 可选链 ``?``（跳过不存在步）

| 项 | 规则 |
|----|------|
| **语法** | ``field?[0]``、``field?.name``、``data?['k']``、``data?['u', 'v']``（``?`` 紧接 ``[`` 或 ``.``） |
| **语义** | 若该步 **不存在**（list 越界、dict 缺键、``Optional`` 无值），**跳过整条选择链**（不 ``append``），不报错 |
| **list** | ``?[i]``：下标越界时跳过 |
| **dict** | ``?['k']``：``__contains__`` 为假时跳过 |
| **字段** | ``?.name``：接收者为 ``Optional[T]`` 且无值时跳过；普通 struct 字段仍静态存在 |
| **emit** | 对应步外包 ``if (guard) { … }`` |

### 4.12 根路径 ``.`` 前缀（receiver 字段）

| 项 | 规则 |
|----|------|
| **语法** | 从 **receiver 根** 进入 **第一个 struct 字段** 须写 ``.ident``；可选根字段 ``?.ident`` |
| **对比** | ``org.select(".teams[0].name")`` ✓；``org.select("teams[0].name")`` ✗（裸 ``teams``） |
| **例外** | ``list`` 根仍可直接 ``[-1]``、``{expr}``；投影 arm 内相对路径 **不** 强制首步 ``.`` |
| **emit** | 与原先 ``FieldStep`` 相同；仅解析层区分根/后缀 |

### 4.13 同链 ``:$`` 绑定与 ``$`` 引用

| 项 | 规则 |
|----|------|
| **绑定** | ``: $ident``（如 ``.teams[0]:$t``）快照当前上下文入绑定表，**不改变**线性 ctx |
| **引用** | ``$ident`` 从绑定表取 ctx 继续导航；可接 ``.field`` / ``[…]`` / ``{…}`` |
| **``;`` 分段** | 左段只绑定不 ``append``；右段为结果段并 ``append``；``;`` 左右**同属一条链** |
| **无 ``;``** | 允许 ``.teams[0]:$t.members[1].name``（绑定与结果同链） |
| **filter** | ``{…}`` 内 ``$t.field`` 等为**非路径根**引用：须来自同链**严格更早**步的 ``: $t``；desugar → ``_bind_t.field`` |
| **路径根** | ``$t`` 作为 ``RefStep`` 起头/续步：同样须已有同链祖先 ``: $t`` |
| **``;`` 右 + 根导航** | 右段首步为根 ``.field`` / ``[…]`` / ``{…}`` 时，**不可**引用左段 ``;`` 前的 ``$`` 绑定（含 filter 内 ``$t.field``） |
| **不做** | filter 内 ``$t[i]``；跨链 ``$``；无祖先绑定的 ``$t``；``;`` 右根导航 + 左段 ``$`` |

示例：

```python
org.select(".teams[0]:$t; $t.name")
org.select(".teams[0]:$t.members[1].name")
org.select(".teams[0]:$t.members{.score > $t.min_score}.name")
org.select(".teams[0]:$t; $t.(members[0].name, members[1].name)")
org.select(".teams[0]:$t; .teams[1].name")
# 非法：; 右从根走，filter 不可引用左段 $t
# org.select(".teams[0]:$t; .teams[0].members{.score > $t.min_score}.name")
```

### 4.14 同链作用域

| 项 | 规则 |
|----|------|
| **作用域** | ``$`` 绑定与使用须**同一条选择链**（同一 IIFE）；``;`` 右首步可为 ``$ident`` 或根 ``.field``，但根首步时左段 ``$`` **不可**再被引用 |
| **顶层 ``,``** | **禁止**（见 §4.9）；``[]`` / ``.(…)`` 内逗号仍合法 |
| **``;`` 右** | 首版 **禁止 ``,``**；多值用 ``.(…)`` 投影或多下标 ``[i,j]`` |
| **投影 arm** | **禁止** ``$`` |
| **IR** | ``SelectorChainPlan(bind_prefix, steps, post_steps)``；无 ``$``/``;`` 仍为 ``SelectorPlan`` |

### 4.15 后处理（``@sort`` / ``@group`` / ``@count``）

后处理 **直接后缀**在整条导航链末尾（**无** ``;`` 分隔）；``;`` 仍仅用于 ``:$`` / ``$`` 同链绑定。

```ebnf
path := nav_part post_ops?

post_ops := post_op post_ops?

post_op := sort_op | group_op | count_op

sort_op  := "@sort(" sort_keys ")"
sort_keys := sort_key ( "," sort_key )*
sort_key := "-"? expr          (* 无 "-" 升序；有 "-" 降序；无 asc/desc 关键字 *)

group_op := "@group(" expr ")"

count_op := "@count" | "@count(" expr ")"
```

| 后处理 | 输入 | 输出 | 说明 |
|--------|------|------|------|
| ``@sort(-.score, .name)`` | ``list[T]`` | ``list[T]`` | 多键 **字典序**；稳定插入排序；键为与 ``{filter}`` **同子集** 的 Py2Cpp 表达式（如 ``.score - $t.min_score``）；比较用 ``py_cmp`` / ``__cmp__`` |
| ``@group(.key)`` | ``list[T]`` | ``dict[K, list[T]]`` | 桶 **插入序** |
| ``@count`` | ``list[T]`` | ``int`` | 元素个数 |
| ``@count(.field)`` | ``list[T]`` | ``Counter[V]`` | 按字段值 **频数**（与先 ``@group(.field)`` 再数桶等价时，**直接**写 ``@count(.field)``） |

**合法组合**（左→右）：任意个 ``@sort`` → 可选 ``@group``（**末步**）；或任意个 ``@sort`` → 末步 ``@count``（无参或 ``@count(.f)``）。``@group`` 与 ``@count`` **不可** 同链串联。

**非法**（译期报错）：

- ``@group`` 后接 ``@sort`` / ``@count``（**不支持** ``@group@sort``、``@group@count``；桶大小/按键计数用 ``@count(.field)``）
- ``@count`` 后再接其它后处理（含 ``@group``）
- ``@group`` 重复；``@count`` 重复

**示例**：

```python
hits: list[Member] = team.select(".members{.score > 0}@sort(-.score, .name)")
n: int = org.select(".teams@count")
by: dict[str, list[Member]] = team.select(".members@group(.dept)")
freq: Counter[str] = team.select(".members@count(.dept)")
names: list[Member] = org.select(
  ".teams[0]:$t; $t.members{.score > $t.min_score}@sort(.name)",
)
# 方案 A：按父节点字段参与排序（须先 :$t 绑定，且整表共用一个父快照）
org.select(".teams[0]:$t.members{.score > 0}@sort($t.name, -.score, .name)")
org.select(".teams[0]:$t; $t.members{.score > 0}@sort($t.name, -.score, .name)")
```

**键表达式**（``@sort`` / ``@group`` / ``@count(key)``）与 §4.4 ``{filter}`` **同子集**：任意合法 Py2Cpp 表达式；``.field`` 表当前 **list 元素**；``$t.field`` 表同链更早 ``: $t`` 绑定（desugar → ``_bind_t``）；其它标识符为 ``select`` 调用点作用域变量。示例：

```python
team.select(".members@sort(.score - threshold)")
org.select(".teams[0]:$t; $t.members@sort(.score - $t.min_score, .name)")
```

**按父节点字段排序（方案 A）**

| 项 | 规则 |
|----|------|
| **前提** | 结果 ``list[T]`` 来自**单一**父上下文（如 ``.teams[i]:$t…members``）；``: $t`` 在进入 ``members`` **之前** |
| **写法** | ``@sort($t.min_score, .name)``、``@group($t.dept)`` 等与 filter 内 ``$t.field`` 相同 |
| **语义** | ``$t`` 为**一个** C++ 绑定变量；该链上所有元素共用同一父快照 |
| **限制** | ``..`` / 多 team 扁平合并进一条 ``list`` 时，**不能**用 ``$t`` 表达「每元素不同父」；须数据模型反指父节点或后续扩展 |
| **非法** | ``;`` 右从 receiver 根导航时，后处理内引用左段 ``$t``（与 filter 同禁） |

---

## 5. 译器行为

### 5.1 流水线

```text
obj.select(".teams[0].name")
        │
        ▼  call_emit: try_emit_select_inline
   parse_selector_literal(".teams[0].name") → SelectorPlan
   （含 ``{expr}`` 步时：子串 → Py2Cpp AST → 挂入 IR）
        │
        ▼  selector_types: TypeGraph walk + 校验 + post 折叠返回类型
   起点类型 ← receiver；逐步推导；``{expr}`` 在元素类型上 type-check；对照 LHS 注解
        │
        ▼  selector_emit: 按 backend 组合 + 后处理
   inline C++（无 select() 调用）
```

| 模块 | 路径 |
|------|------|
| 解析 | ``src/passes/selector_parse.py`` |
| 类型 | ``src/analysis/selector_types.py`` |
| 生成 | ``src/emit/selector_emit.py`` |
| 注册 | ``src/emit/call_emit.py``、``translator.visit_AnnAssign``；``TRANSLATOR_ONLY_METHODS`` 含 ``"select"`` |

**不** bootstrap 生成 ``select`` 的 ``.inl``；**不**手改 ``generated/``。

### 5.2 与真实 ``select`` 方法冲突

对齐 ``assign``（``is_translator_only_method``）：

- 类**未**声明 ``select``，或仅为 ``pass`` / ``...`` → **译期专用**，内联。
- 类有 **真实方法体** 的 ``def select(self, …)`` → 生成 C++，**不**走内联（与 ``list_iterator.assign`` 同理）。

### 5.3 返回类型（恒 ``list[T]``）

| 路径形态 | ``T`` | emit 策略 |
|----------|-------|-----------|
| 末步标量/单对象（``teams[0].name``、``[-1]``） | 末步元素类型 | IIFE + 单次 ``append`` |
| 末步 ``list`` 字段（``teams``） | 元素类型 | ``for`` 枚举 + ``append`` |
| ``[lo:hi]`` / ``{expr}`` | 元素类型 | ``for`` + 可选 ``if`` + ``append`` |

左侧注解 **须** 为 ``list[T]``；与路径推导的 ``T`` 不一致 → ``TranslationError``。

**无左侧注解**（AnnAssign 场景）→ **翻译期报错**（G1）。

Json backend（G2）仍走 ``list[T]``；lazy 读在 ``append`` 前按需 ``read_*`` 字段。

---

## 6. TypeGraph

**单一真相源**：``ClassInfo.field_types``、``dataclass_field_specs``（``expand_dataclass`` / ``@serializable`` 已填充）。

```text
TypeNode :=
  | Scalar
  | Struct(ClassInfo)
  | List(elem: TypeNode)
  | Dict(key, value)   # select 首版不支持动态键步
  | Union              # 暂不支持路径分支
```

**起点规则**：

| receiver | 起点 |
|----------|------|
| ``JsonDocument[T]`` / ``JsonDocCursor[T]`` | ``T`` |
| ``Org``（dataclass） | ``Org`` |
| ``list[U]`` | 容器元素 ``U``（路径常 ``[-1]`` / ``[i]`` 起） |

---

## 7. 分期实现

| 阶段 | 交付 | 路径子集 | 测试 |
|------|------|----------|------|
| **G0** | ``selector_parse`` + IR + 译器单测 | 解析 | ``src/tests/test_selector_parse.py`` |
| **G1** | ``StructBackend`` + ``select`` 脱糖 | ``field``、``field[i]``、``a.b``；标量读 | ``test/lang/test_selector.py`` |
| **G2** | ``JsonNavigateBackend`` | 同 G1；与 ``doc.field[i]`` 对照 | ``test/serde/test_json_document.py`` |
| **G3** | ``SequenceBackend`` + 链式切换 | ``[-1]``、``[lo:hi]``、``{expr}``（完整 Py2Cpp 布尔表达式）→ ``list`` | 同上 |
| **G4** | 投影 ``.(a, b.c)`` + 后缀 | 多路径 ``list[T]``（arm 末步同型） | ``test/lang/test_selector.py`` |
| **G4+** | 通配 ``[:]``、步长、``..`` | 同上扩展 | ``test/lang/test_selector.py`` |
| **G5** | 新 ``Document`` 格式 | 注册 Backend | 不改路径语法 |

**G1 优先 Struct、G2 再接 Json** 的理由：先验证 **SelectorPlan + backend 分派** 与 ``assign`` 同级机制，再复用 ``JsonDocument`` 已有 navigate 叶子。

---

## 8. 错误语义（翻译期为主）

| 情况 | 行为 |
|------|------|
| 非字符串字面量 path | ``TranslationError`` |
| 未知字段 / 类型步不匹配 | ``TranslationError`` |
| 缺少结果类型注解 | ``TranslationError`` |
| receiver 不支持 select backend | ``TranslationError`` |
| 路径语法错误 | ``TranslationError``（附 path 片段） |
| ``{expr}`` 非合法 Py2Cpp / 非布尔 / 未知 ``.field`` | ``TranslationError`` |
| ``{expr}`` 引用调用点作用域内不存在的标识符 | ``TranslationError`` |
| 运行时越界 / JSON 缺键 | 与等价手写链相同（``IndexError`` / decoder ``fail``） |

---

## 9. 测试矩阵（实现后）

| 用例 | 文件 |
|------|------|
| 路径解析正负例（含 ``{expr}`` AST） | ``src/tests/test_selector_parse.py`` |
| ``@dataclass`` + ``select`` 内联（含 ``{expr}``） | ``test/lang/test_selector.py`` |
| 后处理 ``@sort`` / ``@group`` / ``@count`` | ``test/lang/test_selector_post.py`` |
| ``JsonDocument`` vs 静态链 vs ``load()`` | ``test/serde/test_json_document.py`` |
| 非字面量 path 译失败 | ``test/fail/test_selector_fail.py``（可选） |

结构：``TestCaseMixin`` + ``override def test``（[编码规范 §10](./编码规范.md#10-测试)）。

---

## 10. 文档与参考手册同步

**G1（含 ``:$`` / ``$`` / ``;`` 同链绑定）已同步**至项目主文档；**本文件**保留路径 DSL 详规（EBNF、分期、负例）：

| 文档 | 位置 |
|------|------|
| [参考手册.md](./参考手册.md) | [§7.9 译期路径选择](./参考手册.md#79-select译期路径选择)；Passes 表、``TRANSLATOR_ONLY_METHODS``、§14 FAQ |
| [编码规范.md](./编码规范.md) | [§7.5 ``select``](./编码规范.md#75-select路径选择)；§7.4 kwargs 表 |
| [serde-document-crud.md](./serde-document-crud.md) | §4 与静态链等价、``select`` 只读说明 |

后续 G2+ 落地时：更新上表摘要 + 本文 §7 分期表；**勿**只在 skill 内写 spec。

---

## 11. 暂不实现

- runtime 路径解释器 / C++ ``select`` 成员
- 非常量 path、path 拼接
- ``select("…") = value`` 写回
- ``dict`` 动态键、``Union`` 路径
- 模块级 ``select_str(obj, "…")`` 除非后续明确为糖（**主入口仍为** ``obj.select("…")``）

---

## 12. 设计决策记录

| 决策 | 选择 |
|------|------|
| 路径载体 | 仅字符串字面量 |
| 入口 API | ``receiver.select("…")``，译期魔法 |
| 协议 | **无** ``@protocol Selectable``；译器内置 backend |
| 返回 | 无后处理：**恒** ``list[T]``；有后处理：由末步推断（§4.15） |
| 格式无关 | IR + TypeGraph 通用；Backend 按类型注册 |
| 与 JSON 关系 | 复用 navigate/read 叶子，不绑死在 ``JsonDocument.select`` |
| 与 ``assign`` 关系 | 同级 ``TRANSLATOR_ONLY_METHODS``，无 C++ 成员 |
| 过滤 ``{…}`` | 大括号内为 **完整 Py2Cpp 表达式**（非 ``field op literal`` 专用语法）；译期 parse + 在元素类型上 type-check |
