**可空类型、条件访问与空值抑制的拟定语义**

2026-09-08。根据用户要求，新增 `a?.x`、`a: int?`、`a!`，配套纳入 `?[]`、`??`、`??=`。本文是设计方案，解析器与语义层尚未实现。对应[语法迁移对照表](./syntax-migration.md)和[自举实现方案](./parser-self-hosting.md)。

该语法族以 C# 14 已发布规则为参照，包括条件赋值；不采用后续预览特性。源码空值仍写 `None`，对应 C# 的 null。运算符的空值、短路、求值次数、转换及流分析语义按 C# 处理；Py2Cpp 已有的值/引用对象模型和 API 命名保留，不把所有 class、str、list 自动改为 .NET 引用类型。

| 现有形式/能力 | 拟定形式 | 语义 |
|---|---|---|
| `a: int \| None` 等可空注解 | `a: int?` | int 值或 None，零值仍是有效值 |
| `def f(x:T \| None) -> U \| None` | `def f(x:T?) -> U?:` | 参数和返回类型可使用后缀；按类型类别绑定 |
| 容器元素/容器本身可空 | `list[int?]`、`list[int]?`、`list[int?]?` | ? 只作用于紧邻左侧完整类型，三个类型不同 |
| Callable 的返回值/自身可空 | `(int) -> str?`、`((int) -> str)?` | 前者返回 str?；后者整个 Callable 可空，参数表与返回类型的 -> 按类型规则解析 |
| 手写接收者空值分支 | `a?.x` | a 为空返回 None，否则访问 x |
| 手写空值分支后调用 | `a?.method(args)` | a 为空时跳过调用及全部实参求值 |
| 手写空值分支后索引 | `a?[index]` | 只保护空接收者；非空时执行原索引规则 |
| 多级空值分支 | `a?.b?.c`、`a?.b?[i]` | 每个条件步骤独立保护相应接收者 |
| 无对应的纯静态抑制语法 | `a!`、`a!.x` | 只抑制该表达式的可空诊断，不检查、不解包、不改变运行时值 |
| 判空后取值或备选值 | `a ?? fallback` | 非空采用左值，否则才求值右侧 |
| 判空后初始化 | `a ??= create()` | 左侧为空才求值 RHS 并赋值；支持变量、可读写属性和下标 |
| 判空后写属性/下标 | `a?.x = make()`、`a?[i] = make()` | C# 14 条件赋值，接收者为空则连 RHS/索引都不求值 |
| 判空后复合赋值 | `a?.x += delta()` 等 | 仅在访问成立时读、计算、写；遵守成员及运算符合法性 |

值类型与引用类型必须分别建模。

| T 的类别 | `T?` 的含义 | 表示及类型检查 |
|---|---|---|
| 已知非可空值类型，如 int、bool、枚举、按值存储的实体 | NullableValue(T) | 存在标记 + T；不能仅借 T 的零值表示空 |
| 已有引用模型，如 @refcount 类和 @boxing 类 | T 上的可空引用注解 | 与 T 相同存储，不额外套 Optional；@boxing 仍受显式生命周期规则约束 |
| 已有按值存储的 str/list 等 | 按其 Py2Cpp 值类型模型处理 | 名称与 C# string/List 相似不等于引用类别相同 |
| 已有 Callable 或新 `(A,B) -> R` | 按值存储的 PyCallable | 整体 ? 形成 NullableValue(Callable)；现有空槽与 None 是不同状态 |
| 已有裸 FFI Pointer[T] | 保持原不安全指针模型 | 不把它冒充 C# 可空引用；新增 ?/?. 不自动扩展到裸指针 |
| 泛型形参 | 按声明处约束决定 | 不在模板实例化后无条件把所有 T? 改为 Optional[T] |

对于泛型，C# 的未约束 T? 是可空注解：T 实例化为非可空值类型 int 时仍是 int；声明处已知 T 为非可空值类型的约束才使 T? 表示 NullableValue(T)。引用约束对应可空引用，已可空实参不会再增加空层。实现须补齐类型类别约束信息，不能把 copyable、任意协议或“最终生成了 C++ 值”冒充 C# 的 struct 约束。具体约束拼法仍沿用独立的泛型设计，不在本项增加 where 语法。

新方言默认开启可空引用注解与流分析；旧源码兼容入口保留未标注状态，迁移时逐模块启用。引用 T/T? 的区别产生编译期可空警告，不增加构造/赋值时的运行时检查，也不构成可区分的重载签名；构建配置可把警告提升为错误。值类型 T/T? 是不同类型，缺失值的转换属于类型错误或显式取值时的运行时错误，不能通过抑制警告绕过。注解本身也不使未赋值局部变量自动初始化；可空字段/默认值的空状态与局部确定赋值分开处理。

