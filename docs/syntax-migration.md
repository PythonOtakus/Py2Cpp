# 现有语法与拟定迁移语法

初稿 2026-09-08，更新 2026-09-10。本文是语言表面语法、语义边界及兼容映射的唯一规范；前端架构、自举阶段、兼容桥与验收计划集中在[自有前端与自举编译器](./parser-self-hosting.md)。新语法仍是设计提案，lexer 高亮不表示编译器已经支持。

清单按源码语法族、编译器特殊入口、嵌入式 DSL 和模板语言枚举，普通标准库的每一个方法不算独立语法。表中“保持”表示保留当前表面写法及支持范围，不表示兼容全部 CPython 语义；“⏎”表示换行及相应缩进。表格用于查找映射，详细规则在各专节定义。

迁移分为 A、B 两批：A 为 enum/type enum、final、const、ref class；B 为 record、frozen、ordered、字段 optional、其余声明关键字、lazy class 单例、ref/lazy、属性与缓存、箭头 lambda、Callable 类型简写、可空运算、inline 静态分支、match 表达式及显式类型捕获。type match 采用独立入口的推荐方案，并提供其类型表达式形式；call/from 记录用户提出的多行回调方案，as 结果接收和其他块 lambda 入口仍保留候选状态。

迁移期通过旧方言入口接受旧写法；识别装饰器和标记须依据绑定身份，不能全局替换同名用户符号。重复的新旧标记诊断为重复声明。所有新增声明词及 inline/ref/lazy/call，和字段位置的 optional，都是上下文软关键字；普通赋值、属性访问和调用中的同名标识符保持可用。可空、缓存和 record 涉及新行为，不能视为纯文本替换。

<a id="declarations"></a>

## 声明与对象模型

声明种类的对照如下。