新方言把 `T | None` 接受为 T? 的兼容拼法；显式 `Optional[T]` 继续作为现有 ADT 保留。旧方言原有 T|None 的表示和行为不偷偷改变。跨方言迁移必须经绑定后判断：当前 @refcount 的 T|None 已直接用 PyRefCount，@boxing 的 T|None 却可能是 PyOptional<T*>；后者的“没有值”与“有值但指针为空”不能被一次文本替换合并。旧 Optional 的成员、模式、自动取值和反射用法也需要检查；有语义差异时保留显式 Optional 或生成转换代码。

Callable 类型简写与现有 Callable 是同一类型，不改成 C# delegate 引用对象。PyCallable 已有未绑定处理器的空槽，bool(slot) 为 False，旧调用返回默认值或执行空操作（`templates/core/delegate.h:173` 起）；它仍可作为 NullableValue 中的“有值”载荷。`slot ?? fallback` 只在外层无值时选择 fallback，有值空槽不会触发；`slot!` 仍不解包可空值。`(A) -> R?` 修饰返回类型，`((A) -> R)?` 才修饰整个 callable，不能丢掉该层括号。

条件访问按一条完整访问链处理。

| 表达式 | 关键区别 |
|---|---|
| `a?.b.c` | a 为空跳过整条后续链；a 非空而 b 为空时，普通 .c 仍会失败 |
| `a?.b?.c` | a 与 b 都有独立的空值保护 |
| `(a?.b).c` | 括号终止前一条条件链，外部 .c 不再受其保护 |
| `getA()?.f(makeArg())` | getA 只执行一次；结果为空时 makeArg 不执行 |
| `a?[nextIndex()]` | a 为空时不求索引；a 非空时越界/缺失 key 异常仍传播 |
| `a?.x`，x 为非可空值类型 T | 结果提升为 T? |
| `a?.x`，x 已为 T? | 保持单层 T?，不产生双重 Nullable |
| `a?.x`，x 为引用类型 | 保持其引用存储，结果可能为空，流状态为 maybe-null |
| `a?.doWork()`，方法无返回值 | 条件调用语句；不构造 Nullable[void] |

?. 和 ?[] 不捕获 getter/方法/索引抛出的异常，不做成员是否存在的动态判断。项目 select 字符串 DSL 的 ? 会在部分索引场景跳过越界或缺失项，不能拿来实现主语言 C# 条件访问。

空值抑制与实际取值必须分开。

```text
count: int? = None
fallback: int = count ?? 0
stillNullable: int? = count!
bad: int = count!              # 类型错误：! 不将 int? 转成 int

# node 是引用模型的 Node?
value = node!.x                # 只抑制诊断；node 真为空时仍会空引用异常
```

`expr!` 仅影响该表达式的静态空状态，不把原变量的声明改成非空，不替代确定赋值检查，也不抑制无关类型错误。对于 NullableValue，显式读取现有风格的 `.value` 或明确转换才能取出 T；无值时抛错，`!` 本身不会做这一步。项目现有 Optional→T 自动 `.value__get()` 的路径不能用于实现 ! 或让新的 T? 隐式变成 T。C# 的后缀 ! 也不是前缀逻辑取反；主语言逻辑取反仍写 not。

引用值即使标为 T 或经 ! 抑制，运行时仍可能为空。为实现 C# 的正常解引用异常行为，编译器/运行库必须统一为普通引用成员访问提供空引用失败路径；不能直接依赖 C++ 裸指针解引用的未定义行为。这项规则属于所有普通引用访问，不是 ! 增加的检查。现有 refcount operator->/* 没有这项完整保证，需要单列运行库工作。

空合并不使用 Python 真值判断：0、False、空字符串和空容器都是非空值，`a ?? b` 不得展开成 `a or b`。?? 右结合，`a ?? b ?? c` 等价 `a ?? (b ?? c)`；结果类型按可空解包及已有隐式转换规则求解，不凭空生成一般联合类型。具体非可空值类型不能作为 ??/??= 左操作数；引用类型和符合 C# 规则的泛型形参另按对应规则检查。

??= 也右结合，并可在合法表达式位置返回所采用的值；不因此开放普通赋值表达式。对属性或下标使用 ??= 时，接收者、索引和 getter 均只求值一次，只有实际写入才执行 setter 与 __post_set__。C# 14 条件赋值以合法引用接收者为前提，不能向临时解包的 nullable 值类型副本写入；条件目标不成为可取引用的变量，不能传给 @ref 参数或绑定为引用。条件赋值仅作为语句使用，复合形式按同样规则处理；不引入项目原本没有的 ++/--。