| 功能 | 当前写法 | 迁移后拟定写法 | 边界 |
|---|---|---|---|
| 普通类 | `class C:` | 保持 | 保持既有值对象模型 |
| 记录类型 | `@dataclass` ⏎ `class A:` | B：`record A:` | 固定派生构造、相等和展示，详见[record 规则](#records) |
| 冻结类/记录 | `@dataclass(frozen=True)` ⏎ `class A:` | B：`frozen class A:`、`frozen record A:` | 完整有效实例布局的字段均为 final；不等于 final class |
| 可排序记录 | `@dataclass(order=True)` ⏎ `class A:` | B：`ordered record A:` | 仅 record 合法，比较全部逻辑实例字段 |
| 引用类型 | `@refcount ⏎ class A:` | A：`ref class A:` | 保持引用计数对象模型，详见本节 |
| 延迟单例类 | 无对应类声明 | B：`lazy class A:` | 严格无参、首次构造、后续返回同一对象，见[单例规则](#lazy-class) |
| 继承与混入 | `class C(AMixin, BMixin, Base):` | 保持类头 | mixin 在前，至多一个实体基类 |
| 嵌套类 | `class Outer: ⏎ class Inner:` | 保持 | 不等同于普通函数闭包 |
| 普通枚举 | `@enum ⏎ class ModeEnum:` | A：`enum ModeEnum:` | 默认 int |
| 枚举底层类型 | `@enum ⏎ class WideEnum(int64):` | A：`enum WideEnum(int64):` | 仅 int/int64 |
| 枚举继承 | `@enum ⏎ class ChildEnum(ParentEnum):` | A：`enum ChildEnum(ParentEnum):` | 单继承并合并成员 |
| Flag | `@enum(flag=True) ⏎ class AccessFlag:` | A：`enum AccessFlag(flag=True):` | flag 是选项，不是新关键字 |
| Flag 底层/继承 | `@enum(flag=True) ⏎ class AccessFlag(int64):` | A：`enum AccessFlag(int64, flag=True):` | 父 Flag 的规则继续传递 |
| 枚举成员 | `Off = 0`、`On = ...` | 保持 | 普通首项须明确值；后续前值 +1；Flag 从 1 起取下一 2 的幂 |
| MRO 派生枚举 | `@enum.mro ⏎ class KindTypeEnum(base=Animal):` | A：`type enum KindTypeEnum(base=Animal):` | base 指派生根类型，保留 MRO 闭集收集与手动附加成员 |
| MRO 派生枚举继承 | `@enum.mro ⏎ class ChildTypeEnum(KindTypeEnum):` | A：`type enum ChildTypeEnum(KindTypeEnum):` | 单继承已有派生枚举；继承根类型，不可再次写 base= |
| 带载荷联合 | `@union ⏎ class MessageUnion:` | B：`union MessageUnion:` | 隐式 copyable，不与 boxing/refcount 叠加 |
| 泛型联合 | `@union ⏎ class BoxUnion[Value]:` | B：`union BoxUnion[Value]:` | 保留泛型与载荷类型 |
| 联合继承 | `@union ⏎ class ChildUnion(ParentUnion):` | B：`union ChildUnion(ParentUnion):` | 泛型继承保持当前同参要求 |
| 嵌套变体 | `@variant ⏎ class Move: ⏎ x: int` | B：`variant Move: ⏎ x: int` | union 内载荷声明 |
| 空变体 | `@variant ⏎ class Quit: ⏎ pass` | B：`variant Quit: ⏎ pass` | 不另加简写，保持现有块结构 |
| 变体字段模板 | 模块级 `@variant ⏎ class HasCode:` | B：模块级 `variant HasCode:` | 不能当普通实例类构造 |
| 变体字段继承 | `@variant ⏎ class Move(HasCode):` | B：`variant Move(HasCode):` | 基字段在前，合并载荷字段 |
| MRO 派生联合 | `@union.mro ⏎ class ErrorTypeUnion(base=Exception):` | B：`type union ErrorTypeUnion(base=Exception):` | base 指派生根类型；保留附加变体、嵌套 Enum 与转换能力 |
| 协议 | `@protocol ⏎ class SizedType:` | B：`protocol SizedType:` | 结构约束及 traits；不发射普通实体类，已登记协议另有运行时存储包装 |
| 泛型协议 | `@protocol ⏎ class IterableType[Element]:` | B：`protocol IterableType[Element]:` | 不改为运行时 Python Protocol |
| 混入 | `@mixin ⏎ class RowMixin:` | B：`mixin RowMixin:` | 方法、字段及常量编译期注入宿主 |
| 封闭类 | `@final ⏎ class C:` | A：`final class C:` | 禁止继承 |

属性列表允许附着于新增的 enum/union/protocol/mixin/variant 及 type enum/type union 声明。type 直接表达 MRO 派生模式，保留原 base=、声明体和派生根类型；不叠加普通 enum/union。type union 保持现有 base= 要求，不因 type enum 可继承就新增派生联合继承能力。FFI 中的 C enum/union 声明另见后表，不能通过名称后缀机械改成用户 enum/union。

解析器在声明起始位置识别 `type enum NAME` / `type union NAME`，并与现有 `type Name = T` 别名规则区分。`type enum = T`、`type union = T` 仍可表示名为 enum/union 的类型别名，`type(...)` 仍按表达式解析；这只定义语法分派，不新增运行时 type 内建支持。

本轮推荐的 `type match T:` 是另一条语句规则，`type A[T] = T match { case ...: R, ... }` 是类型别名右侧的专用表达式：`type match = T` 仍是名为 match 的类型别名；根据别名头的 `=` 或泛型形参列表与匹配语句的主体/冒号分派，不依赖符号表判断。具体类型模式文法见后文。

`ref class A:` 是引用类型的规范声明，替代旧 `@refcount`：

```text
ref class A:
    value: int = 0

item: A = new()
other: A = item
```

A 的源码类型仍写 A 或 A[T]，存储使用既有引用计数包装；赋值/复制共享同一对象，不改成值对象复制，也不要求用户显式写 RefCount[A]。普通 `class A:` 保持原模型。泛型、继承、构造、析构及 final 等组合沿用现有 refcount 类的合法性检查；不因此允许与 boxing 或 union 等原本冲突的对象模型叠加。

类头的 ref 决定对象存储模型；注解中的 `ref T` 是对某个值槽的引用/借用，见[引用与惰性参数](#ref-parameters)。因此 `x: A` 已能共享引用对象，`x: ref A` 则额外引用持有 A 的槽，二者不同。可空的 `A?` 沿用[可空引用规则](#nullable)。对象模型约束 `T: refcount` 以及运行时 PyRefCount 等名称保持不变；本次只迁移类声明入口。旧 `@refcount` 仅在兼容入口映射到同一模型，不再列为新方言保留装饰器；`@refcount` 与 `ref class` 同写报重复。

<a id="records"></a>

## record、frozen 与 ordered

`record A:` 是数据类的新方言入口，不能带配置括号。它固定生成 `__init__`、`__eq__` 和 `__repr__`；`record(init=False, eq=False, repr=False)` 等写法一律非法。类内不得手写这三个方法，定制构造后的逻辑使用 `__post_init__`。用户可以手写 `__str__`；未写时，编译器为所有 record（包括 ref record）生成转发到 `__repr__` 的 `__str__`。`ordered record` 另外固定生成 `__cmp__`，因此不得手写 `__cmp__`。

```text
@serializable
frozen ordered record Point:
    x: int
    y: int


ordered record User:
    id: int
    name: str = "anonymous"
    optional label: str = ""

    def __post_init__(self) -> None:
        self.label = self.label or self.name

    def __str__(self) -> str:
        return f"User({self.id}, {self.name})"
```

普通 record 的非 optional 字段按声明顺序进入自动 `__init__`；有默认值的字段仍是构造参数，只是有默认实参。`optional name: T = value` 仅能出现在 record 的实例字段位置，必须有默认值，且只表示该字段不进入自动 `__init__` 参数表。每次构造独立求值其默认表达式。它仍是普通实例字段，参与 `__eq__`、`__repr__`、排序、序列化、反射和模式匹配。

`new(id=1, label="guest")` 先运行 record 的自动构造和 `__post_init__`，再把不属于自动构造形参的 `label` 写入实例；`assign(label=...)` 也可以后续覆盖 optional 字段。该顺序使 `__post_init__` 始终观察默认初始化后的对象。frozen 类型禁止 optional 字段和任何构造后字段写入。

`ordered` 只允许修饰 record。比较字段按一个实体 record 基类的逻辑字段、按源码顺序展开的 mixin 字段、当前 record 字段组成，包含 optional 字段；每个字段必须有合法的比较操作。静态成员、编译器缓存/同步槽及属性的实现槽不作为独立值字段重复加入这个序列。record 只能继承一个实体 record 基类，可同时使用 mixin；普通带实例字段的实体基类不能成为 record 基类。`ref record A:` 与 `final record A:` 合法，既有对象模型和封闭继承规则继续适用；`lazy record A:` 和 `ordered class A:` 均诊断。

`frozen` 可以修饰 class 或 record，且不同于禁止继承的 `final`。绑定完成后，它使完整有效实例布局成为 final：实体基类字段、mixin 注入字段、当前类字段及 property/descriptor 展开产生的真实用户存储都包含在内。由于 C++ 不能在派生类中把已声明的基类成员重新变为 const，frozen 类的实体基类必须也是 frozen，或完全没有实例字段。frozen 不递归冻结字段所指向的对象；它沿用 final 字段的受控只读访问语义。frozen 类拒绝可写实例 property、post-setter 和 descriptor setter；缓存、锁等编译器内部槽不属于用户实例布局，也不参与 record 的比较、展示、序列化或反射。

`@serializable` 保持为装饰器，按绑定到内建身份识别，适用于 record 和 union，不由 record 自动启用。它生成现有 JSON `serialize`/`deserialize` 协议；手写任一同名方法与装饰器冲突。反序列化缺少 record 字段时使用该字段的声明默认值；没有默认值时诊断缺字段，不能悄悄采用类型零值。

旧 `@dataclass` 和 `T @optional` 仅在旧方言兼容入口保留，继续使用其历史参数及语义；不能与 `record` 或前置 `optional` 混写。迁移工具必须按绑定和实际行为转换，尤其不能把旧的排序排除规则或 decorator 配置机械改成新方言。

保留的其他类级属性如下；它们可以与新声明组合，组合合法性沿用语义检查。

| 功能 | 当前写法 | 迁移后 | 语义 |
|---|---|---|---|
| 序列化 | `@serializable` | 保持 | record/union 派生 serialize/deserialize |
| 可复制 | `@copyable` | 保持 | 复制构造与赋值 |
| 不可复制 | `@uncopyable` | 保持 | 禁止复制，保持移动模型 |
| 裸堆对象 | `@boxing` | 保持 | 源码写 C，存储表示采用 C*；显式生命周期 |
| 元数据定义 | `@annotation`、`@annotation(inheritable=True, repeatable=False)` | 保持 | 可与 record 或 legacy dataclass 组合；不新建 annotation 关键字 |
| 描述符定义 | `@descriptor ⏎ class RangeVar[T]:` | 保持 | get/set 内联；不新建 descriptor 关键字 |
| 原生实现 | `@native ⏎ class C:` | 保持 | C++/FFI/模板提供实现 |
| C++ 名称映射 | `@native_name("CppName")`、`@native_name("prefix_*")` | 保持 | 类/模块函数的外部命名 |
| 开放元数据 | `@TagMeta`、`@TagMeta(...)` | 保持 | 同样适用于合法的方法/声明位置 |

<a id="lazy-class"></a>

## lazy class 延迟单例

`lazy class A:` 声明只在首次构造时初始化的单例类。它隐含 [ref 引用对象模型](#declarations)，同时增加独立的单例构造策略；类型仍写 A，不需要用户另写 RefCount[A]。后续所有成功的构造调用都返回同一对象，不重新执行字段初始化或 `__init__`。

```text
lazy class A:
    value: int = 0

    def __init__(self) -> None:
        self.value = 1

first = A()           # 若尚未构造，在这里初始化单例
second = A()          # 与 first 共享同一对象
same: A = new()       # 有目标类型的构造入口也取得同一对象
print(first is second)  # True
print(first is same)    # True
first.value = 2       # second.value 和 same.value 随之变为 2
```

声明类、导入模块、引用类型、建立别名或写 `A?` 注解都不触发构造。首次实际执行 `A()` 或有 A 目标类型的 `new()` 时，在原调用位置完成正常字段初始化和构造链，成功后才返回实例。初始化副作用不移到模块加载、编译期或 callable 创建时；后续调用只取得已经完成的实例。`lazy class` 不使普通方法和属性自动缓存，参数 lazy 与成员 [声明缓存](#declaration-cache) 仍遵守各自规则。

无参是声明约束，不只是“调用时可以省略实参”：

| 位置 | 规则 |
|---|---|
| 构造声明 | 允许隐式无参构造或 `def __init__(self) -> None:`；除 self 外不能有参数 |
| 默认值/参数包 | `__init__(self, x: int = 0)`、`*args`、`**kwargs` 及带参重载均不合法，即使可用空实参调用 |
| 生成/继承构造 | 在 mixin、record/legacy dataclass 等展开及继承解析后检查完整有效构造链；任一环节有显式参数即不满足无参约束 |
| 调用入口 | 只接受空实参的 `A()`、`A[T]()` 及对应有目标类型的 `new()`；`A(1)`、`A(x=1)`、`A(*args)`、`A(**kwargs)` 全部拒绝，包括展开结果为空的情况 |
| 附加字段初始化 | `new(x=1)` 等构造后字段赋值简写也拒绝；获取实例后可按普通成员规则显式修改可写状态 |

每个具体类及每个闭合泛型特化各有一个实例身份。例如 A[int] 与 A[str] 各自单例；同一类型的别名、不同调用点和同一模块的重复导入共用一个槽。正常引用复制与赋值只共享该对象；复制构造、反序列化、原生工厂、低层分配等入口不得绕过单例策略制造第二个相同具体类型的独立对象。不能保证这一点的构造或派生能力在开放前明确拒绝，不通过复制缓存值实现 `A()`。

单例由进程强持有到退出；即使用户代码暂时不再持有引用，也不会销毁后重建。首版不提供单例 `clearCache`、reset 或可替换实例入口；进程退出时按受控生命周期清理。类中已有 lazy property/lazy def 的清理只影响对应成员缓存，不清除单例身份。

并发构造必须只发布一个完整实例。一个调用负责当前初始化，其他线程等待其结果，不运行第二份并行构造；这与 [lazy def](#declaration-cache) 允许并发未命中重复计算不同。同一线程在初始化期间再次构造同一个具体类，包括 A → B → A 的初始化依赖环，报告明确的构造重入错误，不返回半初始化对象，也不等待自身。字段初始化或构造抛错时，释放本次已构造资源、恢复未就绪状态并传播异常；随后调用可以重试。跨线程等待不得因初始化依赖环永久阻塞，实现需识别并报告这类循环。

单例策略不自动传给未标记的派生类：普通派生类沿用其既有 ref 模型与构造规则；显式写 `lazy class Child(Base):` 才为 Child 建立独立槽。构造派生对象时，基类初始化作用于同一个 self，不另取或构造 Base 的单例；整条有效构造链仍须无参。其余继承、抽象类可实例化性、对象模型互斥及访问规则沿用既有 ref 类限制。

类头 lazy 是无参数修饰词，采用 `lazy class` 的单例形式；函数的 `@LazyCache` 容量配置不适用于类声明。该语法及单例生命周期检查尚未实现，不能只删除 lazy 或加旧 `@refcount` 就视为已支持。

`lazy record A:` 一律非法。record 的固定自动构造与 lazy class 的严格无参单例入口不能通过把全部字段改 optional 或省略调用实参来兼容。

## 函数、方法与工厂

函数、方法及装饰工厂的对照如下。

| 功能 | 当前写法 | 迁移后拟定写法 | 边界 |
|---|---|---|---|
| 普通函数/方法 | `def f(...):` | 保持 | 无新 function 关键字 |
| 缓存函数/方法 | 无对应声明缓存 | B：`lazy def f(...):` | 默认不设容量上限，见[声明缓存](#declaration-cache) |
| 函数缓存容量 | 无对应入口 | B：`@LazyCache(128) ⏎ lazy def f(...):` | 装饰器限定最大完成条目数，见[声明缓存](#declaration-cache) |
| 静态缓存方法 | 无对应声明缓存 | B：`static lazy def f(...):` | [声明缓存](#declaration-cache) |
| 异步函数 | `async def f(...):` | 保持 | 现有协程状态机语义 |
| 封闭方法 | `@final ⏎ def f(self):` | A：`final def f(self):` | 隐含 virtual，不可 static |
| 静态方法 | `@staticmethod ⏎ def f(...):` | B：`static def f(...):` | 无 self，不等于 classmethod |
| 虚方法 | `@virtual ⏎ def f(self):` | B：`virtual def f(self):` | 可被覆盖 |
| 纯虚方法 | `@abstract ⏎ def f(self): ...` | B：`abstract def f(self): ...` | 体须省略号，隐含 virtual |
| 覆盖方法 | `@override ⏎ def f(self):` | B：`override def f(self):` | 保留继承签名检查 |
| 封闭覆盖 | `@override ⏎ @final ⏎ def f(self):` | B：`override final def f(self):` | 禁止继续覆盖 |
| 再声明纯虚 | `@abstract ⏎ @override ⏎ def f(self): ...` | B：`abstract override def f(self): ...` | 中间类保留纯虚要求 |
| 协议静态纯虚 | `@staticmethod ⏎ @abstract ⏎ def f(...): ...` | B：协议内 `static abstract def f(...): ...` | 编译期契约 |
| 协议静态虚契约 | `@staticmethod ⏎ @virtual ⏎ def f(...):` | B：协议内 `static virtual def f(...):` | 当前可写函数体，但只提取签名/探测实现类，不提供默认继承实现；实体类禁止 static virtual |
| 实现静态契约 | `@staticmethod ⏎ @override ⏎ def f(...):` | B：`static override def f(...):` | 编译期绑定，不产生静态虚表 |
| 只读成员方法 | `@immutable ⏎ def f(self):` | 保持 | C++ const this，不是 final |
| 结果式异常 | `@noexcept ⏎ def f(...) -> T:` | 保持 | 对外 Result[T,E]；raise/return 改为 Err/Ok；不是单独 C++ noexcept 标签 |
| 重载 | 每个同名声明使用 `@overload` | 保持 | 有体生成实现，区别于 typing.overload |
| 多播委托类型 | `@delegate ⏎ def FuncDelegate[T](x:T) -> T: ...` | 保持 | 模块级类型声明，不是普通函数 |
| 原生函数/方法 | `@native ⏎ def f(...): ...` | 保持 | 实现不由该函数体产生；使用省略号 |
| 全局 C++ 调用绑定 | `@global_call`、`@global_call("py_*")` | 保持 | 不增加 extern/globalcall 语法 |
| 编译期包装工厂 | `@decorator ⏎ def repeat(...): ...` | 保持 | yield 表示调用被包装体；保留展开顺序 |
| 编译期上下文工厂 | `@context ⏎ def sample(...): ... yield ...` | 保持 | 顶层 yield 分隔进入和退出 |
| 应用工厂 | `@repeat`、`@repeat(3)`、`@sample(begin="x")` | 保持 | 编译期绑定实参，不开放任意运行时装饰器 |
| 工厂上下文应用 | `with sample:`、`with sample(...):`、`with obj.sample(...):` | 保持 | 单管理器，模块/实例工厂内联；多管理器、async with 不走该展开路径 |
| 工厂产值绑定 | `with sample(...) as x:`、`with obj.sample(...) as x:` | 保持 | 必须有顶层 yield value；简单名目标可采用工厂返回注解，其他目标沿用普通赋值限制 |
| 包装目标元数据 | `__func__.__name__` | 保持 | with 内为特定名称，不是动态函数对象 |

modifier 组合按语义矩阵检查，而非任意排列即可合法。final/virtual、final/abstract、final/static 等冲突保持；新的方法修饰符也不自动开放普通函数、局部变量或任意 static 字段的同名语义。

上下文工厂以顶层 yield 切分；完全没有 yield 的工厂用作装饰器时可按现有规则整段替换。只有嵌套 yield 时会切分失败，不应解释为“没有顶层 yield 就一律回退”。

## 字段、参数标记与访问器对照

字段、参数标记与属性访问器如下。

| 功能 | 当前写法 | 迁移后拟定写法 | 边界 |
|---|---|---|---|
| 实例字段 | 类体 `x: T`、`x: T = v` | 保持 | 有默认值仍是实例字段 |
| 构造内字段赋值 | `self.x = v`、允许位置的 `self.x: T = v` | 保持 | 静态字段收集与类型规则保持 |
| 类级常量 | `x: T @const = v` | A：`const x: T = v` | static constexpr；当前仅支持部分字面量/标量属性初始化 |
| 实例只读字段 | `x: T @final`、`x: T @final = v` | A：`final x: T`、`final x: T = v` | 仍须各构造完整初始化；不新增局部 final |
| 无注解类体常量 | `_testTag = 1` 等既有标量形式 | 保持 | 与带注解实例默认字段区分 |
| 线程局部字段 | `x: T @thread_local = v` | 保持 | 类静态线程存储 |
| 自动构造排除字段 | `x: T @optional = v` | B：`optional x: T = v` | 仅 record 实例字段；必须有默认值，不进生成的构造形参，仍参与相等、展示、排序、序列化、反射和模式匹配，也可 assign/new 覆盖 |
| 引用参数 | `def f(x: T @ref):` | B：`def f(x: ref T):` | 保持调用方值的可变引用 |
| 引用返回 | `def f(...) -> T @ref:` | B：`def f(...) -> ref T:` | 保持引用返回语义；悬垂引用诊断需补齐 |
| 引用绑定 | `x: T @ref = obj.field` | B：`x: ref T = obj.field` | 保持局部引用绑定，不改为值拷贝 |
| 惰性参数 | `def f(x: T @lazy = None):` | B：`def f(x: lazy T = None):` | 首次访问求值并在本次调用记忆；None 表示未传 supplier |
| 引用与惰性组合 | `T @ref @lazy` | B：参数 `lazy ref T` | 本次调用 memo 的引用，见[参数规则](#ref-parameters) |
| 字段元数据 | `x: T @Meta`、`x: T @Meta(...)` | 保持 | 开放注解 |
| 多标记 | `x: T @MetaA @MetaB(...)` | 保持 | 顺序及 repeatable 检查保持 |
| 字段描述符 | `x: T @RangeVar(0, 10) = v` | 保持 | 描述符参数与字段默认值分开 |
| 参数/返回描述符 | `def f(x:T @Desc(...)) -> U @Desc(...):` | 保持 | 入口/返回的验证与替换 |
| 元数据加描述符 | `T @Meta @Desc(...)` | 保持 | 不把全部标记折叠成单一限定符 |
| 字段只读访问器 | `x: T @property = v` | B：存储字段 + `property x:` 中的 `__get__`，或等价 `property def x(self) -> T:` | 保留默认值和只读接口；简写仍须保留存储字段，存储仍可变，区别于 final |
| 实例 getter | `@property ⏎ def x(self) -> T:` | B：`property x: ⏎ def __get__(self) -> T:`；仅 getter 可简写 `property def x(self) -> T:` | 函数体成为该属性的 getter；允许单行 suite 和返回类型推断 |
| 实例 setter | `@property.setter ⏎ def x(self, value:T):` | B：同一块内 `def __set__(self, value:T):` | setter 负责实际写入，编译器不再额外赋值 |
| 实例赋值后回调 | `@property.postsetter ⏎ def x(self, value:T):` | B：同一块内 `__get__` + `__set__` + `__post_set__` | 迁移工具补出旧语义隐含的存储和 getter/setter，原回调体放 __post_set__ |
| 字段回调简写 | `x:T @property.postsetter(cb1, cb2) = v` | B：存储字段 + property 块，回调依序放入 `__post_set__` | 保留初始化、回调接收者、0/1 参数及调用顺序 |
| 静态 getter | `@staticproperty ⏎ def x() -> T:` | B 配套建议：`static property x: ⏎ def __get__() -> T:`；仅 getter 可简写 `static property def x() -> T:` | 无 self/cls，保持静态访问 |
| 缓存只读属性 | 无对应声明缓存 | B：`lazy property x:`、`lazy property def x(self) -> T:` | [声明缓存](#declaration-cache) |
| 静态缓存属性 | 无对应声明缓存 | B：`static lazy property x:`、`static lazy property def x() -> T:` | [声明缓存](#declaration-cache) |
| 静态 setter | `@staticproperty.setter ⏎ def x(value:T):` | 同一静态块内 `def __set__(value:T):` | 承接旧静态访问器语义 |
| 静态赋值后回调 | `@staticproperty.postsetter ⏎ def x(value:T):` | 同一静态块内 `__get__` + `__set__` + `__post_set__` | 补出原有静态存储/赋值，回调体迁入 __post_set__ |
| 静态字段回调简写 | `x:T @staticproperty.postsetter(cb) = v` | 静态存储 + `static property x:` 块 | 保留原静态初始化和回调，不将实例字段默认值误改为静态字段 |
| 访问器存储槽 | `self.__value__`、`Self.__value__` | 保留兼容引用；新块可直接访问显式存储，如 `self._x` | 仅对应访问器/描述符上下文；不由属性名自动猜测 _x |
| 原生字段名 | `x:T @native_name("c_field")` | 保持 | FFI 与名称映射元信息 |

const 初始化目前不等于任意常量求值，`1 + 2` 等不能因为新拼法自动获得支持。final 的现有构造提取主要处理顶层赋值，完整控制流确定赋值另行实现。新 frozen 的完整布局检查在 record/property/descriptor/mixin 展开后进行，拒绝 optional、可写 property、post-setter 和 descriptor setter；旧 `T @final @optional` 等字段标记限制仅留在旧方言兼容规则中。旧 postsetter 与手写 getter/setter 互斥只是旧入口规则；新 property 块明确允许 __get__/__set__/__post_set__ 共存，不沿用该互斥检查。

<a id="ref-parameters"></a>

## 引用与惰性参数

```text
def f(x: lazy int, y: ref str):
    y += str(x + x)

def nameRef(name: ref str) -> ref str:
    return name

type RefReader = (ref str) -> int

def useFactory(factory: lazy (() -> int)) -> int:
    return factory()

def localMemo(value: lazy ref int = 10) -> int:
    slot: ref int = value
    slot += 1
    return value
```

ref/lazy 是上下文软关键字；普通 `ref = value`、`lazy(...)`、`obj.lazy` 等名称用途保持。在类型/参数前缀位置识别 ref T、lazy T，组合规范写 lazy ref T；重复修饰和反序 ref lazy T 均诊断，不靠任意排列推断含义。参数 lazy 是求值策略，不是可放入任意字段、容器元素或返回位置的通用 Lazy[T] 值类型。ref 继续只用于原有合法位置，不因前缀拼法新增引用成员存储或任意容器引用元素。

类型前缀与可空后缀、Callable 的绑定顺序统一见[Callable 类型](#callable-types)。

开放元数据仍写在类型后，例如 `x: ref T @Meta`；描述符和对象存储标记保持各自作用。optional 是 record 字段名前缀，不是类型标记；迁移期旧 `T @optional` 与新前置写法不能叠写。旧 T @ref、T @lazy、T @ref @lazy 可经兼容入口规范化，不能与同一用途的新前缀叠写。用户自定义的同名标记须按绑定身份判断，不能做全局文本替换。

惰性参数保持现有行为，而非自动变成跨调用缓存。

- 普通实参表达式包装为零参 supplier，首次读取形参时执行，后续读取复用本次调用的值；未读取时不执行。成功计算前不标记就绪，失败仍沿原异常规则传播。
- 默认 None 表示未传 supplier；非 None 默认表达式在需要时通过默认 supplier 计算。缺席判断、同名惰性形参透传等沿用现有入口规则；可空返回 None 与没有 supplier 是两种状态。
- supplier 透传不等于共享不同函数调用帧中的 memo。当前实现每帧有独立初始化标记和缓存值，不承诺一条调用链只计算一次。
- 旧 `T @ref @lazy` 的 supplier 返回 T 值，callee 将其存入本地 memo，再返回该 memo 的 T&。因此 lazy ref T 不成为调用者变量的别名，引用也不能逃逸出 memo 的生命期；T 本身是 refcount 等共享对象时，其普通值复制仍保留共享对象语义。现有后端没有完整的引用逃逸分析，这项悬垂引用诊断是需补齐的要求。

当前惰性参数要求缓存值可默认构造并赋值，迁移拼法不自动解除这一限制。

lazy ref 写入应作用于本地 memo；当前直接赋值/增量赋值路径尚未接通，开放前应诊断。上述 localMemo 先读取 value、绑定其 memo，再通过 slot 修改。

<a id="properties"></a>

## 属性

property 块的拟定完整形态如下；示例中类型由已声明的 `_x` 推导，也可以显式写访问器注解。

```text
class Counter:
    _x: int = 0

    property x:
        def __get__(self):
            return self._x

        def __set__(self, value):
            self._x = value

        def __post_set__(self, value):
            print(value)
```

属性块只在类成员声明上下文中识别，形式为 `property NAME:`；静态形式配套建议为 `static property NAME:`。块内可有 docstring 和访问器声明，三种访问器各至多一个；访问器名称使用双下划线，属于该属性的局部作用域，不是普通嵌套函数或宿主类的 descriptor 方法。`property = value`、`obj.property` 和迁移期的旧装饰器仍按对应规则处理。

仅含 getter 的属性允许 `property def NAME(self):` 简写。例如：

```text
class One:
    property def x(self): return 1
```

等价于：

```text
class One:
    property x:
        def __get__(self):
            return 1
```

简写沿用 def 的单行或缩进 suite，返回注解可省略并从 getter 推断；也可以显式声明返回类型。静态只读属性相应使用 `static property def NAME():`：

```text
class Counter:
    _x: int = 0

    property def x(self) -> int:
        return self._x

    static property def title() -> str:
        return "Counter"
```

简写仍只在类成员上下文识别；实例 getter 只有接收者参数，静态 getter 没有 self/cls 或其他调用参数，限定规则与完整块相同。读取仍写 `obj.x` 或静态属性的 `Counter.title`；未加 lazy 时每次读取执行 getter，不自动生成存储字段、缓存或 const 语义。`obj.x()` 表示调用 getter 返回的值，仅在该值可调用时合法。

简写与完整块具有同一属性身份，不额外产生公开的同名方法，getter 的属性/效果信息遵循共同访问器规则。需要 setter 或 __post_set__ 时改用完整块；同名简写、完整块和旧属性声明不能拼接或重复声明。

| 块内声明/操作 | 拟定语义 |
|---|---|
| `__get__(self)` | 读取 `obj.x` 时调用；缺少时不可读 |
| `__set__(self, value)` | 写入 `obj.x = expr` 时调用；缺少时不可写 |
| `__post_set__(self, value)` | 可选；要求同块有 __set__，在 setter 正常返回后调用一次 |
| 仅 getter | 只读属性，可用 property def 简写；不等于 backing field 为 final |
| 仅 setter | 只写属性，读操作给出明确诊断 |
| setter + hook | 合法组合；setter 抛错不运行 hook，hook 抛错不回滚已完成的写入 |
| 静态块 | 对应访问器无 self/cls，使用 Self 访问类成员 |

每次属性写入只求值一次接收者和 RHS，绑定本次赋值参数后执行 setter，再把该次赋值参数传给 hook；不会重读 getter 或为了回调重复执行 RHS。参数按项目既有类型/所有权规则传递，不承诺额外深拷贝；setter 消费或移动参数后仍需回调使用的情形必须由所有权检查明确处理。setter 提前正常 return 也应触发 hook。直接写 `self._x` 不触发属性 hook；assign/new 的属性写入通过同一 setter 路径触发一次。

属性值类型由 getter 的显式返回类型、setter/hook 的 value 注解、已知 backing field 与 getter 返回表达式共同约束；可推断时允许省略注解，set/post_set 默认返回 None。省略 value 注解不能使访问器变成隐式泛型；不足、冲突或循环推导须明确报错。这是新语义层需要完善的统一推断，不能把现有有限 getter 推断当成已经完整支持。普通 getter 的 ref 返回（旧 @ref）及对象存储模型等限定另行保留并检查兼容性，首版缓存属性拒绝 ref 返回。

旧字段属性迁移为块或 getter 简写时保留字段默认值、元数据、record/legacy dataclass 的构造参与规则及反射映射；生成的 backing field 不得占用已有名称，并在 frozen 类中计入有效实例布局。旧 postsetter 隐含的写入只保留一次，回调顺序不变；descriptor 的类级 __get__/__set__ 协议不改为属性块。

<a id="declaration-cache"></a>

## 声明缓存

本节定义只读属性和有实现的同步函数的声明缓存；它与参数 lazy 的单次调用 memo、[lazy class](#lazy-class) 的单例构造分别建模。

```text
class Report:
    source: str = "hello"

    lazy property summary:
        def __get__(self) -> str:
            return self.source + "!"

    lazy property def size(self) -> int:
        return len(self.source)

    static lazy property def title() -> str:
        return "Report"
```

首次读取 obj.summary 执行 getter，正常完成后缓存；再次读取使用缓存。每个实例/属性声明有独立槽，静态属性按具体类及泛型特化隔离。单行 `lazy property def answer(self): return 42` 同样合法，省略返回注解时沿用属性推断。slot 有独立状态，None、False、0、空字符串都可以是已缓存结果，不能以值的真值或 None 判断是否计算。

首版仅接受有实现的 getter；lazy property 不与 __set__/__post_set__ 混用，不能直接赋值覆盖缓存。修改 source 等普通字段不会自动使相关缓存失效。用 `del obj.summary` 或 `del Report.title` 显式清除对应 lazy property；目标接收者只求值一次，清除不读取 getter，尚未初始化时为空操作。下一次读取重新计算。这是针对缓存属性新增的删除操作，不开放普通字段删除或 property deleter。

缓存槽属于编译器内部存储，不参与 record 生成的构造实参、相等/排序、序列化或公共字段反射，不以用户可见的 backing field 占用名称。清除和首次初始化不能被当成修改用户的 final/frozen 字段；内部槽的可变性与用户对象的只读约束分开。源数据仍受既有可写性检查。

lazy def 的规则如下。

```text
lazy def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

@LazyCache(128)
lazy def formatValue(value: int, prefix: str = "value=") -> str:
    return prefix + str(value)

formatValue.clearCache()
```

函数在调用时正常执行，缓存命中仅跳过函数体。接收者、普通实参以及按既有规则需要求值的默认实参仍正常求值；不会因为标记 lazy def 就把所有实参变成惰性参数。零参数函数只有一个键。缓存未命中才计算函数体；命中更新最近使用次序，达到容量时淘汰最久未使用的已完成条目，淘汰后允许重算。

lazy 声明修饰词不接配置参数，不再接受 `lazy(maxsize=...) def`。未加容量装饰器的 lazy def 默认不设容量上限；需要限制时，在函数声明上方写 `@LazyCache(128)`，表示最多保存 128 个已完成条目，超限按 LRU 淘汰。`@LazyCache` 只接收一个编译期非负整数或 None 的位置参数，bool 不冒充整数；`@LazyCache(0)` 不保留完成结果，`@LazyCache(None)` 显式表示无界。首版不引入关键字配置、TTL、typed 或任意 key 回调。

`@LazyCache` 是绑定到 lazy def 的容量元数据，不单独使普通 def 变成缓存函数，也不作为运行时装饰器执行。每个缓存函数至多有一个该配置；重复、参数非法，或用于普通函数、property、class 等错误位置时诊断。按符号绑定身份识别这一内建配置，不误解释同名用户装饰器。静态方法采用 `@LazyCache(128)` 加 `static lazy def`；lazy property 保持单槽，lazy class 保持单例，都不接函数容量配置。普通 lazy 名称调用和参数类型中的分组，如 `factory: lazy (() -> int)`，仍按各自规则解析。

缓存按实际声明、重载和封闭泛型特化隔离。完成形参与默认值绑定后，按声明顺序构造键；f(1, b=2) 与 f(a=1, b=2) 绑定到同一声明及值时共享条目，不采用关键字书写顺序区分。首版支持固定参数签名；可变参数包、结构化 **kwargs 的键规范化另行实现。实例方法把缓存存于每个接收者，不把 self 放入全局键，也不要求 self 可 hash；实例字段变化不会自动失效，调用方应主动清理依赖旧状态的缓存。

自动键必须能够独立持有并满足 DictKeyType，且存留期间 hash/相等关系稳定。首版采用已支持的不可变稳定值及合法组合，不自动接纳可变 list/dict、裸指针或悬垂借用；哈希碰撞仍需相等判断。涉及自定义哈希/相等的类型须证明符合稳定无副作用的键契约或明确不支持，不能在缓存锁内任意调用可重入用户逻辑。复杂输入可以由用户编写接收稳定标识/内容摘要的包装函数；首版没有自动深拷贝或对象内容追踪。

清理使用 `f.clearCache()`、`obj.method.clearCache()` 或 `Class.method.clearCache()`，不接参数，清理后返回 None。这是编译器识别的声明操作，不执行函数体，不要求先实现完整的 Python 函数对象；只有已解析到缓存声明的目标拥有该入口，不给任意 Callable 或同名成员增加特权。实例方法只清理该接收者的对应缓存；尚无条目时为空操作，清理不改变容量策略，后续调用重新计算。泛型/重载目标须能静态确定具体声明和特化，存在歧义时诊断，不任意清空其他函数的缓存；跨特化清理、逐键删除和统计接口可另行增加。

缓存持有键与结果，寿命与所属实例或函数缓存一致。值对象复制/赋值时目标缓存为空；移动后源和目标的派生缓存均清除，以免复用依赖旧地址/旧状态的结果。ref class 的引用计数包装复制只是共享同一个对象，其缓存继续共享；销毁真实实例才销毁实例槽。缓存是派生状态，不是序列化内容。

缓存结果保持项目对象模型：可复制值结果按正常复制规则返回，refcount 对象以强引用持有并返回同一对象，后续读取可观察到对该对象的修改。不能把缓存中的唯一所有权值在首次返回时搬空，也不能以引用返回来绕过复制；首版拒绝 ref 返回、不可复制所有权结果及无可证明生命期的 boxing/裸借用结果。无值返回可缓存正常完成状态，用独立状态代替 void 存储。缓存强持有的对象仍遵守既有引用计数/循环引用规则，不自动变成弱引用。

失败、重入和并发要分别处理。

1. getter/函数普通异常不缓存，清理本次未完成状态后传播，下次访问可以重试。缓存插入或键构造失败也不得发布半初始化条目。项目 @noexcept 会把结果改写为 Result，缓存包装读取转换后的正文结果，只保存 Ok，Err 原样返回且不保存；不能把所有 Err 当作成功返回值永久记忆。正文的转换不覆盖外围缓存操作：公共缓存入口还须将键构造、查找、重入、结果复制和发布等阶段的可表示异常转换为 Err，错误类型 E 须覆盖这些缓存错误。该入口的错误转换及清理接通前拒绝 @noexcept 与声明缓存组合，无法表示所需错误类型时明确诊断。
2. 同线程递归访问正在计算的同一属性/同一函数键时抛出明确的缓存重入异常，不能等待自己；不同键的递归允许，因此上述 fibonacci 合法。普通声明沿异常路径传播；@noexcept 组合开放后，由上述公共缓存入口转换错误，不能假设正文转换会自动处理缓存重入。`@LazyCache(0)` 也不把同键重入误当成已完成结果。
3. 缓存元数据的更新有同步保护，函数体/getter 在锁外执行。并发未命中可以重复计算，不承诺全局只计算一次，也不替用户函数体、接收者或结果对象提供线程安全。重入跟踪区分执行线程，不能把其他线程正在计算直接当成递归错误。
4. 清理递增 generation。清理前已开始的计算可把结果返回给其调用者，但不得重新填入新一代缓存；失败、淘汰与清理均只销毁实际已构造的值。有限 LRU 的容量约束作用于已完成条目，执行中的计算跟踪独立保存。

声明缓存首版的组合范围固定如下。

| 组合 | 规则 |
|---|---|
| 有实现的同步模块函数、静态方法、实例方法 | 支持 lazy def；按上述范围隔离缓存 |
| @LazyCache(N) | 仅配置 lazy def 的容量，每个声明至多一个；无配置时不设容量上限 |
| final class 中的普通方法/只读属性 | 合法，封闭类本身不影响缓存 |
| ref 或 lazy 形参的缓存函数 | 首版拒绝；命中不能悄悄跳过引用写入，也不能为了做键提前强制惰性参数 |
| 缓存函数/属性的 ref 返回 | 拒绝；缓存失效或淘汰后不能留下借用 |
| virtual/abstract/override、隐含 virtual 的 final 方法 | 缓存包装与动态分派归属另行设计；首版拒绝，不破坏原覆盖检查 |
| async、generator、native、delegate、decorator/context 工厂 | 首版拒绝缓存声明，不能复用已消费的协程/迭代器或改变工厂展开 |
| @noexcept | 按转换后的 Result 只缓存 Ok；公共缓存入口的错误转换、E 覆盖及清理接通后才开放 |
| 用户注解与其他派生/效果 | 继续各自校验，不因 lazy 绕过不可复制、只读或生命周期约束 |

缓存与可空状态独立：`obj?.cached` 在空接收者上不启动 getter，`value ?? cached()` 仅在需要 RHS 时访问缓存；lambda 中的缓存访问发生在调用正文时。lazy 不证明结果永远非空或函数没有副作用；类型捕获得到的引用/可空限定继续参与键与结果合法性检查。

<a id="types"></a>

## 泛型与类型

新增 T?、Callable 简写及 ref 前缀按共同优先级解析，lazy 求值方式归参数声明而非通用类型。

| 功能 | 当前写法 | 迁移后 | 边界 |
|---|---|---|---|
| 标量类型 | `bool`、`byte`、`char`、`int`、`int16`、`int64`、`uint16`、`uint`、`uint64`、`uintptr`、`long`、`float`、`float64` | 保持 | 具体宽度与行为按项目类型 |
| 字符串/复数 | `str`、`bytes`、`utf8ptr`、`utf16ptr`、`complex[T]`、`complex128` | 保持 | 不是新增关键字 |
| 根对象类型 | `object` | 保持 | 内建非泛型类，映射 PyObject；不是任意目标类型的统一动态装箱类型，也不等同 Any |
| 容器类型 | `list[T]`、`dict[K,V]`、`set[T]`、`deque[T]`、`frozenlist[T]`、`frozendict[K,V]`、`frozenset[T]` | 保持 | 其他普通泛型库类型同一语法 |
| 普通类型别名 | `type Name = ExistingType` | 保持 | 已有 type 软关键字 |
| 泛型别名 | `type Map[K,V] = dict[K,V]` | 保持 | 普通别名默认类型参数尚未完整实现 |
| 类关联类型 | 类体 `type Item = int` | 保持 | 不允许以 `class Box[T]: type Element=T` 重命名泛型参数（S0605）；应写 `class Box[Element]:` 自动公开 |
| 协议关联类型要求 | 协议中 `type Element = ...` | 保持 | 要求宿主提供关联类型 |
| 类泛型参数 | `class Box[Element]:` | 保持 | Element 自动成为关联类型 |
| 函数/方法泛型参数 | `def f[T](x:T) -> T:` | 保持 | 静态实例化 |
| 类泛型默认值 | `class Counter[K, C = int]:` | 保持 | 已实现类默认实参 |
| 函数默认类型参数 | `def input[Element = str](...) -> Element:` | 保持已有范围 | 不承诺任意多参数默认推导已完整 |
| 显式泛型调用 | `f[int](x)`、`C[int](x)`、`C.method[int](x)` | 保持 | 与调用上下文的 new 规则协调 |
| 隐式泛型 | `def f(x):`、`def f(x: SomeProtocol):` | 保持 | 未注解/协议参数生成模板，不是 Any |
| 协议约束 | `T: ComparableType` | 保持 | 编译期约束 |
| 协议存储 | `x: SizedType`、`it: IteratorType[int]`，以及已登记协议的字段/返回类型 | 保持 | 可映射运行时擦除包装，范围由注册表决定；不能推广到所有协议，也不同于协议形参的隐式泛型 |
| 交集约束 | `T: ComparableType & DictKeyType` | 保持 | 类型约束交集 |
| oneof 约束 | `T: oneof[char, byte]` | 保持已有范围 | 候选简单类型名；至少两个；类/mixin/alias 与函数覆盖不同 |
| 混合约束 | `T: DictKeyType & oneof[int, str]` | 保持 | 至多一个 oneof |
| 对象模型约束 | `T: refcount`、`T: copyable`、`T: boxing` | 保持 | 对应标记与协议可组合；模型约束之间受互斥检查 |
| 值模板参数 | `class ModInt[T: IntegralType, Mod: T]:` | 保持 | 当前类参数类型为前面泛型名或 int |
| 常量模板默认值 | `class Buffer[T, N: int = 0]:` | 保持 | 不推定任意函数 NTTP 均支持 |
| 值模板实参 | `ModInt[int, 1000000007]`、`array[int, 16]` | 保持 | 与普通类型实参分别建模 |
| 泛型实参边界 | CPython AST 将 `A[T,U]`、`A[(T,U)]` 都表示为 tuple slice | B：两者保留为不同泛型应用 | 前者有两个外层实参 T/U；后者只有一个 `(T,U)` 元组类型实参，不能自动打包、解包或按声明形参数量猜测 |
| 类型捕获声明 | `def f[T, _U = ...](x:T):`，模式中使用 `_U` | B：`def f[T](x:T):`，模式中使用 `list[type U]` 等 | 捕获在模式位置显式声明，不进入公开泛型实参表；旧捕获形参仅 legacy 兼容 |
| 可变类型参数 | `def f[*Ts](*args: Ts):`、`class C[*Ts]:` | 保持 | 函数最多一个 TypeVarTuple |
| 元组类型 | `(int, str)`、`(T,)`、`(*Ts,)` | 保持 | 顶层注解规范使用此形式；嵌套 tuple[A,B] 可用 |
| 可空类型 | `T \| None`、`Optional[T]` | B：`T?`；新方言中 T\|None 为兼容拼法，显式 Optional[T] 保留 ADT | 值可空、引用注解、旧 Optional 必须区分；跨方言转换先检查语义 |
| 堆数组 | `T[:]`、`T[:, :]`、`T[:, :, :]` | 保持 | 1/2/3 维专用支持 |
| 栈数组 | `T[:N]`、`T[lo:hi]`、`T[:R,:C]`、`T[:D,:R,:C]` | 保持 | 尺寸须可在编译期确定 |
| 借用视图 | `span[T]`、`span2d[T]`、`span3d[T]` | 保持 | 与拥有存储的数组区分 |
| 切片对象类型 | `slice[T]`、`slice[T,U]` | 保持 | 单参数归一化到相同的双参数 |
| 指针 | `Pointer[T]`、`Pointer[Pointer[T]]` | 保持 | 不添加 *T、&T 新拼法 |
| C 函数指针 | `Function[[A,B],R]`、`Function[[],None]` | 保持 | 无闭包状态 |
| 可绑定调用类型 | `Callable[[A,B],R]` | B：`(A,B) -> R`；旧拼法继续接受 | 固定参数签名的 Callable，与 Function 和多播 delegate 不同 |
| 结果/迭代类型 | `Result[T,E]`、`IterResult[Y,R]` | 保持 | 普通泛型/union 类型应用 |
| 生成器/协程类型 | `GeneratorType[Y,S,R]`、`CoroutineType[Y,S,R]`、`AsyncGeneratorType[Y,S]` | 保持 | 参数意义按项目协议 |
| 协议与关联类型引用 | `IteratorType[T]`、`AwaitableType[T]`、`T.Element`、`Optional[T].Value` 等 | 保持 | 不逐一给每个库类型新增语法 |
| 引用计数/boxing 类的源码类型 | `Node`、`Node[T]` | 保持 | 由类模型决定包装；普通源码不再套 RefCount[Node]/Pointer[Node] |

<a id="generic-argument-boundaries"></a>

### 泛型实参边界

方括号中的逗号只分隔当前泛型应用的外层实参；括号中的逗号先形成一个元组类型。因此 `A[T, U]` 是两个实参的应用，`A[(T, U)]` 是一个元组类型实参的应用，`A[T,]` 是一个 T 实参，而 `A[(T,)]` 是一个一元元组类型实参。后两种边界同样必须保留。若声明的形参数量或约束不接受相应形状，绑定器报告该应用非法；它不会为了通过检查把 `A[T, U]` 改写成 `A[(T, U)]`，也不会反向拆开元组。

```text
generic_type        := type_primary "[" generic_argument ("," generic_argument)* [","] "]"
generic_argument    := type | compile_time_value_argument
parenthesized_type  := "(" type ")"
tuple_type          := "(" type "," [type ("," type)* [","]] ")"
```

原生 Syntax AST 为前者保存两个 `GenericApplyTypeSyntax.arguments`，为后者保存一个 `TupleTypeSyntax` 实参；绑定后的泛型 `TypeId` 也维持相同嵌套结构。纯分组 `(T)` 可以在绑定后归约为 T，但元组 `(T,)`、`(T,U)` 不能被擦除。`A[(T, U)]` 与显式 `A[tuple[T, U]]` 表示同一个单元组实参；这不改变其与 `A[T, U]` 的区别。

旧 CPython AST 的 `Subscript(slice=Tuple(...))` 和 `ast.unparse` 无法单独恢复外层圆括号。legacy adapter 只能在保存原始源文本、token/trivia 和 span 时重建该原生形状；缺少这些信息的 AST 输入必须诊断无法保真迁移，不能凭实参数目或 C++ 模板字符串猜测。

<a id="callable-types"></a>

## Callable 类型

Callable 类型新增 `(int, float) -> str`，等价于 `Callable[[int, float], str]`。它可用于变量/字段、参数、函数返回注解、类型别名和容器类型实参等类型位置。-> 连接参数类型表和返回类型；=> 定义 lambda 值，二者可组合使用。

```text
formatValue: (int, float) -> str = (a,b) => f"{a}:{b}"

def apply(fn: (int, float) -> str, a: int, b: float) -> str:
    return fn(a, b)

type Formatter = (int, float) -> str
type Transform[T, U] = (T) -> U
```

| 现有类型写法 | 拟定类型写法 | 含义 |
|---|---|---|
| `Callable[[], int]` | `() -> int` | 零参数，返回 int |
| `Callable[[int], str]` | `(int) -> str` 或 `(int,) -> str` | 单参数；参数类型表括号始终必需 |
| `Callable[[int, float], str]` | `(int, float) -> str` | 两个参数，返回 str |
| `Callable[[int], None]` | `(int) -> None` | 无值返回，沿用 None 拼法 |
| `Callable[[tuple[int, float]], str]` | `(tuple[int, float]) -> str` | 单个元组参数；与两个参数不同 |
| `Callable[[int], tuple[str, float]]` | `(int) -> (str, float)` | 返回元组 |
| `Callable[[int], Callable[[float], str]]` | `(int) -> (float) -> str` | 返回另一个 Callable，-> 右结合 |
| `Callable[[Callable[[int], float]], str]` | `((int) -> float) -> str` | 接收一个 Callable 参数 |
| `list[Callable[[int], str]]` | `list[(int) -> str]` | Callable 作为容器元素类型 |
| `Callable[[T], U]` | `(T) -> U` | T/U 由外层泛型声明绑定，不在此声明新类型形参 |

类型参数表由类型构成，零项写 ()，一项或多项都保留括号，非空表允许尾逗号。首版保持固定参数数目；不增加参数名、默认值、...、ParamSpec 或任意参数包语义。`int -> str`、`(x: int) -> str` 和 `(...) -> str` 不属于本次语法。能表达高阶类型不等于当前后端已支持任意嵌套/逃逸 lambda；类型表示与值的构造、调用分别验收。

拟定类型文法及消歧规则如下。

```text
callable_type := "(" [type ("," type)* [","]] ")" "->" type
```

类型 parser 只在配对括号之后存在 -> 时把该组括号识别为参数类型表；否则沿用原分组/元组类型规则。因此 `(int, float)` 是元组类型，`(int, float) -> str` 是两个参数的 Callable 类型。泛型实参表同样保留这一层边界：`A[int, float]` 有两个实参，`A[(int, float)]` 有一个元组类型实参。返回侧递归调用类型 parser，`(A) -> (B) -> C` 等价 `(A) -> ((B) -> C)`；-> 比类型应用、后缀 ? 和返回侧 @ 标记绑定更弱，外围逗号、= 和声明冒号终止当前类型。`def make() -> (int) -> str:` 的第一个 -> 属于函数声明，余下部分是返回的 Callable 类型。

-> 不加入普通表达式二元运算符表。变量/字段/参数注解、函数返回和 type 别名 RHS 直接进入类型 parser；在已有显式泛型应用的类型实参位置也使用同一规则，外层名称是否确为泛型仍由绑定检查。`value = (int, float) -> str` 不创建运行时类型对象，应报告需要类型上下文；`value = (a,b) => ...` 才是 lambda 表达式。类型别名是该 Callable 类型的别名，不创建新的名义委托类型。

类型应用与后缀 ? 先于 ref/lazy 前缀绑定，前缀又比 -> 更紧：`ref T?` 表示对可空 T 槽的引用，`lazy ref T?` 再指定惰性求值。组合时必须保存括号的作用范围。

| 拟定写法 | 归属 |
|---|---|
| `(int?) -> str` | 参数值可空 |
| `(int) -> str?` | 返回值可空，Callable 本身不因该 ? 可空 |
| `((int) -> str)?` | Callable 整体可空 |
| `(ref T) -> R` | Callable 签名中的引用参数 |
| `(T) -> ref R` | Callable 签名中的引用返回 |
| `ref ((T) -> R)` | 对 Callable 值本身的引用 |
| 参数 `fn: lazy ((T) -> R)` | 延迟产生 Callable 值；其自身调用签名保持 (T) -> R |

ref 前缀比 -> 绑定更紧，`(T) -> ref R` 修饰返回类型 R；引用或延迟产生整个 Callable 时必须括起整个箭头类型。旧 `R @ref` 的兼容语法仍归返回类型。引用签名可由语法表示，实际可调用性还需沿用并验证 ABI/生命周期规则；例如现有空槽返回 `Ret()` 的实现无法直接用于 `Ret=T&`，不能只改类型拼法就宣称引用返回已完整。lazy 参数不是 Callable 的普通值参数类型，`(lazy T) -> R` 需要独立 supplier ABI 支持，未接通前诊断。

Callable 的值对象模型及有值空槽与 None 的区别，统一见[可空类型](#nullable)。

<a id="nullable"></a>

## 可空类型与空值运算

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
| 已有引用模型，如 ref class 和 @boxing 类 | T 上的可空引用注解 | 与 T 相同存储，不额外套 Optional；@boxing 仍受显式生命周期规则约束 |
| 已有按值存储的 str/list 等 | 按其 Py2Cpp 值类型模型处理 | 名称与 C# string/List 相似不等于引用类别相同 |
| 已有 Callable 或新 `(A,B) -> R` | 按值存储的 PyCallable | 整体 ? 形成 NullableValue(Callable)；现有空槽与 None 是不同状态 |
| 已有裸 FFI Pointer[T] | 保持原不安全指针模型 | 不把它冒充 C# 可空引用；新增 ?/?. 不自动扩展到裸指针 |
| 泛型形参 | 按声明处约束决定 | 不在模板实例化后无条件把所有 T? 改为 Optional[T] |

对于泛型，C# 的未约束 T? 是可空注解：T 实例化为非可空值类型 int 时仍是 int；声明处已知 T 为非可空值类型的约束才使 T? 表示 NullableValue(T)。引用约束对应可空引用，已可空实参不会再增加空层。实现须补齐类型类别约束信息，不能把 copyable、任意协议或“最终生成了 C++ 值”冒充 C# 的 struct 约束。具体约束拼法仍沿用独立的泛型设计，不在本项增加 where 语法。

新方言默认开启可空引用注解与流分析；旧源码兼容入口保留未标注状态，迁移时逐模块启用。引用 T/T? 的区别产生编译期可空警告，不增加构造/赋值时的运行时检查，也不构成可区分的重载签名；构建配置可把警告提升为错误。值类型 T/T? 是不同类型，缺失值的转换属于类型错误或显式取值时的运行时错误，不能通过抑制警告绕过。注解本身也不使未赋值局部变量自动初始化；可空字段/默认值的空状态与局部确定赋值分开处理。

新方言把 `T | None` 接受为 T? 的兼容拼法；显式 `Optional[T]` 继续作为现有 ADT 保留。旧方言原有 T|None 的表示和行为不偷偷改变。跨方言迁移必须经绑定后判断：当前 @refcount 的 T|None 已直接用 PyRefCount，@boxing 的 T|None 却可能是 PyOptional<T*>；后者的“没有值”与“有值但指针为空”不能被一次文本替换合并。旧 Optional 的成员、模式、自动取值和反射用法也需要检查；有语义差异时保留显式 Optional 或生成转换代码。

Callable 类型简写与现有 Callable 是同一按值类型，不改成 C# delegate 引用对象。PyCallable 已有未绑定处理器的空槽，bool(slot) 为 False，旧调用返回默认值或执行空操作；它仍可作为 NullableValue 中的“有值”载荷。`slot ?? fallback` 只在外层无值时选择 fallback，有值空槽不会触发；`slot!` 不解包可空值。返回可空与整体可空的括号区别见[Callable 类型](#callable-types)。

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

??= 也右结合，并可在合法表达式位置返回所采用的值；不因此开放普通赋值表达式。对属性或下标使用 ??= 时，接收者、索引和 getter 均只求值一次，只有实际写入才执行 setter 与 __post_set__。C# 14 条件赋值以合法引用接收者为前提，不能向临时解包的 nullable 值类型副本写入；条件目标不成为可取引用的变量，不能传给 ref 参数或绑定为引用。条件赋值仅作为语句使用，复合形式按同样规则处理；不引入项目原本没有的 ++/--。

与前一项 property 块联动：`a?.x = make()` 在 a 为空时跳过 make、__set__ 和 __post_set__；非空时按正常属性写入调用 setter，再在其正常返回后运行 hook 一次。`a?.x ??= make()` 还必须先读取 x，只有 x 为空时才写入。接收者、索引和值都保持单次求值。

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

? 只修饰紧邻左侧的完整类型；类型应用、ref/lazy 与 Callable 的优先级见[Callable 类型](#callable-types)，不接受直接 `int??` 作为双重可空类型。`??` 低于 or、高于条件表达式，右结合；match 表达式位于 or 与 ?? 之间，其完整结合表见[匹配表达式](#match-expression)。箭头 lambda 与旧 lambda 同处最低表达式层，因此 `x => a?.x ?? 0` 的访问/合并在调用体内执行；`fallback ?? (x => x)` 用括号限定 callable RHS。`??=` 位于赋值层。字符串或 f-string 的转换标记不因这些运算符改变含义。

官方参照：[条件访问及 C# 14 条件赋值](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/member-access-operators#null-conditional-operators--and-)；[可空值类型](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/builtin-types/nullable-value-types)；[可空引用与泛型](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/builtin-types/nullable-reference-types)；[后缀 !](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/null-forgiving)；[?? / ??=](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/null-coalescing-operator)。

## 类型条件与捕获

类型条件需要区分三套现有能力。

| 功能 | 当前写法 | 迁移后 | 边界 |
|---|---|---|---|
| 函数类型分支 | `if T is int: ... elif T is str: ... else: ...` | 保持 | 每个函数一条类型链，不能并列/嵌套多条 |
| 无 else 的类型分支 | `if T is int: ...` | 保持 | 未匹配的实例化产生静态断言；首分支为 is not 时仍要求 else |
| 类型集合分支 | `T in [int, float]`、`T not in {str, bool}` | 保持 | 编译期类型比较，非运行时类型对象集合 |
| 类型形状匹配 | `T is list[...]`、`T is dict[str, ...]` | 保持 | ... 为类型模式通配 |
| 类型捕获与守卫 | `T is list[_U] and _U in [int,float]` | B：`T is list[type U] and U in [int,float]` | 新方言不在函数头声明捕获；正向匹配成功后 U 才对后续 guard 和对应分支可见 |
| 正向析取 | `T is int or T is float` | 保持 | 当前 OR/AND 支持受限，不代表任意布尔式 |
| 负向类型判断 | `T is not int` | 保持已有范围 | 当前首分支/else 等限制保持 |
| 泛型类类型分支 | `class C[T]: ⏎ if T is int: ... else: ...` | 保持 | docstring 后首条；可跟共享成员；不能用于 protocol/enum/union |
| 条件类型别名 | `type Elem[T, _U = ...] = _U if T is list[_U] else T` | B：`type Elem[T] = U if T is list[type U] else T` | type U 为该正向 is 模式的局部捕获，不是调用方传入的泛型参数 |
| 条件别名链 | `A if T is P else B if T is Q else C` | 保持 | 当前语法必须有最终 else |
| 不匹配拒绝 | `type Only[T, _U = ...] = _U if T is list[_U] else Never` | B：`type Only[T] = U if T is list[type U] else Never` | 显式 Never，不采用无 else 的假语法 |
| 类型匹配表达式别名 | 无统一入口 | B：`type ElementOf[T] = T match { case list[type U]: U, case _: T }` | 花括号 case 按源码顺序选择一个结果类型；复用 `type match` 的类型模式、守卫与显式捕获 |
| 宏条件 | `if "WIN32" in __macro__: ...`、`elif "X" not in __macro__:` | 保持 | 宏名常量字符串；独立宏分支链 |

这些类型条件入口与新增 inline if、推荐的 type match 及其类型表达式分开保留；类型捕获改用显式 type 的同时不改变旧分派阶段。旧函数 type if 的具体类型优先/类型模式匹配、无 else 时的未覆盖诊断，以及类 type if 的位置/else 限制，不能通过加 inline 或改成 type match 机械迁移；宏条件的选择发生在 C++ 预处理阶段，也不等于前端已知的布尔常量。新静态分支的源序选择与实例剪枝规则见下文。

<a id="type-capture"></a>

## 显式类型捕获

类型捕获统一在模式中写 `type NAME`，不需要预先把捕获加到泛型参数列表：

```text
type ElementOf[T] = U if T is list[type U] else T
type ValueOf[T] = V if T is dict[str, type V] else Never
type InnerOf[T] = U if T is list[list[type U]] else T
type EntryOf[T] = (K, V) if T is dict[type K, type V] else Never
```

预期 `ElementOf[list[int]]` 为 int，`ElementOf[str]` 为 str，`InnerOf[list[list[float]]]` 为 float。U/K/V 是匹配得到的编译期类型，不是运行时变量，也不是调用方额外提供的泛型实参。

| 模式写法 | 含义 |
|---|---|
| `list[type U]` | 匹配 list 的类型构造，捕获其元素类型为 U |
| `dict[type K, type V]` | 捕获两个类型实参；K/V 各是单个类型 |
| `dict[str, list[type U]]` | 固定实参精确比较，捕获可嵌套在已有固定参数数目的类型构造中 |
| `list[U]`、`list[_U]` | 引用模式外已有类型参数/别名；名字不存在时报错，不按前缀或声明遗漏猜测捕获 |
| `type U` | 捕获整个主体类型；在 type match 语句或类型匹配表达式中可写 `case type U:` |

type NAME 只在类型模式上下文中激活：条件类型别名的正向 is 右侧、已有函数类型分支的正向模式，以及 type match 语句或类型匹配表达式的 case。普通注解 `value: list[type U]`、普通类型别名 `type X = list[type U]` 或值表达式不是捕获位置，应诊断；只有该名称已通过合法模式声明后，才能在对应成功分支的普通类型位置写 U。普通 match/inline match 的值捕获规则保持，inline if 的精确类型比较暂不因本项开放形状捕获。

主体及模式中的裸类型名称先在外层环境绑定；每个 type U 为匹配成功后的分支建立独立类型绑定。因此捕获可在成功分支中遮蔽外层同名 U，但不改写外层；`dict[type U, U]` 的第二个 U 只引用外层 U，无外层声明则报错，不回指刚捕获的 U。同一个模式备选内重复写 type U 报重复声明；若需要两个实参类型相等，在 type match 中使用 `dict[type K, type V] if K is V`。不同 case 或 OR 的不同备选可以各自声明同名捕获。

条件类型别名虽然把结果 U 写在 if 之前，绑定器仍须先分析条件模式，匹配成功后才在捕获环境中解析真分支结果类型。捕获只对该真分支有效，不能泄漏到 else、后续条件别名链或外层；else 中同名 U 若存在则是外层原有类型，否则为未声明名称。所有分支先解析并做必要结构检查，当前依赖的模式为 Dependent 时保留整个条件别名，不提前选 else；仅选中结果类型进入当前实例的语义求值，未声明名称不能冒充 Dependent。

条件别名首版仍沿用正向 `T is Pattern` 及带最终 else 的条件链，不顺带开放所有函数类型 if 条件。已有函数类型 if 中的正向匹配可把捕获提供给后续 and 守卫及成功体，例如 `if T is list[type U] and U in [int, float]:`；匹配失败或守卫假时丢弃本分支绑定，elif/else 不继承。首版不在 not、is not 或布尔 or 内引入新类型捕获；type match 的模式 OR 使用后文的独立绑定规则。

结构匹配先展开透明别名、检查别名依赖循环，再比较同一类型构造及固定实参；保留名义类型边界，不通过子类、协议满足或隐式转换寻找匹配。捕获保留完整类型及其可空注解、引用等限定，不仅是用于精确比较的类型身份。例如 `ElementOf[list[Node?]]` 必须得到 Node?，即使 Node/Node? 在既定精确身份比较中相同；`ElementOf[list[int?]]` 得到 int?，不自动取内层 int。

type U 首版只捕获一个类型槽；已支持的固定参数泛型可以递归嵌套。它不捕获整数 NTTP、数组维度或参数包，也不自动增加 `type U?` 的可空解构、构造器高阶捕获等规则。Callable、数组等结构可继续做已有的精确类型匹配；在其内部增加专用捕获节点须独立定义结构和验证。

旧源码兼容入口继续识别已由旧声明登记的 `_U = ...` 捕获参数；新方言不再以该列表或下划线命名触发隐式捕获。迁移必须依据实际的旧捕获声明绑定，逐分支产生显式 type U 及局部引用，并检查 else/分支外使用和名称冲突。旧捕获本已从调用类型参数中排除，迁移须保留公开实参数目、顺序和默认值；不能简单添加一个普通泛型 U，不能仅按 `_U` 文本前缀替换。旧函数分派优先级与无 else 诊断继续保留，不把语法迁移顺便改成 type match 的选择规则。

## 参数与调用

参数与调用形式如下。

| 功能 | 当前写法 | 迁移后 | 边界 |
|---|---|---|---|
| 参数/返回注解 | `def f(x:T, y:U) -> R:` | 保持 | 静态类型 |
| 默认参数 | `def f(x:T = value):` | 保持 | 按现有默认值发射规则 |
| 自动异构参数包 | `def f(*args):` | 保持 | 自动生成独立模板包 |
| 显式异构参数包 | `def f[*Ts](*args: Ts):` | 保持 | 不写 *args: *Ts |
| 同构数组参数包 | `def f(*args: int[:]):` | 保持 | 包为数组 |
| 固定长度展开 | mixin 中 `*axis: Vec[:Self._dim-1]` | 保持 | 专门展开机制；可以有后续固定参数 |
| 结构化关键字参数 | `def f(**kwargs: Options):` | 保持 | Options 字段对象，非动态字典 |
| 位置/命名调用 | `f(a, b)`、`f(x=a)`、`obj.f(x=a)` | 保持当前静态绑定范围 | 以可解析签名为前提 |
| 包展开调用 | `f(1, *args, 2)`、`f(*tupleVar)` | 保持 | 受同构包/模板包/定长 tuple 等路径限制 |
| 结构化转发 | `g(**kwargs)`、`self.assign(**opt)` | 保持 | 已知 Options 类型及简单绑定 |
| 类型推断构造 | `x:T = new(...)`、`return new(...)` | 保持 | 必须有目标类型上下文 |
| 字段/实参构造 | `self.x = new(...)`、`f(new(...))` | 保持 | 字段或形参类型可确定时 |
| 目标类型静态工厂 | `new.make(...)`、`new.zero` | 保持 | 目标类型由注解等提供 |
| 显式/当前类构造 | `C(...)`、`C[T](...)`、`Self(...)` | 保持允许位置 | 已有注解等位置仍遵守 new 的 strict 规则 |
| union 构造 | `x:U = new.Move(1,2)`；嵌入实参 `f(U.Move(1,2))` | 保持 | 不开放 new[T]() 或 new(Type) |
| 构造及附加字段初始化 | `new(positional, field=value)` | 保持 | 普通类匹配构造形参后，再写入剩余合法字段/property；record 的 optional 字段在自动构造和 __post_init__ 后写入，assign 同样可覆盖；frozen 不允许事后写入；[lazy class](#lazy-class) 仅接受 new() |
| 批量字段赋值 | `obj.assign(x=1, y=2)` | 保持 | 编译期展开、字段可写性检查 |
| 选项对象批量赋值 | `obj.assign(**opt)`，opt 来自 `**kwargs: Options` | 保持 | 选取 Options 与接收者共有的可写字段，不要求字段集合相同，不是任意动态 dict 展开 |
| 委托操作 | `d += handler`、`d -= handler`、`d(x)` | 保持 | 包括现有受限 lambda/绑定方法 |
| 无参数 lambda | `lambda: 1` | B：`() => 1` | 表达式体，调用时返回 1 |
| 单参数 lambda | `lambda x: 2*x` | B：`x => 2*x` 或 `(x) => 2*x` | 一个普通参数，可省略参数括号 |
| 多参数 lambda | `lambda a,b: a+b` | B：`(a,b) => a+b` | 参数括号必需，不是元组解构 |
| 旧 lambda 写法 | `lambda x: x + 1` | 继续接受，与箭头形式共用语义 | Callable/委托/聚合 key 等当前支持范围见下文 |

<a id="arrow-lambda"></a>

## 箭头 lambda

箭头 lambda 的参数和函数体规则如下；它是现有 lambda 的替代拼法，沿用 Py2Cpp 的参数绑定和对象模型。

需要语句体的长回调见[call/from](#call-from)；其他表达式块入口保留为[候选方案](#multiline-lambda-options)。本节定义已拟定的表达式体写法。

```text
one: () -> int = () => 1
twice: (int) -> int = x => 2*x
add: (int, int) -> int = (a,b) => a+b
```

首版参数表只包含普通名称：零参数必须写 ()；单参数可写 x 或 (x)；多参数必须写 (a,b)，括号内允许尾逗号。参数不能重名，未引用的参数仍是普通绑定，不引入特殊 discard 规则。暂不增加箭头参数注解、默认值、参数包、/、bare *、元组解构或 lambda 参数后的返回类型后缀；需要明确签名时使用外围 `(参数类型) -> 返回类型`（兼容 Callable）或委托类型，复杂函数保持 def。

=> 后为单个表达式，调用时才执行，结果作为返回值；void 目标仅在函数体符合既有无值调用规则时成立。换行沿用括号内隐式续行或反斜杠续行，=> 本身不打开缩进语句块。`=> {"x": x}` 中花括号仍是字典表达式；不引入语句块、return 语句、async 箭头或命名 def 的箭头函数体。

拟定文法的参数头为：

```text
arrow_lambda := NAME "=>" expression
              | "(" [NAME ("," NAME)* [","]] ")" "=>" expression
```

expression 在 lambda 层递归解析，故 => 与旧 lambda 同处最低表达式层并右结合。它不是任意左右操作数都可套用的二元运算符：左侧必须为上述参数头。在 ?? 等较高优先级操作数位置嵌入 lambda 时要求括号；普通赋值/??= 的合法 RHS 可以接收整个 lambda 表达式。未括起的逗号属于外围实参、容器或元组构造，不进入函数体；返回元组需显式括起。结合关系如下，表格只描述解析，不把所有组合标为现有后端能力。

| 写法 | 解析结果/边界 |
|---|---|
| `x => 2*x + 1` | `x => (2*x + 1)` |
| `x => a?.value ?? 0` | `x => (a?.value ?? 0)`，条件访问/合并在调用时执行 |
| `x => a!` | `x => (a!)`，! 仍只抑制可空分析 |
| `x => a if cond else b` | `x => (a if cond else b)` |
| `x => x match { case 0: 1, case _: 2 }` | 整个 match 表达式是 lambda 体；调用时才匹配和计算结果 |
| `x => y => x+y` | `x => (y => x+y)`；嵌套闭包语义另行验收 |
| `fallback ?? (x => x)` | 合并已有 callable 与 lambda；括号明确 lambda 边界 |
| `f(x => x+1, y)` | f 的两个实参，第一个是 lambda |
| `x => (x, x+1)` | lambda 体是显式括起的元组表达式 |
| `(x => x+1)(2)` | 语法上调用括起的 lambda；通用立即调用路径尚待实现 |

现有 lambda 仅在 Callable 变量、委托处理器、部分已有 Callable 目标签名的实参/字段初始化及 min/max key 等路径中受支持。参数和返回类型应由目标签名与表达式共同约束，类型信息不足时报错，不把当前 int 推断回退固化为语言规则。

创建 callable 时绑定其环境，正文在调用时执行。首期仅开放已验证的受限捕获；复制 callable 不延长引用捕获的局部变量或 self 的生命期。完整逃逸闭包、直接返回 lambda、立即调用和嵌套 lambda 尚缺通用支持，未接通的组合明确诊断。回调语句和未来块 lambda 也遵守这一生命期边界。

<a id="call-from"></a>

## call/from 多行回调

推荐把它定义为“带局部回调的调用语句”：签名声明 f，from 后写使用 f 的外层调用，冒号后的 suite 是 f 的函数体。相较于表达式中的缩进块，它在进入 suite 前已关闭全部调用括号，可以直接使用普通 Python NEWLINE/INDENT/DEDENT 和单行 suite，不需要改变括号内的续行规则。

```text
call f(x: int) -> int from s.sort(key=f):
    value = abs(x)
    if value > 100:
        return 100
    return value
```

理解顺序相当于下列概念展开，但实际绑定必须是编译器内部局部名字，不能直接用会覆盖外层变量的文本替换：

```text
def __callback(x: int) -> int:
    value = abs(x)
    if value > 100:
        return 100
    return value

s.sort(key=__callback)
```

sort 只是用户给出的接口例子，这种语法不专门识别 sort/key，也不凭语法方案扩展库接口。`from` 引导“使用这个回调的调用”，沿用用户提议；`call` 表示执行外层调用，不规定其内部必须同步调用 f。它适合 map/filter、排序、遍历和事件注册等接收回调的 API。

建议最小语义如下。

| 项目 | 建议规则 |
|---|---|
| 外层行为 | 创建一次回调值，再按普通调用规则求值 from 后的调用表达式一次 |
| 正文执行 | 正文属于 f；只有实际调用 f 才执行，可能零次、一次、多次或在未来执行 |
| 回调返回 | `-> int` 约束 f 的结果；正文 return 返回给调用 f 的代码 |
| 外层返回 | 不写结果接收时丢弃外层调用结果；不会自动返回外围函数 |
| f 的名字 | 只在 from 调用表达式及回调正文中可见；不泄漏到外围，也不覆盖外层同名绑定 |
| 正文局部变量 | 与普通函数一样属于回调函数作用域；不会成为调用者的局部变量 |
| 递归 | 正文可引用自身的 f，使用稳定声明身份绑定；不能依赖已退出的临时栈槽 |
| 控制流 | break/continue 仅可作用于回调内部循环；return 仅返回回调；不跨函数边界跳转 |
| 异常 | 回调异常按普通函数传播给其调用者，外层 API 可以处理；外层调用失败按普通异常规则传播 |
| 多回调 | 首版一条语句定义一个回调；其余回调使用已有函数/可调用值，后续可另行设计多声明形式 |

`pass` 可以作为单行 suite 被 parser 接受，但不能实现声明为返回 int 的函数；类型检查应报告缺少返回值。应写 `: return x` 或使用多行 return。无值回调可以写：

```text
call on_tick() -> None from register(on_tick): pass
```

名字局部化不限制回调对象的寿命：register 等 API 可能保存它。捕获的拥有值/共享对象要由回调环境持有，借用值须证明在每次调用时仍有效。若当前实现只能提供局部 `[&]` 捕获，必须在逃逸时诊断，而不能因为本语句结束就留下悬垂回调。调用方不保存回调的事实应由已知实现、分析或后续效果信息证明，不能仅凭方法名是 sort/visit 来假定。

递归引用不得通过环境强持有自身 callable 而制造引用计数环。回调正文捕获外层值、允许的 nonlocal 写入等与统一闭包规则保持一致，不能只因采用语句拼法就声称现有后端已具备完整支持。

from 的调用表达式按项目普通调用规则保留接收者、callee、各实参的求值次序，不重复计算 s 或其他有副作用的实参。回调创建属于本条语句的执行位置，不提升到外围条件/循环之外；在循环中执行本语句时，每次创建独立的回调实例。若后续开放函数对象创建期执行的参数默认值或捕获初始化，它们在进入 from 调用求值前执行，规则须与普通函数对象一致。

建议首版要求 from 后为普通调用表达式，回调名在其中按正常词法绑定使用；不引入隐式参数位置，也不在没有写 f 时自动补传。未使用 f 可以给出未使用回调提示；不按名称文本计数，因为嵌套作用域可能遮蔽 f。f 的形参只在正文可见，不能在 from 后被误当作已有实参变量；签名中的类型仍从原有类型环境解析。

为了接收外层调用结果，可以增加独立的可选扩展 `as NAME`，这是本方案的建议，尚未作为已采纳语法：

```text
call key(x: int) -> int from sorted(s, key=key) as result:
    return abs(x)

print(result)
```

这里 result 是 sorted 的返回值，`-> int` 仍只约束 key。result 按普通赋值作用域绑定，在外层调用正常完成后赋值；调用失败时本语句不执行该赋值，也不回滚调用已产生的副作用。新名字的未初始化状态须纳入确定赋值检查，回调不能借此无条件读取尚未产生的外层结果。首版 as 只允许单个名字，不同时扩展解构/属性目标；建议目标不得与本语句回调同名，以明确外围结果与临时函数的边界。无值 sort 接口通常不需要 as。

也可以先不增加结果接收，但那样这个语句主要服务忽略返回值的调用；它不能全面替代 map/filter 等表达式中的 lambda。独立可存储、可放入容器或 return 表达式的块函数，仍需普通函数定义或后续表达式块方案。现有 `x => expr` 保留为短回调写法。

拟定语句形式如下，as 为可选候选扩展：

```text
call_callback_stmt := "call" NAME parameters ["->" type]
                      "from" call_expression ["as" NAME] ":" suite
```

call 只在语句起始处的完整声明头中作为软关键字，普通 `call(...)`、`call = value`、`obj.call` 保持名称用途。签名中的返回 Callable 类型、参数注解及调用表达式内的冒号由各自文法处理，外层调用括号关闭后的冒号才引入普通单行或缩进 suite。不开放 `r = call ...` 这种表达式拼法。

这不代表普通 def 的所有参数能力已自动可用。显式类型优先，省略时由外层调用的 Callable 目标签名推断，无唯一签名或信息不足时诊断；建议首版固定签名、同步正文。ref/lazy 参数、泛型、默认值、参数包、async/generator 及 nonlocal 等随共同参数/闭包能力逐项开放，async 外层调用不自动 await。

<a id="multiline-lambda-options"></a>

## 其他多行 lambda 候选

通用块 lambda 的备选仍未冻结，不纳入当前箭头的已拟定语义。各方案均使用缩进语句体，不使用大括号代码块；call/from 优先服务调用现场，独立存储/return/容器位置仍需普通 def 或未来表达式方案。

| 候选 | 块头 | 保留的取舍 |
|---|---|---|
| A：箭头加冒号 | `x =>:` | 表达式方案中的优先建议；明确区分 `=> expr`，需换行、非空缩进 suite，不增单行块形式 |
| B：箭头后换行 | `x =>` 后换行缩进 | 简短，但与现有括号内表达式续行冲突，不按正文是否含 return 猜测种类 |
| C：扩展 lambda | `lambda x:` 后换行缩进 | 熟悉，但旧 `(lambda x: ⏎ compute(x))` 本来返回表达式值，不能静默改成无值语句体 |
| D：匿名 def 表达式 | `def(x: int) -> int:` | 便于完整签名；新增表达式入口，与箭头形成两套匿名函数形式 |
| E：call/from | `call f(x: int) -> int from operation(f):` | 采用普通语句 suite；作用域、结果接收与逃逸规则见上一节 |

如果以后采用 A，建议独立赋值 RHS/return 的完整末尾值可直接以块结束，其他嵌入位置统一为整个块 lambda 加圆括号。外围闭括号应独占退缩进行；DEDENT 结束正文，随后 `)`、`,` 才结束分组/实参。`return score,` 仍返回单元素元组，不能充当外围实参分隔符。表达式体隐式返回结果；语句体显式 return，末行表达式不隐式返回，正常结束的所有路径按目标返回类型检查。

```text
# 候选 A，并非已采纳语法
result = sorted(
    records,
    key=(row =>:
        score = row.base + row.bonus
        return max(score, 0)
    ),
)
```

这些表达式方案需要额外的括号内布局规则，不能仅因换行就改变既有 lambda/箭头表达式语义。语句体共用独立函数作用域、返回/跳转边界、捕获和所有权规则；A–C 首版普通名称参数头、D 的完整签名及后续 async/generator 等能力都须单独接通。布局与函数 HIR 的实现要求留在[自举方案](./parser-self-hosting.md)。

## 基础词法与模块

基础词法与模块形式保持 Python 外形。

| 功能 | 当前写法 | 迁移后 | 边界 |
|---|---|---|---|
| 源码编码 | UTF-8、当前 loader 去 BOM | UTF-8；明确 BOM 策略 | 不宣称任意编码声明可用 |
| 语句分块 | 缩进、冒号、分号分隔简单语句、括号内/反斜杠续行 | 保持 | 新 parser 实现相同 token 结构 |
| 注释/docstring | `# comment`、三引号文档字符串 | 保持 | 注释也供位置、重构与 strict 检查使用 |
| 字符串词法 | 单/双/三引号、转义、raw、相邻字符串拼接 | 保持当前有效范围 | 字面量结果仍是项目类型 |
| 字节字面量 | `b"abc"`、`br"abc"` 及对应三引号形式 | 保持 | 与 str/char 区分；按 bytes 或已支持数组上下文发射 |
| 数值字面量 | 十进制、0x/0o/0b、下划线、浮点指数、j 复数 | 保持 | 类型范围/溢出由静态语义处理 |
| 特殊常量 | `None`、`True`、`False`、特定位置的 `...` | 保持 | ... 不是通用运行时对象 |
| 模块导入 | `import pkg`、`import pkg.sub`、`import pkg as p` | 保持 | 顶层静态导入 |
| 符号导入 | `from pkg import X`、`from pkg import X as Y`、`from pkg import *` | 保持 | 星导入受 __all__/FFI 限制 |
| 相对导入 | `from .sub import X`、`from ..pkg import X` | 保持 | 静态模块发现 |
| 模块变量/导出 | `Name:T = value`、`__all__ = [...]` | 保持 | 不等同任意 Python 顶层执行语义 |
| 编译期源码信息 | `__name__`、`__file__`、`__line__`、`__debug__` | 保持 | 不新增关键字 |
| strict 指令 | `# py2cpp: strict-off` | 保持 | 风格规则开关不是类型/语义检查豁免 |

## 控制流、异常与异步

控制流、异常和异步语法如下。

| 功能 | 当前写法 | 迁移后 | 边界 |
|---|---|---|---|
| 普通分支 | `if/elif/else` | 保持 | 运行时分支 |
| 显式编译期分支 | 局部常量 if 折叠 | B：`inline if cond: ... elif cond2: ... else: ...` | [静态分支规则](#static-branches) |
| 显式编译期模式分支 | 专用 match/annotation 路径 | B：`inline match subject: ⏎ case pattern if guard: ...` | [inline match](#inline-match) |
| 显式类型匹配 | 类型 if | B 推荐：`type match T: ⏎ case list[int]: ... ⏎ case list[type U]: ...` | [type match](#type-match) |
| 类型匹配表达式 | 无统一入口 | B：`type A[T] = T match { case list[type U]: U, case _: T }` | [type match](#type-match) |
| 条件表达式 | `a if cond else b` | 保持 | 与条件类型别名分开 |
| 匹配表达式 | match 语句赋值/return | B：`x match { case 0: 1, case y if y > 0: 2, case _: 3 }` | [取值规则](#match-expression) |
| while | `while cond:` | 保持 | 静态可发射表达式 |
| for | `for x in xs:` | 保持 | 普通目标以简单名为主 |
| range 循环 | `for i in range(n):`、`for i in range(a,b):`、`for i in range(a,b,s):` | 保持 | 非循环表达式 range(...) 仍是库对象 |
| enumerate/zip | `for i,x in enumerate(xs):`、`for a,b in zip(xs,ys):` | 保持 | 专门平坦解构路径 |
| 循环 else | `for/while ... else:` | 保持 | 用户 break 抑制 else |
| 流程跳转 | `break`、`continue`、`return`、`return value` | 保持 | 所处循环/函数限制保持 |
| 空语句 | `pass` | 保持 | 原生/抽象桩仍要求 ... |
| 删除下标 | `del obj[i]`、允许容器的 `del obj[i:j]` | 保持 | 单下标目标；不是通用 del |
| 清除缓存属性 | 无对应入口 | B：`del obj.cachedProperty`、`del Class.cachedProperty` | 仅缓存属性，见[声明缓存](#declaration-cache) |
| 清除函数缓存 | 无对应入口 | B：`f.clearCache()`、`obj.method.clearCache()` | [声明缓存](#declaration-cache) |
| 通用上下文 | `with cm:`、`with cm as x:`、`with a as x, b as y:` | 保持 | as 为简单名；沿用项目 __exit__ ABI |
| 异常捕获 | `try/except/else/finally` | 保持 | finally 发射顺序与跳转交互保持 |
| 异常类型/绑定 | `except E:`、`except E as e:`、`except (A,B):`、`except:` | 保持 | 异常类型表达式有现有限制 |
| 异常组 | `except* E as group:` | 保持 | ExceptionGroup 分拆语义 |
| 抛出异常 | `raise E(...)`、`raise e` | 保持 | 已有上下文与异常类型要求；裸 raise 当前不支持 |
| 异常 cause | `raise E(...) from e`、`raise E(...) from None` | 保持 | 保留 cause 处理 |
| 生成器 | `yield x`、`x = yield y`、`yield from g()`、带值 return | 保持 | 状态机，受现有组合限制 |
| 协程 | `async def`、`await expr` | 保持 | 状态机与 Awaitable 协议 |
| 异步迭代 | `async for x in xs:` | 保持 | 目标简单名 |
| 异步生成器 | `async def` 内 `yield x` | 保持 | AsyncGeneratorType，不能 yield from |
| 异步上下文 | `async with cm as x:` | 保持已实现范围 | 正常路径已有；完整异常退出语义不能笼统宣称支持 |
| 编译期循环展开 | `for i in inlineRange(...):` | B：`inline for i in range(...):` | 语义不变：编译期完全展开；保持常量边界、宿主上下文及跳转限制 |
| 形参包循环 | `for x in args:`、`len(args)` | 保持 | 模板包循环不能 break/continue/else |
| OpenMP 循环 | `for i in prange(..., schedule="static", numThreads=0, chunkSize=0, th=0):` | 保持 | 与当前并行检查及开关一致 |

<a id="inline-for"></a>

## inline for

inline for 是 inlineRange 的替代拼法，迁移期仍接受旧写法。对应关系如下，循环体保持原样。

| 原写法 | 拟定写法 |
|---|---|
| `for i in inlineRange(stop):` | `inline for i in range(stop):` |
| `for i in inlineRange(start, stop):` | `inline for i in range(start, stop):` |
| `for i in inlineRange(start, stop, step):` | `inline for i in range(start, stop, step):` |

```text
inline for i in range(Self._dim):
    self[i] = 0

inline for i in range(Self._dim):
    inline for j in range(i + 1, Self._dim):
        self[i, j] = 0
```

两种写法都在编译期按范围顺序复制循环体，将循环索引的读取替换为常量，递归展开内层 inline 循环并折叠已有规则能确定的 if。范围边界在编译期求值；复制出的循环体仍在运行时按原顺序执行，副作用不在编译期执行。对应 inline 循环不生成运行时 for；循环体内原有普通循环保持普通循环。

本次语义不变，保留以下已实现范围和限制。

| 项目 | 保持的规则 |
|---|---|
| 调用形状 | range 后为 1–3 个位置参数，无关键字参数/星号展开；默认 start=0、step=1，stop 不包含在范围内 |
| 步长/空范围 | 支持正步长、负步长和空范围；step=0 在编译期报错 |
| 边界来源 | 整数字面量、外层展开循环变量、宿主类静态整数字段及 Self.field；沿用当前宿主常量读取范围 |
| 常量运算 | 现有求值器支持一元负号和 +、-、*、// 的嵌套，// 按向下取整；不自动增加任意 constexpr/函数调用或其他运算 |
| 循环目标 | 单个简单名称，含原有 _ 写法；不增加解构目标 |
| 控制流 | 不支持 for-else；break/continue 检查覆盖循环体完整子树，包括内嵌普通循环和常量死分支；return 沿用原语句规则 |
| 嵌套 | 不同索引名的展开循环可嵌套，内层范围可引用外层索引；运行时循环变量不能用作编译期边界 |
| 使用上下文 | 保留 mixin 贴入宿主和已有 ClassInfo 的类方法路径；不因此新增模块普通函数/顶层使用能力 |

当前常量读取只取类字段的整数字面量或负字面量初值，不能把任意 @const 初始化表达式都称为可求值；旧 isinstance(value, int) 实现还接受 bool，这属于兼容事实，不在本次拼法迁移中改变。当前替换仅按名称处理 Load，不建立独立迭代作用域，也不生成循环结束后的索引赋值。重新赋值索引、同名嵌套和闭包遮蔽存在原有绑定缺口，应独立诊断/修复并记录兼容影响；不能借迁移承诺普通 Python for 的循环后变量语义。

inline 是语句起始处紧邻 for、if 或 match 才激活的软关键字：`inline = value`、`obj.inline`、`inline(...)` 仍是普通名称用法。识别到 inline for 后提交到专用语句规则；新形式要求 `in range(...)`，此处 range 明确表示内建的整数范围 intrinsic，而非用户可替换的普通函数调用。普通 range 循环的名称处理不受影响，现有编译器实际按名称拼写识别 range/inlineRange 的事实须与未来完整的遮蔽检查区分。迁移工具只改已确认的旧 inlineRange 循环头，保留原实参、循环体、注释与位置，不替换任意同名文本。

本次不将 inline 泛化到任意 iterable、prange、推导式或 async for，也不增加 inline def；`inline for i in inlineRange(...)` 是重复标记。新旧入口使用相同的完全展开语义，不可移除 inline 后当普通运行时 range 循环。

<a id="static-branches"></a>

## inline if 与静态分支共用规则

inline if、inline match、type match 语句和类型匹配表达式共用本节的静态求值、待特化依赖、分支隔离和声明规则；各 match 入口只补充自己的模式规则。新增 inline if 写法为：

```text
inline if Self._dim == 2:
    self.update2D()
elif Self._dim == 3:
    self.update3D()
else:
    self.updateGeneric()

inline for i in range(Self._dim):
    inline if i == 0:
        self[i] = 1
    else:
        self[i] = 0
```

首行的 inline 作用于整条 if/elif/else 链，后续直接写 elif、else；不增加 inline elif、inline else。普通 if 链中不能以 inline elif 混入编译期条件，可在分支体内嵌套一条 inline if。inline if 自身支持多条、嵌套及与普通 if/inline for 组合；它是语句，不增加三元条件表达式的 inline 拼法。

| 规则 | 拟定语义 |
|---|---|
| 分支选择 | 按源码顺序求条件，选择首个为 True 的分支；后续 elif 条件不求值 |
| 无匹配 | 有 else 则选择 else；没有 else 则产生空语句序列，无隐含静态断言 |
| 条件类型 | 实际求得的结果必须是编译期 bool；`inline if 1:` 报错，不调用用户 __bool__ 或借用容器真值 |
| 尚依赖泛型/宿主 | 保存待特化条件，在对应类型/值实参、mixin 宿主或 inline 循环索引绑定后求值；实际实例生成代码前仍未知则报错 |
| 未选分支 | 仍须通过词法、语法及必要的结构检查；当前实例不展开、不作常规名称/成员解析与类型检查、不注册其中声明 |
| 选中分支 | 按原所在作用域插入，只保留该分支；不创建额外作用域，分支语句及副作用仍在原运行时位置执行 |
| 控制流 | return/break/continue 绑定到原函数/循环；仍受外层结构限制，inline if 不创建新的函数或循环 |

条件求值首版拟支持：bool/整数字面量、已绑定的编译期 const、宿主常量、inline for 索引、已绑定整数 NTTP；整数一元负号及 +、-、*、//，整数比较 ==、!=、<、<=、>、>=，布尔 not/and/or，以及已绑定类型的精确 `T is U` / `T is not U`。类型比较使用 TypeId 及透明别名展开，不比较类型名称字符串，不含类型形状匹配/捕获。标量运算按目标语言的类型、范围和除法规则，错误定位到条件表达式。not/and/or 的实际操作数须为 bool，and/or 保持短路；只有实际需要求值的子式才触发求值错误。

inline match 共用这套静态求值器，并补充 None、str、enum 静态值及同类别标量的 ==/!=、`is None` / `is not None`；同一扩展也供 inline if 条件使用。bool 与整数分开，enum 比较要求相同枚举 TypeId，TypeId 本身仍使用 is/is not；不调用用户 __eq__。主体、模式和守卫的完整边界见下文。inline for 的旧范围求值继续使用其兼容子集。

这是一组待实现的静态求值能力，不是对旧折叠器支持范围的描述，也不扩大 inline for 的边界运算子集。需要求值的子式若依赖运行时变量、对象属性 getter、用户函数调用或无编译期实现的运算，应报告不能在编译期求值；泛型未绑定与运行时依赖使用不同诊断。普通 if 的原真值语义保持，const 的合法初始化范围也不因本项自动扩大。尚未登记为可靠静态 intrinsic 的 hasattr/反射调用继续受限，不能用一个任意 CPython eval 实现。

设计目标覆盖函数/方法语句、普通类成员和模块声明位置；所选语句仍须满足该位置已有规则，不为 enum/protocol 等受限声明体增加任意语句。模块中的条件 import 只在选择后登记依赖；类中的条件字段/方法只进入当前有效成员集合，参与布局、record 生成、legacy dataclass 和反射。相同名称若只出现在互斥分支，不因未选声明报重复；与实际保留的其他声明冲突仍报错。函数中的局部绑定与返回类型检查以所选分支为准，未选分支不满足也不妨碍当前实例的确定赋值。未实例化泛型保存条件树，各特化有独立的有效声明集合。

声明条件只能依赖选择前独立可求的值/类型，如外层类型形参、宿主身份及无条件常量。若条件需要的常量、导入或反射成员集合反过来依赖受该条件控制的声明，报告依赖循环；不能先登记所有分支来获得条件值。受控导入、属性、record/legacy dataclass 与反射都只观察当前实例选中的声明。

本项与现有能力的兼容边界如下。

| 现有能力 | 与 inline if 的关系 |
|---|---|
| 普通常量 if 折叠 | 原入口保持；新 inline if 增加强制编译期求值与未选分支隔离，不能只删除 inline |
| inlineRange/inline for 内折叠 | 新节点必须先求条件再展开选中体；旧 `_flatten_stmt` 先遍历两个分支，不能原样接入 |
| inline for 的跳转限制 | 仍先扫描原循环体的 break/continue；`inline if False:` 包住 break 也不能绕过已约定的结构限制 |
| 旧函数/类 type if | 保留原分派语义；具体类型优先/模式匹配及无 else 的静态断言不改成新链的源序/no-op；迁移须逐例验证 |
| `if "X" in __macro__` | 保持现有 C++ #ifdef 路径；首版 inline if 不接受 __macro__。未来若加入，须显式提供目标构建宏环境并纳入依赖/缓存 |

## 表达式、容器与解包

表达式、容器与解包如下。

| 功能 | 当前写法 | 迁移后 | 边界 |
|---|---|---|---|
| 普通赋值 | `x = expr`、`x:T = expr`、`obj.x = expr`、`a[i] = expr` | 保持 | copy/move/final 等语义保持 |
| 链式赋值 | `a = b = expr` | 保留语法，单独完善语义 | 当前发射路径存在，但 RHS 调用可能重复执行；不可承诺 Python 单次求值/共享语义 |
| 平行赋值 | `a,b = b,a`、`a[i],a[j] = a[j],a[i]` | 保持 | 先求值 RHS 再写入目标 |
| 定长元组解包 | `a,b = tupleValue`、`a,*mid,z = tupleValue`、`a,*_,z = tupleValue` | 保持 | PyTuple，rest 仍是子 PyTuple |
| 丢弃结果 | `_ = expr`、`_:T = expr` | 保持 | 受静态类型上下文规则 |
| 增强赋值 | `+= -= *= /= //= %= **= <<= >>= &= ^= \|= @=` | 保持当前已实现类型组合 | 不承诺任意用户类均有所有 inplace 协议 |
| 算术 | `+ - * / // % **` | 保持 | /、//、% 不能改成错误的 C++ 数值语义 |
| 位运算 | `& \| ^ ~ << >>` | 保持 | 静态类型决定合法性 |
| 矩阵运算 | `a @ b` | 保持 | 表达式 MatMult，与类型 @ 标记区分 |
| 比较 | `== != < <= > >=`、`a < b <= c` | 保持写法 | 简单比较链已支持；中间表达式带副作用时可能重复求值，需另行修复 |
| 身份判断 | `is`、`is not` | 保持写法；新可空类型的 None 判断接入流分析 | 原项目对象地址/Optional 语义与新 nullable 类型按各自规则处理 |
| 成员测试 | `x in c`、`x not in c` | 保持 | 受容器/字面量查找规则限制 |
| 逻辑 | `and`、`or`、`not` | 普通非可空操作数保持 | and/or 的操作数返回值语义保持；bool? 条件规则见可空方案，?? 不采用真值判断 |
| 属性/方法 | `obj.x`、`obj.method(...)`、属性链 | 保持 | 静态绑定/访问器/编译期派发 |
| 下标/切片 | `a[i]`、`a[i:j:k]`、`a[i,j]` | 保持 | 容器和维度各有约束 |
| 数据拷贝与视图 | `buf[i:j]`、`buf.view`、`buf.view[i:j]` | 保持 | 前者复制与后者借用不可混同 |
| 列表字面量 | `[a,b]`、`[a,*xs,b]`、`[]` | 保持 | 需要可确定的容器/元素类型 |
| 字典字面量 | `{k:v}`、`{**mapping,k:v}`、`{}` | 保持 | {} 是 dict |
| 集合字面量 | `{a,b}`、`set()` | 保持 | 上下文指定 set/frozenset；空集合非 {} |
| 元组值 | `(a,b)`、`(a,)`、`makeTuple(...)` | 保持 | 允许返回值/PyTuple 等，非任意 Python tuple 容器用途 |
| 列表推导 | `[f(x) for x in xs if pred(x)]` | 保持 | 静态容器上下文，普通 for 目标简单名 |
| 字典推导 | `{key(x): value(x) for x in xs if pred(x)}` | 保持 | 字典/Counter 等已有目标类型 |
| 集合推导 | `{f(x) for x in xs if pred(x)}` | 保持 | set/frozenset 已有目标类型 |
| 多层推导 | `[f(x,y) for x in xs for y in ys if p(x,y)]` | 保持已有范围 | 不含 async for |
| 生成器表达式 | `sum(x*x for x in xs)` 等 | 保持 | min/max/sum/any/all 或特定 IterableType 用户调用点内联 |
| f-string | `f"value={x}"`、`f"{x:.2f}"` | 保持有效子集 | !s/!r/!a、debug 转换存在缺口，不能当完整支持；现有占位符上限 32 |
| 字符串格式化 | `"{}".format(x)`、`"%d" % x`、`format(x,spec)` | 保持 | 格式说明符以现有实现为准 |

## 内建与特殊调用

内建和特殊调用都保留函数形式，不把每项提升为关键字。

| 功能族 | 当前写法 | 迁移后 |
|---|---|---|
| 聚合 | `min/max`、`sum`、`any/all`，现有 key/default/start 选项 | 保持 |
| 长度与迭代 | `len`、`iter`、`next`、`aiter`、`anext`、`reversed`、`range`、`enumerate`、`zip` | 保持 |
| 转换和展示 | `str/int/float/complex/bool`、`repr`、`format`、`hash`、`chr`、`ord` | 保持 |
| 数值辅助 | `abs`、`pow`、`divmod`、`modmul`、`__cmp__` | 保持 |
| 输入输出 | `print(...,sep=...,end=...,flush=...)`、`input()`、`input[T]()` | 保持当前签名限制 |
| 内存分配 | `alloc[T]()`、`allocArray[T](n)`、`allocRawArray[T](n)` | 保持 |
| 初始化和析构 | `init[T](p,...)`、`destroy[T](p)`、`free[T](p)`、`freeArray[T](p)` | 保持 |
| 地址和转换 | `id(x)`、`id[T](x)`、`cast[T](x)`、可推断时 `cast(x)` | 保持；id 是地址语义 |
| 拷贝与移动 | `b = a`、`b = +a`、`a.__moved__`、特许位置的 __copy__/__move__ | 保持类模型决定的语义 |
| 标量静态成员 | `int.Min/Max`、`float.Inf/NaN`、`float64.isInf(x)/isNaN(x)` 等 | 保持 |

## 值匹配对照

普通 match 语句保持项目现行形式，不能统一写成“支持全部 Python match”；新增 match 表达式的取值规则及 inline match 的静态选择规则紧随对照表说明。

| 功能 | 当前写法 | 迁移后 | 边界 |
|---|---|---|---|
| 普通常量 | `case 0:`、`case "x":`、`case True:` | 保持 | 当前常量匹配路径 |
| 通配/捕获 | `case _:`、`case name:` | 保持 | 不宣称所有 wildcard guard 已无缺陷 |
| 绑定/守卫 | `case pattern as name:`、`case pattern if cond:` | 保持已有组合 | 嵌套和通配守卫另测 |
| OR | `case p1 \| p2:` | 保持 | 结构 OR 要求捕获名集合和绑定类型一致 |
| 序列 | `case [a,*mid,z]:` | 保持 | 最多一个星号；不同序列类型的 rest 规则保持 |
| 映射 | `case {"k":v, **rest}:` | 保持 | 键是字面量；支持已有嵌套映射范围 |
| 用户类字段模式 | `case new(x=0,y=y):` | 保持 | 按 match 主体类型推断，仅关键字字段 |
| 用户类模式 OR | `case new(x=1) \| new(x=2):` | 保持 | 不引入 case C(...) 的通用 Python 语义 |
| 枚举 | `case E.A:`、`case E.A \| E.B:` | 保持 | OR 是两个值择一，不是 Flag 位组合 |
| 空变体 | `case new.Quit:` | 保持 | union 主体推断 |
| 带载荷变体 | `case new.Move(x,y):`、`case new.Move(x=ax,y=ay):` | 保持 | 载荷顺序/字段类型检查 |
| 变体字面量与 OR | `case new.Move(1,y) if y>0:`、`case new.Ping(x) \| new.Pong(x):` | 保持 | 穷尽性与绑定规则保持 |
| Optional | `case None:`、内层字面量、`case value:` | 旧 ADT 保持；新可空值按 nullable 模式另行绑定 | 不使用 Optional.Some/None_ 模式，不无条件把旧 ADT 改成可空引用 |
| 字段 annotation 匹配 | Self 字段反射循环中的 annotation 模式 | 保持现有展开形式 | 是反射 pass 的专门机制，不开放动态反射 |

<a id="match-expression"></a>

## match 表达式

新增运行时 match 表达式，用花括号围住产生结果的 case：

```text
def matchCode(x: int) -> int:
    return x match { case 0: 1, case y if y > 0: 2, case _: 3 }

def describe(x: int) -> str:
    return x match {
        case 0: "zero",
        case y if y > 0: f"positive: {y}",
        case _: "negative",
    }
```

每个 case 的冒号后是一个表达式；整个 match 可放在赋值 RHS、return、实参、容器元素和 lambda 体等合法表达式位置。花括号内允许换行、注释与尾逗号，分支间必须有逗号，至少一条 case。换行只作隐式续行，不生成 case 的缩进 suite；需要多条语句时继续使用 match 语句或调用已有函数。这里不增加 return/raise 表达式，也不把 `{...}` 变成通用语句块。

```text
match_expr := disjunction ("match" "{" match_arm ("," match_arm)* [","] "}")*
match_arm  := "case" value_pattern ["if" expression] ":" expression
```

其中 disjunction 是包含现有比较、算术和 or 的较高优先级表达式；外层 ??、条件表达式和 lambda 继续使用各自规则。value_pattern 使用当前启用的运行时值模式语法，expression 不包含未括起的元组逗号。列表/字典/调用实参、嵌套 match、旧 lambda 的冒号与逗号都由各自子规则消费；不能扫描第一个冒号或按所有逗号拆分 case。元组模式和元组结果均须显式括起，例如 `case (a, b): (b, a)`；这只是括号分隔规则，具体元组模式能力仍须按模式 profile 接通。

| 规则 | 拟定语义 |
|---|---|
| 主体 | 在该表达式实际被求值的位置执行一次，所有分支共享该次匹配主体；仅有 _ 时也不能删除主体的副作用 |
| 分支选择 | 按源码顺序尝试模式，模式成功后才计算 guard；guard 成功后计算该分支结果一次，随即结束匹配 |
| 守卫 | 在运行时沿用普通 if 的真值转换；bool? 仍受可空条件规则限制，不套用 inline match 的编译期 bool 限制 |
| 失败/异常 | 模式不匹配不求 guard；guard 假则转下一 case；模式操作、guard 或结果抛出的异常直接传播，不回滚已经发生的副作用 |
| 捕获作用域 | 捕获名只在所属 case 的 guard 和结果表达式内可见；可遮蔽外层同名变量但不覆盖它，失败分支和整个表达式结束后均不泄漏 |
| 名称与 OR | 裸名称仍为值捕获，不因恰好叫 str/int 就成为类型模式；OR 备选须绑定相同名称集合及对应类型，选中一个备选后 guard 只计算一次，guard 假不重试该 OR 的其他备选 |
| 静态检查 | 所有分支都须通过名称、模式和结果类型检查，即使主体写成常量也不套用 inline 的未选分支隔离 |
| 无匹配 | 属于必须排除的路径；无法证明穷尽时要求末尾无 guard 的 _ 或经绑定证实不可反驳的捕获分支，不默认返回 None 或空操作 |

首版先接通普通标量/枚举主体上的字面量、限定枚举成员、_、名称捕获、as、OR 和 guard，覆盖上述 x:int 示例。序列、映射、`new(...)`、union 载荷、旧 Optional 与新 Nullable 等结构化模式以当前语句的有效值模式为迁移目标，逐项完成绑定、顺序匹配、穷尽性和取值发射后开放；旧 Optional 内层捕获与一般整值捕获不能混淆。不自动引入任意 Python `case C(...)`、字段 annotation 的编译期展开，或用运行时对象隐式开启 type match。

结果类型优先使用赋值注解、函数返回类型、调用形参等提供的目标类型，并将它传播到每个分支的 `new(...)`、箭头 lambda 和嵌套表达式。没有目标类型时，按项目既有隐式转换规则求一个唯一共同结果类型；不能任意采用第一分支类型，也不因 int/str 混合自动构造 Any 或一般 union。不能确定兼容结果时给出分支位置诊断，要求显式类型或转换。None 分支依既定可空值/可空引用/Optional 规则处理，例如在 `-> int?` 上下文中允许一个分支返回 None，另一个返回 int；不能让新的 int? 隐式变成 int。无值调用沿用项目 None/void 规则，不能与有值分支任意混用或凭空生成可存储的 void。

穷尽性依据主体类型和完整模式检查，带 guard 的 case 保守地不计入覆盖证明；末尾 `case _ if cond:` 也不能充当保证命中的默认分支。覆盖有限的 bool 域可以省略兜底；整数、str 等无法枚举的域通常需要兜底。枚举存在 Flag 组合或合法的未命名值时，列完声明成员不证明穷尽；union 仅覆盖变体名但给载荷加字面量约束，同样可能遗漏输入。无 guard 的不可反驳 case 必须最后，带 guard 的捕获/通配 case 可以后接其他 case。OR 内不可反驳备选只能最后，外层 guard 不改变 OR 内部可达性。结构化捕获能否覆盖全部主体必须经过对应类型的模式绑定确认。

match 表达式的优先级定为低于 or、高于 ??，同层左结合；这保持原有 ?? 低于 or、高于条件表达式的相对关系：

| 写法 | 归属 |
|---|---|
| `a + b match { ... }` | `(a + b) match { ... }` |
| `a or b match { ... }` | `(a or b) match { ... }` |
| `x match { ... } ?? fallback` | `(x match { ... }) ?? fallback` |
| `a ?? b match { ... }` | `a ?? (b match { ... })`；若匹配空合并的结果，显式写 `(a ?? b) match { ... }` |
| `x match { ... } if cond else other` | `(x match { ... }) if cond else other`；只在条件成立时求主体 |
| `x => x match { ... }` | `x => (x match { ... })`；每次调用 lambda 才求主体与分支 |
| `x match { ... } match { ... }` | `(x match { ... }) match { ... }` |
| `(x match { ... }).member`、`(x match { ... })(arg)` | 用括号对整个匹配结果访问成员或调用，结果本身须具备对应能力 |

将整个匹配结果用作更高优先级运算的操作数也须括起，例如 `(x match { ... }) + 1`；这与上述低优先级文法一致。

解析器在已读入表达式后前瞻 `match` 和 `{` 进入取值规则；`match` 仍是软关键字，普通名称 `match`、`obj.match`、`match(...)` 保持原角色，语句 `match value:` 仍由语句规则处理。识别明确的表达式前缀后，缺失 case、冒号、结果、分隔逗号或右花括号应定位诊断，不回退成名称/字典。case 和 guard 的分隔遵守递归文法；lambda、字典、嵌套 match 与 f-string 内部标点不能被外层提前截断。

匹配结果不额外要求结果类型具有默认构造、复制或赋值能力；按正常所有权和构造规则取得所选结果。

主体保存、模式借用和结果移动遵守现有所有权规则；捕获作用域不能代替生命期检查。返回临时主体的字段引用或 `case y: () => y` 这类逃逸闭包，必须证明借用有效或提供受支持的拥有环境，否则诊断；不能照搬当前 lambda 的 `[&]` 生成悬垂引用。匹配节点留在原求值点，不能把主体或 guard/结果提升到外层短路分支之前、循环条件之外或 lambda 创建时；与 ??、and/or、条件访问和函数实参组合须保留各自既定求值顺序。

<a id="inline-match"></a>

## inline match

新增 inline match 与 inline if 同属显式编译期分支，拟定写法如下。

```text
inline match Self._dim:
    case 2:
        self.update2D()
    case n if n >= 3:
        self.updateND(n)
    case _:
        self.updateGeneric()

inline for i in range(Self._dim):
    inline match i:
        case 0:
            self[i] = 1
        case _:
            self[i] = 0
```

inline 作用于整个 match，内部仍写 `case pattern [if guard]:`，至少一条 case；不增加 inline case 或 match-else。该入口是编译期语句，不另加 inline/type 的表达式变体。裸名称始终是值捕获，不根据主体切换为类型模式；直接类型模式使用下一节的 type match。

采用[静态分支共用规则](#static-branches)，匹配专有规则如下。

| 规则 | 拟定语义 |
|---|---|
| 主体求值 | 在当前编译/特化环境中求值一次，得到带目标类型的静态值；仅有 _ 也须满足静态求值要求 |
| 选择与 guard | 按源序尝试模式；成功后才求编译期 bool guard，True 或省略时选中；False 转下一 case，失败模式不求 guard |
| 待特化 | 当前所需主体、模式值或 guard 未绑定时延迟整次选择，不能越过它去选 _；运行时依赖是错误 |
| 无匹配 | 空语句序列，不要求兜底或穷尽性，不增加隐含断言 |

静态值与模式首版范围如下。这是新入口的待实现能力，普通 match 的运行时支持范围不能直接当作编译期求值能力。

| 静态值/模式 | 首版规则 |
|---|---|
| 主体来源 | None、bool、整数、str 字面量，已独立求值的 const/宿主常量，展开索引、整数 NTTP、枚举成员及已绑定类型；整数表达式沿用 inline if 的受限运算 |
| 字面量模式 | `case None:`、`case True:`、`case 2:`、`case -1:`、`case "fast":`；按静态类别匹配，类别不同则不匹配，不调用用户比较方法 |
| 整数规则 | 整数字面量按主体的目标整数类型检查范围后比较值；越界报错，不截断；bool 不作为整数参与匹配 |
| 字符串规则 | str 按内容匹配；`case "a":` 不匹配整数 97，单字符也不隐式变成字符码 |
| 枚举模式 | `case E.A:`、`case E.A \| E.B:`；枚举值保留 TypeId 与底层值，同一枚举的同值别名可匹配；不同枚举或整数不隐式互换，OR 不表示 Flag 位组合 |
| 通配/捕获 | `_` 不绑定；裸 `name` 捕获整个主体，含 `case int:` 也是捕获，不能解释为匹配 int 类型或同名常量 |
| as 绑定 | `case (2 \| 3) as n:`；n 保存完整主体及其类型，不取模式字面量的类型 |
| OR | `case p1 \| p2:`；备选按左到右选择，捕获名集合与对应类型必须一致；选定备选后 guard 只求一次，guard 假直接转下一条 case，不重试该 OR 的其他备选 |
| 类型主体 | 此前 TypeId 的 `_`/捕获/as 及 guard 形式保留，如 `case U if U is int:`；直接类型 case 推荐独立 `type match`，不改变 inline match 中裸名称的捕获规则 |
| 后续结构化模式 | 序列、映射、`new(...)`、union 载荷、字段 annotation、Optional/Nullable 包装值先增加对应静态值表示与匹配协议，再逐项开放；float/char 等值域也需明确目标规则后加入 |

枚举主体包括普通 enum、Flag 和已完成派生的 type enum；求值只读取已绑定的成员值。MRO 闭集及其他声明展开若尚未就绪，必须等待依赖完成；若选择反过来控制其所需的成员集合，按依赖循环报错。None 静态值不表示已经支持 Optional/Nullable 包装的自动解包；新可空类型继续遵守可空方案。未支持的结构模式不能通过调用运行时 getter、用户构造函数、__getitem__ 或 CPython eval 临时求值。

捕获是该 case 的 guard/正文内不可变的编译期局部绑定，失败模式及 guard 为假均不泄漏，也不覆盖外层同名变量；离开 case 后不可引用该捕获。正文中其他声明仍遵守原作用域规则。禁止对捕获赋值、增量赋值或取得可写引用；需要可变局部时显式复制到另一个名称。所选体中的捕获保留目标类型和词法作用域，不改变嵌套 lambda/函数的参数遮蔽；类型元值只进入合法类型或静态判断上下文，不成为运行时字符串/类型对象。捕获进入 lambda 时按常量绑定处理，不产生对临时 case 变量的悬垂引用。

所有 case 的必要结构预检包括模式种类是否在当前静态 profile 内、同一模式重复捕获、OR 捕获名集合一致性，以及无 guard 的不可反驳模式必须位于末尾；带 guard 的捕获/通配模式允许后接 case。OR 内不可反驳的备选也只能位于最后，case guard 不能让被该备选遮蔽的后续备选重新可达。捕获类型一致性在有主体类型的模式绑定阶段验证。名称解析、模式值与 guard 求值仅针对实际需要尝试的路径；已经选中后，不求后续 case 的值或 guard。外层 inline for 的全子树跳转预检先行，因此未选 case 中的 break/continue 也不能绕过既有限制。

主体/guard 对声明集合的依赖、未选体隔离、嵌套、模块/类位置及 inline for 的跳转限制均遵循[静态分支共用规则](#static-branches)。

<a id="type-match"></a>

## type match 与类型匹配表达式

本轮类型匹配建议采用显式 `type match`。用户提出的两种形式都可在自有 parser 中实现，区别在于是否让同一个名称模式随主体类别改变含义。

| 方案 | case str / case list[int] 的解释 | 取舍 |
|---|---|---|
| 普通 match 根据主体切换 | 主体绑定为类型时按类型匹配，否则按值模式 | 少一个前缀；需要先保存歧义节点，绑定后才能确定捕获与类型引用，影响后续名称作用域、重命名及语法工具 |
| 显式 type match（推荐） | 在整个块内固定按类型模式解析 | 多一个 type；parser 可独立确定模式种类，拼写错误可直接报未知类型，值匹配的捕获规则保持稳定 |

不采用“能解析为类型名就匹配类型，否则当捕获”的回退规则；否则漏写 import 或类型拼错会悄悄变成全匹配。完整的推荐分工为：

| 入口 | 匹配对象与阶段 | case 中裸名称 |
|---|---|---|
| `match value:` | 现有值模式与既有展开入口 | 捕获变量 |
| `value match { case pattern: expression, ... }` | 运行时值匹配，选中分支提供表达式结果 | 所属 case 的局部值捕获 |
| `inline match value:` | 编译期可求的值；保留此前 TypeId 元值 + guard 路径 | 编译期捕获 |
| `type match T:` | 编译期类型身份及带显式捕获的类型形状 | 裸名称为已声明类型引用；type U 才声明类型捕获 |
| `type A[T] = T match { case pattern: R, ... }` | 编译期类型身份及带显式捕获的类型形状，选择一个结果类型 | 裸名称为已声明类型引用；type U 仅在所属 case 声明类型捕获 |

```text
def typeCode[T](value: T) -> int:
    type match T:
        case list[int]:
            return 1
        case str:
            return 2
        case int | float:
            return 3
        case _:
            return 0
```

type match 语句本身表示编译期选择，不必叠加 inline；首版只开放这一种顺序，不另加 inline type match/type inline match。T 在绑定时须代表类型，首版主体包括类型形参、已声明类型/别名及合法的已构造类型表达式；`type match value:` 若 value 是运行时对象则报错，不隐式执行 type(value) 或 isinstance。它不新增运行时动态类型检查。

类型匹配表达式是类型别名右侧的专用 TypeExpr；首版仅接受它作为 `type Name[...] =` 的完整右侧，不在注解、泛型实参、类关联类型或其他一般类型位置开放：

```text
type ElementOfMatch[T] = T match {
    case list[type U]: U,
    case dict[str, type V] if V is int: V,
    case _: T,
}

type OnlyListElement[T] = T match {
    case list[type U]: U,
    case _: Never,
}
```

其文法为：

```text
type_alias_rhs       := type_match_expr | type_expr
type_match_expr      := type_match_subject "match" "{" type_match_expr_case ("," type_match_expr_case)* [","] "}"
type_match_subject   := type_expr_without_top_level_match
type_match_expr_case := "case" type_pattern ["if" static_bool_expr] ":" type_expr
```

最外层 `match {` 将类型别名右侧前面的完整 TypeExpr 作为主体；每个 case 的顶层 `:` 终止模式/守卫，顶层 `,` 分隔 case。括号、类型实参、Callable 的 `->` 和 case 结果中的普通 TypeExpr 各自消费内部标点，因此不会被外层 case 提前截断。解析器只在 `type Name[...] =` 的右侧读到完整主体之后的 `match {` 时建立该节点：`type A = match` 仍是类型名为 match 的普通别名，`type match = T` 仍是名为 match 的别名，`type match T:` 仍是语句；已开始的 `T match` 缺少 `{` 必须报错，不回退为其他类型或值 match。

每次实例化按源码顺序尝试 case：完整类型模式成功后，在该 case 的捕获环境中求严格编译期 bool guard；guard 为 False 时丢弃捕获并继续下一 case，guard 成功后只解析和归约该 case 的结果 TypeExpr。`type U` 的作用域覆盖对应 guard 与结果类型，不泄漏到下一 case、别名外层或其他 OR 备选；OR 的捕获集合一致性、首个成功备选和 guard 不重试规则与 type match 语句完全相同。上述例中 `ElementOfMatch[list[int]]` 为 int，`ElementOfMatch[str]` 为 str，`OnlyListElement[str]` 则明确归约为 Never。

类型匹配表达式必须在每个实际特化上得到一个结果类型。首版一律要求最后有无 guard 的 `case _:` 或 `case type U:`，不以已知闭集的穷尽推断代替该 arm。没有 case 命中是特化错误，不隐式产生 Never、None 或原主体；作者若要拒绝未覆盖的类型，须显式选择 `case _: Never`。所有 case 先做语法、模式轮廓、类型名和捕获冲突预检，之后只对选中结果做该特化的常规类型归约。

主体、模式或 guard 仍为 Dependent 时保留整个类型匹配表达式，等待特化；不能因较早 case 尚未可判定而越过它选择后面的 case 或兜底。待依赖绑定后从第一条 case 重新按源序选择，结果类型再在已提交的捕获环境中归约；透明别名展开、循环检测、精确类型身份和可空限定继续沿用本节的统一规则。

type match 语句的显式类型捕获复用条件类型别名的 type U 规则，匹配成功后对该 case 的守卫和正文可见：

```text
def capturedTypeCode[T](value: T) -> int:
    type match T:
        case list[type U] if U is int:
            return 1
        case list[type U]:
            return 2
        case dict[type K, type V] if K is V:
            return 3
        case type Whole:
            return 0
```

两个 case 中的 U 是不同局部符号；第一个守卫失败不会把其捕获带到第二个分支。type Whole 捕获整个主体类型，是显式的具名兜底。

| 类型模式 | 首版拟定规则 |
|---|---|
| `case str:`、`case pkg.Model:` | 解析为 TypeExpr 并绑定已声明类型，按精确类型身份比较；名称不存在时报错，不回退成捕获 |
| `case list[int]:`、`case dict[str, int]:` | 精确构造类型，包括泛型实参；不表示“某个 list 子类”或允许元素隐式转换 |
| `case list[U]:` | U 必须是外层已声明的类型参数/别名；未绑定实参则延迟匹配，不将 U 作为新捕获；未知 U 报错 |
| `case list[type U]:`、`case dict[str, list[type U]]:` | 按构造类型结构匹配并捕获单个类型实参；U 保存完整类型用途，对本 case 的 guard/正文可见 |
| `case dict[type K, type V]:` | 多个不同名的类型捕获，不是调用方额外提供的泛型参数 |
| `case A[int, str]:` 与 `case A[(int, str)]:` | 前者匹配 A 的两个外层类型实参，后者匹配 A 的一个元组类型实参；括号内元组不得展平到 A 的实参表 |
| `case type U:` | 捕获整个主体类型；无 guard 时不可反驳，必须最后 |
| `case int \| float:` | case 顶层为类型模式 OR，任一精确匹配即可；匹配成功后 guard 只求一次 |
| `case list[type U] \| set[type U]:` | OR 各备选独立匹配并提供相同捕获名集合；U 取首个成功备选的实际类型，守卫失败不重试该 OR |
| `case _:` | 不绑定名称的顶层通配符；无 guard 时必须最后 |
| `case list[type U] if U is int:`、`case _ if cond:` | 模式成功后在捕获环境求编译期 bool guard；False 则下一 case，Dependent 阻止越过，运行时条件报错 |
| 类型别名/限定 | 透明别名先展开，名义类型身份保留；数组维度、值实参、引用限定及 Callable 签名按统一类型相等规则处理，不比较 C++ 类型文本 |
| 可空类型 | 值类型 `int?` 与 int 不同；引用模型的 Node/Node? 只差可空注解，具有相同类型身份，不能据此分派；不读取对象当前空状态 |
| 后续类型形状 | 拟复用已有 `list[...]`、`dict[str, ...]` 的匿名形状含义，独立增量实现；不与 inline match 的运行时容器内容模式混淆 |
| 捕获标记 | 必须写 type NAME；`list[U]`、`list[_U]` 和 `as U` 不声明类型捕获，旧 `_U = ...` 仅在旧源码兼容入口识别 |

精确相等与“继承自某类”“满足某协议”“可转换成某类型”分别建模；`case Base:` 仅匹配 Base，`case SomeProtocol:` 不表示所有实现者。带捕获的 list[type U] 同样要求构造类型本身相同，不自动接受 list 的子类；固定子模式依原规则精确比较。泛型实参是否已绑定与名称是否存在分开诊断，前者可以是 Dependent，后者为 Error；无论是语句还是类型匹配表达式，即使后面有 _ 或 type U，也不能越过当前待特化的模式选择兜底。

case 层的顶层 `|` 固定为 OR 分隔，括号/类型实参内部进入可识别 type NAME 的类型模式子规则；不含捕获的部分沿用类型文法。泛型应用沿用[泛型实参边界](#generic-argument-boundaries)：`A[T,U]` 与 `A[(T,U)]` 的模式结构不同，后者的元组不展平。可空类型优先写 `case int?:`，不把 `case int | None:` 解读成可空类型整体。允许在明确类型括号内使用已支持的可空兼容拼法；不因类型匹配而新增一般 union type。Callable 的 -> 继续采用原类型优先级，参数括号与元组类型保留；case 头在顶层 if 或冒号处结束，不把 guard 当作条件类型别名 RHS。_ 仅在顶层类型模式位置特殊，`list[_]` 不成为匿名形状的新拼法。

每个 case/OR 备选用独立捕获环境，按完整模式匹配后提交；OR 备选必须显式声明相同的捕获名集合，名称绑定种类均为类型，实际被捕获的具体类型由成功备选决定。无 guard 的 _ 或 type U 必须作为最后一个 case；OR 内不可反驳备选也只能最后。guard 假则丢弃本 case 的绑定并尝试下一 case，不重试本 OR 的其他备选。重复声明、外层同名遮蔽和模式裸名解析均遵循前述显式类型捕获规则。

type match 语句与类型匹配表达式使用[静态分支共用规则](#static-branches)的源序选择和待特化规则：当前模式成功后才在捕获环境中求严格 bool guard，当前依赖未绑定时等待特化，不提前选 _。语句无匹配为空，完整函数仍检查选中路径的返回值与确定赋值；表达式无匹配按前述规则是特化错误。

旧函数类型 if 先选具体类型、再选形状模式，而新 type match 语句和类型匹配表达式始终按源序；`list[type U]` 在 `list[int]` 前时先命中。旧无 else 的未覆盖断言及类体位置限制也不机械迁入；迁移显式捕获拼法与改用 type match 是不同变更。

## 访问控制、继承与类型身份

访问控制、类型身份和继承访问的拼法保持。

| 功能 | 当前写法 | 迁移后 |
|---|---|---|
| 公有/受保护/私有 | `name`、`_name`、`__name` | 保持；不增加 public/protected/private 关键字 |
| 友元 | `class Vault(friends=(Reader, Writer)):` | 保持类头选项；不增加 friend 关键字 |
| 当前类型 | `Self`、`Self.__name__` | 保持 |
| 直接实体基类类型 | `Super`、`C.__base__` | 保持自动注入；不允许手写 __base__ |
| 基类成员调用 | `super.method(...)`、`super.__init__(...)` | 保持规范写法 |
| 基类可调用协议 | `super()`、`super.__call__()` | 保持本项目语义，不当 Python super 代理 |
| 受限括号基类访问 | `super().method(...)` | 当前也接受，但要求基类存在 __call__；直接按基类/Proxy 目标成员发射，不先调用 __call__ 获取结果；作为兼容特例保留并单测 |
| 透明代理 | `class Wrapper(Proxy[T]):` | 保持；不新增 proxy 关键字 |
| 类型身份 | `C.__id__`、`obj.__class_id__` | 保持自动生成 |
| union 标签 | `U.Enum`、`obj.__enum__` | 保持 |
| MRO 枚举操作 | `E.of(obj)`、`E.create(tag)`、`U.Enum.of/create` | 保持 |

现有命名与 strict 规则也影响源码的合法性，但不必进入词法关键字表。本轮保持类名后缀：enum → `Enum`，flag enum → `Flag`，MRO 派生 → `TypeEnum`/`TypeUnion`，union → `Union`，protocol → `Type`，mixin → `Mixin`，boxing → `Unsafe`，annotation → `Meta`，descriptor → `Var`，delegate → `Delegate`，自定义异常 → `Error`；内建类型及已有豁免继续有效。枚举成员 PascalCase，方法/参数/字段 camelCase，模块 snake_case。后续若取消类型后缀要求，应作为独立风格规则变更，不在本次关键词迁移中顺带处理。

模块入口约定保持：用户模块 `from py2cpp import *`，标准库子模块相对导入 `builtins`，FFI 桩导入 `py2cpp.builtins`；用户从 FFI 导入使用具名符号。关键字转换不自动删除这些导入，因为它们同时提供类型、协议和函数。自有编译器将来若引入隐式 prelude，应另外明确导入兼容规则。

## dunder 协议

dunder 协议不改名、不提升为关键字；保留已实现的协议及类型组合。

| 协议族 | 当前及拟定写法 |
|---|---|
| 生命周期 | `def __init__/__del__/__copy__/__move__/__post_init__` |
| 调用/容器 | `__call__`、`__len__`、`__getitem__`、`__setitem__`、`__delitem__`、`__contains__` |
| 迭代 | `__iter__`、`__next__`、`__reversed__` |
| 转换/展示 | `__bool__`、`__str__`、`__repr__`、`__format__`、`__hash__`、`__int__`、`__float__`、`__complex__`、`__abs__` |
| 算术 | `__add__/__sub__/__mul__/__truediv__/__floordiv__/__mod__/__pow__/__matmul__`、`__modmul__`；已支持的 r/i 版本 |
| 位运算/一元 | `__and__/__or__/__xor__/__lshift__/__rshift__` 及已有 r/i 版本，`__neg__/__pos__/__invert__` |
| 比较 | `__cmp__`、`__eq__/__ne__/__lt__/__le__/__gt__/__ge__` |
| 上下文/异步 | `__enter__/__exit__`、`__aenter__/__aexit__`、`__aiter__/__anext__`、`__await__` |
| 描述符 | `__get__/__set__`，保留宿主内联语义 |
| 方法别名特例 | `__repr__ = __str__` |

record 未显式声明 `__str__` 时，自动生成 `__str__ -> __repr__`；显式 `__str__` 优先。这是 record 的派生规则，不改变普通类现有的 dunder 别名特例。

## 静态反射与编译期参数栈

静态反射与编译期参数栈继续采用 intrinsic 调用形式。

| 功能 | 当前写法 | 迁移后 |
|---|---|---|
| 字段枚举 | `Self.iterFields()`、`Self.iterFields[Meta](...)` | 保持 |
| 字段序号枚举 | `Self.enumFields(publicOnly=True,mro=True)` | 保持 |
| 字段类型/默认值 | `Self.getFieldType(f)`、`Self.getFieldDefault(f)` | 保持 |
| 字段单个/全部注解 | `Self.getFieldAnnotation[Meta](f)`、`Self.getFieldAnnotations(f)` | 保持 |
| 方法枚举 | `Self.iterMethods()`、`Self.iterMethods[Meta](...)` | 保持 |
| 方法注解 | `Self.getMethodAnnotation[Meta](m)` | 保持 |
| 方法签名反射 | `Self.iterMethodParams(m)`、`Self.getMethodParamType(m,p)`、`Self.getMethodReturnType(m)` | 保持 |
| 枚举筛选 | 现有 `publicOnly=...`、`mro=...`、`glob="..."` | 保持各接口已有选项 |
| 子类枚举 | `Mixin.iterSubclasses()`、`sortConst="_testTag"` | 保持当前发现/展开位置 |
| 静态成员访问 | `getattr(obj,name)`、`setattr(obj,name,value)`、受限 `hasattr(obj,name)` | 保持；name 需编译期解析，不引入动态反射 |
| 编译期参数栈 | `s: VarStack = new()`、`s.push(v)`、`s.pop()`、`s.top()` | 保持作用域要求 |
| 参数栈展开 | `new(*s)`、`f(*s)`、`(*s,)` | 保持 |
| 旧反射拼法 | 已接受的 `iter_fields`、`get_field_type`、`iter_methods` 等 snake_case | 兼容读取，迁移工具统一到对应 camelCase 名；不是新增语言规则 |

## select DSL

select 是编译期字符串 DSL，主语言入口与串内语法均保留。

| 功能 | 当前写法 | 迁移后 |
|---|---|---|
| 入口 | `obj.select("...")` | 保持；一个字符串字面量 |
| 字段 | `.meta.title` | 保持；列表须先显式下降，如 `.teams[:].name` |
| 下标/键 | `[0]`、`[-1]`、`['key']` | 保持 |
| 切片 | `[:]`、`[1:3]`、`[1:5:2]`、`[::2]` | 保持 |
| 多下标/键 | `[0,1:3]`、`['a','b']` | 保持 |
| 过滤 | `{.score > threshold}` | 保持；子表达式交给统一 parser |
| 投影 | `.(a,b.c)`、嵌套投影 | 保持；各路径汇入同一个 list，末步类型须一致，不产生异构 tuple/record |
| 可选链 | `?.title`、`.items?[0]`、`.data?['k']` | 保持 |
| 递归下降 | `..name` | 保持 |
| 绑定/引用 | `:$t`、`$t.field` | 保持 |
| 同链分段 | `.teams[0]:$t; $t.members` | 保持现有绑定可见性规则；当前至多一个分号，不开放顶层逗号多路径 |
| 排序 | `@sort(-.score,.name)` | 保持 |
| 分组 | `@group(.dept)` | 保持 |
| 计数/频次 | `@count`、`@count(.dept)` | 保持 |

select 无后处理时返回 list；有后处理时按 sort/group/count 推断。对象字段链不自动展开 list，列表下降须显式使用下标、切片或过滤步。现有 group 后再 sort/count 等限制保持；字符串中的 @sort 等不是主语言装饰器，也不改成主语言关键字。

## build DSL

build 同样保持独立字符串 DSL。

| 功能 | 当前写法 | 迁移后 |
|---|---|---|
| 对象根 | `Type.build("...")` | 保持 |
| 列表根 | `list[T].build("[:3] > ...")` | 保持 |
| 字段赋值 | `name="x", score=1` | 保持 |
| 直接 RHS | 字符串、整数、`True/False/None`、`$i` | 保持；一般表达式用花括号，浮点如 `score={1.5}`，不能误当所有 Python 表达式均可裸写 |
| 对象下降 | `child > name="x"` | 保持 |
| 列表构造 | `members[:3] > score=1` | 保持；当前 N 为非负常量 |
| 下标绑定 | `members[:3]: $i > score=$i` | 保持 |
| 内嵌表达式 | `name={prefix + str($i)}` | 保持；调用统一表达式 parser |
| 嵌套 | 多级对象/列表及外层 $i 引用 | 保持 |

## FFI

FFI .pyi 语法保持声明形式。

| 功能 | 当前写法 | 迁移后 |
|---|---|---|
| C 类型 | `@native ⏎ @native_name("CType") ⏎ class PyiType:` | 保持 |
| C enum/union | FFI 生成的原生类、别名及常量组合 | 保持，不套用户 enum/union 迁移 |
| typedef | `type PyiAlias = PyiType` | 保持 |
| 字段映射 | `field:T @native_name("c_field")` | 保持 |
| 常量映射 | `PyiConst:T @native_name("C_MACRO") = v` | 保持 |
| C 函数 | `@native ⏎ @native_name("c_fn") ⏎ def fn(...) -> T: ...` | 保持 |
| 指针/字符串/回调 | `Pointer[T]`、`uintptr`、`utf8ptr/utf16ptr`、`Function[[...],R]` | 保持 |
| C varargs | `def fn(fmt:utf8ptr,*_) -> int: ...` | 保持特殊 FFI 处理 |
| 未完全映射字段 | `field: None  # C: ...` | 保留占位输入，不标为完整类型支持 |
| 导入 | `from ffi.module import Symbol` | 保持；用户星导入仍受禁止规则 |

## 模板语言

模板语言的外形保留，但执行范围需与自举方案一起明确。

| 当前形式 | 迁移后拟定形式/行为 |
|---|---|
| `PY2CPP_BEGIN(for ...)/PY2CPP_END` | 同拼法，原生模板求值/展开；保留现有 range 运行时界到 C++ while 的回退（start/step 为编译期整数，stop 为 C++ 标识符） |
| `PY2CPP_BEGIN(if .../elif .../else)` | 同拼法；保持静态展开及已有运行时 C++ 分支回退 |
| `PY2CPP_BEGIN(def fn_Name(...))` | 同拼法；注册明确的模板函数 |
| `PY2CPP_EVAL(expr)` | 同拼法；原生表达式解析；保留当前上下文差异：独立 EVAL 渲染 C++ 字面量，静态 for/helper 体中的字符串插值原样拼入 |
| `PY2CPP_EXEC(stmt)` | 同拼法；限制为已定义模板子集，不再隐式任意 CPython |
| `PY2CPP_ECHO(expr)` | 同拼法；保留字符串/片段/类型注册表区分 |
| `PY2CPP_INCLUDE("path")` | 同拼法；模板文件包含 |
| `PY2CPP_TYPE(Name)`、已有 `PY2CPP_TYPE_Name` | 同拼法；显式类型注册表 |
| `PY2CPP_IGNORE ... PY2CPP_END` | 同拼法；IDE 内容剔除 |
| `PY2CPP_INJECT_CLASS(CppClass) ... PY2CPP_END` | 同拼法；类体注入 |
| `PY2CPP_BEGIN_SCOPE/PY2CPP_END_SCOPE` | 同拼法；命名空间展开 |
| `PY2CPP_NAMESPACE` | 规范模板仅用于生成的 ~macro 桩，paste/镜像模板受 R0403 禁止；底层兼容替换器仍按 module_rel 展开命名空间限定符，保持这两层规则 |

模板中的任意 CPython 执行能力是本清单唯一明确建议收敛的宿主语言契约；生产用例和已有模板测试应先逐项迁移，再禁用宿主回退。生成的 `PY2CPP_GETATTR/SETATTR/CALL` 等属于 C++ 后端实现，不是 Python 用户源码语法。

## 未完成或未承诺的能力

下列形式出现在 CPython 语法、旧文档或辅助代码中，不能当作现有完整目标语言支持。

| 写法/能力 | 当前判断 | 迁移处理 |
|---|---|---|
| `assert expr` | 无完整 visitor/pass | 新前端明确报未实现，若新增支持需单独设计 |
| 裸 `raise` | 当前 emit_raise 明确拒绝 | 与 `raise e` 分开；新增重抛支持需独立实现 |
| `(x := expr)` | 无完整 NamedExpr 发射 | 同上 |
| `global x`、`nonlocal x` | 闭包方案待实现 | 保留规划语法，不能当作已迁移功能 |
| 普通嵌套 def/逃逸闭包 | 无完整闭包环境/绑定实现 | 与工厂内联、受限 lambda 分开 |
| 普通签名 `/`、bare `*` | CPython 可解析，普通签名处理不完整 | 暂明确诊断；特殊 intrinsic 不证明普遍支持 |
| 普通 varargs 后 kwonly | 通用路径拒绝 | 保持限制；固定长度 mixin 展开是例外 |
| `@classmethod` | 仅见 CPython/IDE 辅助实现，目标支持未证实 | 不自动改为 static |
| `@x.setter`、`@property.deleter` | 前者被当前规则禁止，后者未完整实现 | setter 的新规范是 property 块内 __set__；不因新块自动开放删除访问器 |
| `f"{x!s}"`、`f"{x!r}"`、`f"{x!a}"`、默认 repr 的 `{x=}` | 未正确支持；conversion 处理存在缺口 | 明确诊断或独立修复，不当作语法迁移已完成 |
| `del x`、普通 `del obj.field`、多目标 del | 不在已实现删除子集 | 明确诊断；新增 `del obj.cachedProperty` 仅用于显式失效 lazy property，不推广为普通字段删除 |
| `[a,b] = value`、任意 iterable 解包 | 不等于现有 PyTuple 解包 | 明确诊断/另行扩展 |
| async 推导式 | 现有代码显式拒绝 | 保持拒绝 |
| 任意位置 generator expression | 仅少数调用点内联支持 | 保持限制 |
| ORM genexp → `SqlQuery[T]` | 旧文档中的规划，当前无对应用户入口及发射器 | 不计入现有 generator expression 支持；作为后续库/编译器功能实现 |
| 一般 `{*xs}`、任意 tuple 星展开 | 无对应完整通用路径 | 区分于参数包/VarStack/PyTuple 特例 |
| `x in (a,b)`、`(a,b)[i]` 等 tuple 字面容器用法 | strict/发射规则有禁止 | 不因新 parser 自动开放 |
| 一般 `A \| B` 联合类型 | 当前可空特例不能证明一般支持 | 使用现有 union 声明或另行实现 |
| `type Alias[T=int] = ...` | 普通别名默认值未完整保存/发射 | 不列完整支持 |
| ParamSpec `**P` | 未核实完整目标语义 | 不列完整支持 |
| CPython 内建 `isinstance` / `issubclass` | 未确认完整目标发射实现 | 不因为 CPython 能解析普通调用就列为已实现内建；类型约束/类型 if 另列 |
| 注解内任意条件类型 | 不等同已有条件 type alias | 使用已支持别名形式 |
| `new[T]()`、`new(Type)` | 当前明确禁止 | 保持 new(...) 的类型上下文规则 |
| `super().__init__()`、`super(T,obj)` | 当前禁止/不同语义 | 用 super.__init__；不模拟通用 Python super |
| `case C(...)`、任意嵌套类字段模式 | 不等同项目 case new(...) | 保持当前模式子集 |
| `Optional.Some(...)`、`Optional.None_()` | 当前 strict 禁止用户写法 | 用 None、内层值及匹配 sugar |
| 任意动态 getattr/setattr、eval/exec/importlib | 无目标动态运行时 | 不因重写 parser 承诺支持 |
| 任意顶层执行/函数内动态 import | 当前是静态模块系统 | 明确模块语言边界 |
| `@entity`、`@autoinit`、旧 `field()` | 旧文档/已移除概念 | 不放入有效迁移语法 |
| `record(...)` 配置参数 | 新方言禁止 | record 固定生成构造、相等和展示；legacy `@dataclass(...)` 仅在兼容入口按历史已接受的参数语义处理 |
| 任意 metaclass/动态 Python hook | 无完整目标模型 | 不承诺自动支持 |

核查依据主要包括：`py2cpp/builtins.py`、`src/translator.py`、`src/analysis/ir.py`、`src/analysis/analyzer.py`、`src/passes/strict_style.py`、`src/passes/type_if.py`、`src/passes/type_conditional.py`、`src/passes/field_properties.py`、`src/passes/kwargs_options.py`、`src/passes/match_case.py`、`src/emit/fstring_emit.py`、`src/emit/comprehensions_emit.py`，以及 `test/lang/` 和对应 `src/tests/` 用例。模板、select、build、FFI 另对应各自实现与文档。本清单是静态审计和迁移提案，没有为所有语法重新执行编译/运行验证。