与前一项 property 块联动：`a?.x = make()` 在 a 为空时跳过 make、__set__ 和 __post_set__；非空时按正常属性写入调用 setter，再在其正常返回后运行 hook 一次。`a?.x ??= make()` 还必须先读取 x，只有 x 为空时才写入。后端必须使用保存接收者/索引/值的明确求值计划，不能把有副作用的 AST 文本重复拼入条件和赋值。

可空值类型运算也须有独立规则，不能复用旧 Optional 的普通 union 运算。

| 运算 | C# 对应规则 |
|---|---|
| T 到 T? | 隐式构造有值状态 |
| T? 到 T | 不隐式转换；显式取值/转换在空时抛错 |
| 对已有值运算符的提升 | 通常任一操作数为空则结果为空，否则对底层值运算 |
| `< > <= >=` | 任一操作数为空，结果为 False |
| `==` / `!=` | 两边都空时相等，只有一边空时不等，否则比较底层值 |
| bool? 的 `&` / `\|` | 使用三值逻辑：False & None 为 False，True \| None 为 True；不能一概传播空 |
| bool? 用作条件 | 不隐式转换为 bool；显式判空、与 True 比较或 `flag ?? False` |

本项提升既有运算符时保留底层 Py2Cpp 数值规则，例如 /、//、% 的现有 Python 数值语义；不顺带增加 C# 的 &&、||、?: 或 CLR 装箱/动态反射。普通非可空表达式的 and/or 保持原语义。原有 Optional ADT 的模式匹配保留；新的 NullableValue 可用 None/非空值模式，不能因此把所有旧 Optional 模式无条件改写为可空引用模式。

解析与实现边界如下。

1. Lexer 区分 `?.`、`?[`、`??`、`??=`、`!=`、单独 `?`/`!`，数字扫描须允许 `1?.member` 正确分词后再由类型层拒绝；f-string 表达式内的后缀 ! 与 !s/!r/!a 转换分隔按模式处理，不能用全局替换。
2. 类型 parser 生成 NullableTypeSyntax(inner)，在绑定层区分可空值/引用注解/泛型注解。`T? @ref` 的 ? 先作用于 T；后续引用限定仍独立。容器/数组的 ? 放置必须保存完整嵌套结构，不接受直接 `int??` 作为双重可空类型。Callable 的 -> 比 ? 绑定更弱，区分返回可空值的 CallableTypeSyntax 与包裹整个 CallableTypeSyntax 的 NullableTypeSyntax。
3. Pratt 在成员/下标/调用层处理条件访问与后缀 !；?? 低于 or、高于条件表达式 `a if cond else b`，并右结合；??= 位于赋值层。箭头 lambda 与旧 lambda 同处最低表达式层，`x => a?.x ?? 0` 将访问/合并包含在函数体内，`fallback ?? (x => x)` 以括号界定 callable RHS。保存 ParenthesizedExpr 或等价边界，禁止过早擦除链外括号。
4. AST 使用 ConditionalAccessChain、NullSuppressExpr、CoalesceExpr、CoalesceAssignExpr 及 NullableTypeSyntax；语义层分别记录 NullableValueType、引用 NullabilityAnnotation 与表达式/CFG 的 NullState。
5. 流分析覆盖 `is None/is not None`、分支/循环合流、重新赋值、参数/返回、非空字段初始化；对重复 property 调用、别名和副作用采用可靠的失效规则。! 是局部抑制节点，不能直接覆盖整个变量后续状态。
6. lowering 建立单次求值、分支和结果提升，之后才接现有 C++ 后端；旧 CPython AST 无法直接表达新 token。lambda/箭头 lambda 函数体内的可空运算和临时变量必须留在调用体内，不能在创建 callable 时提前求值；表达式 AST 无法容纳的分支需内部函数体/HIR 支持。语义未完成前不得把 ? 全擦除、把 ! 改成取值、或在所有 T 上统一套 Optional 来宣称兼容。

验收应包含 0/False/空容器、空值比较及 bool? 真值表、嵌套访问链与括号、getter/索引/实参计数、异常传播、引用空解引用、! 不解包、??/??= 结合性、条件属性写入及 hook 次数、引用可空重载冲突、泛型 T? 分类和旧 Optional 跨方言转换。用等价的 C# 小程序作语义参照，项目特有数值/所有权行为另列断言；这些均为待实现验收项，本次没有新增编译器功能或运行测试。

官方参考：[条件访问及 C# 14 条件赋值](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/member-access-operators#null-conditional-operators--and-)；[可空值类型](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/builtin-types/nullable-value-types)；[可空引用与泛型](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/builtin-types/nullable-reference-types)；[后缀 !](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/null-forgiving)；[?? / ??=](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/null-coalescing-operator)。
