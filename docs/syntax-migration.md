**现有语法与拟定迁移语法完整对照**

初稿 2026-09-08，更新 2026-09-10；配套方案：[自有前端与自举编译器](./parser-self-hosting.md)。所有新写法均为设计提案，尚未实现。

清单按源码语法族、编译器特殊入口、嵌入式 DSL 和模板语言枚举；普通标准库的每一个方法不算独立语法。依据为 builtins、解析/分析/发射代码、语言测试和译器单测。表中“保持”表示保留表面写法及当前支持范围，不表示兼容全部 CPython 语义；“⏎”表示实际换行与相应缩进。

本提案固定两批语法变化：A 为 enum（含 type enum）/final/const，B 为 union（含 type union）/variant/protocol/mixin/static/virtual/abstract/override/property、箭头 lambda（=>）、Callable 类型简写（(A,B) -> R）、inline for/inline if/inline match，以及 C# 风格的 T?、?.、?[]、后缀 !、??、??=。本轮推荐将独立类型匹配 type match 也纳入 B，具体选择理由与边界见后文。type 复用已有软关键字，在 type enum/type union 中表示 MRO 派生声明，在 type match 中显式开启类型模式；属性改为类内 property 块，静态属性配套建议使用 static property；inline for 保持原 inlineRange 的完全展开语义，inline if/inline match 显式选择编译期分支。ref/lazy、所有权标记和用户注解继续使用现有形式，但进入明确的自有 AST 字段。新增的声明词与 inline 均为上下文软关键字。迁移期旧写法继续接受；新可空语义涉及类型与行为差异，按下述规则适配，不能全部视作文本替换。

声明种类的对照如下。

| 功能 | 当前写法 | 迁移后拟定写法 | 边界 |
|---|---|---|---|
| 普通类 | `class C:` | 保持 | 普通实体类型 |
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

属性列表允许附着于新增的 enum/union/protocol/mixin/variant 及 type enum/type union 声明。MRO 派生由 type 前缀直接表达，自有 AST 显式记录派生模式及根类型，不再以 mro 属性表达新写法。兼容桥分别恢复 `ClassDef + @enum.mro` 或 `ClassDef + @union.mro`，保留原有 base= 和声明体，不叠加普通 @enum/@union；旧装饰器与对应新前缀同写属于重复声明。type union 保持现有 base= 要求，不因 type enum 可继承就新增派生联合继承能力。FFI 中的 C enum/union 声明另见后表，不能通过名称后缀机械改成用户 enum/union。

解析器在声明起始位置识别 `type enum NAME` / `type union NAME`，并与现有 `type Name = T` 别名规则区分。`type enum = T`、`type union = T` 仍可表示名为 enum/union 的类型别名，`type(...)` 仍按表达式解析；这只定义语法分派，不新增运行时 type 内建支持。

本轮推荐的 `type match T:` 是另一条语句规则：`type match = T` 仍是名为 match 的类型别名；根据别名头的 `=` 或泛型形参列表与匹配语句的主体/冒号分派，不依赖符号表判断。具体类型模式文法见后文。

保留的类级属性如下；它们可以与新声明组合，组合合法性沿用语义检查。

| 功能 | 当前写法 | 迁移后 | 语义 |
|---|---|---|---|
| 数据类 | `@dataclass`、`@dataclass(init=..., repr=..., eq=..., order=..., frozen=...)` | 保持 | 派生构造、比较、展示；frozen 已实现 |
| 序列化 | `@serializable` | 保持 | dataclass/union 派生 serialize/deserialize |
| 可复制 | `@copyable` | 保持 | 复制构造与赋值 |
| 不可复制 | `@uncopyable` | 保持 | 禁止复制，保持移动模型 |
| 引用计数对象 | `@refcount` | 保持 | 源码写 C，存储表示采用引用计数包装 |
| 裸堆对象 | `@boxing` | 保持 | 源码写 C，存储表示采用 C*；显式生命周期 |
| 元数据定义 | `@annotation`、`@annotation(inheritable=True, repeatable=False)` | 保持 | 可与 dataclass 组合；不新建 annotation 关键字 |
| 描述符定义 | `@descriptor ⏎ class RangeVar[T]:` | 保持 | get/set 内联；不新建 descriptor 关键字 |
| 原生实现 | `@native ⏎ class C:` | 保持 | C++/FFI/模板提供实现 |
| C++ 名称映射 | `@native_name("CppName")`、`@native_name("prefix_*")` | 保持 | 类/模块函数的外部命名 |
| 开放元数据 | `@TagMeta`、`@TagMeta(...)` | 保持 | 同样适用于合法的方法/声明位置 |

`order=True` 且未显式给 eq 时，当前默认 eq=False；frozen 的字段 final 语义保持。kwOnly/kw_only 和 slots 尚未构成可用功能，不能作为已支持选项迁移；repeatable 的完整多实例反射也需单列完善。copyable 与 boxing、frozen 等组合限制保持。

函数、方法及装饰工厂的对照如下。

| 功能 | 当前写法 | 迁移后拟定写法 | 边界 |
|---|---|---|---|
| 普通函数/方法 | `def f(...):` | 保持 | 无新 function 关键字 |
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

字段、参数标记与属性访问器如下。

| 功能 | 当前写法 | 迁移后拟定写法 | 边界 |
|---|---|---|---|
| 实例字段 | 类体 `x: T`、`x: T = v` | 保持 | 有默认值仍是实例字段 |
| 构造内字段赋值 | `self.x = v`、允许位置的 `self.x: T = v` | 保持 | 静态字段收集与类型规则保持 |
| 类级常量 | `x: T @const = v` | A：`const x: T = v` | static constexpr；当前仅支持部分字面量/标量属性初始化 |
| 实例只读字段 | `x: T @final`、`x: T @final = v` | A：`final x: T`、`final x: T = v` | 仍须各构造完整初始化；不新增局部 final |
| 无注解类体常量 | `_testTag = 1` 等既有标量形式 | 保持 | 与带注解实例默认字段区分 |
| 线程局部字段 | `x: T @thread_local = v` | 保持 | 类静态线程存储 |
| 自动构造排除字段 | `x: T @optional = v` | 保持 | dataclass 中不进自动构造形参/排序；仍可 assign/new 关键字赋值 |
| 引用参数 | `def f(x: T @ref):` | 保持 | 可变引用 |
| 引用返回 | `def f(...) -> T @ref:` | 保持 | 引用返回 |
| 引用绑定 | `x: T @ref = obj.field` | 保持 | 非值拷贝 |
| 惰性参数 | `def f(x: T @lazy = None):` | 保持 | 首次访问求值并记忆；None 表示未传 supplier |
| 引用与惰性组合 | `T @ref @lazy` | 保持 | AST 分开记录引用类型与求值策略 |
| 字段元数据 | `x: T @Meta`、`x: T @Meta(...)` | 保持 | 开放注解 |
| 多标记 | `x: T @MetaA @MetaB(...)` | 保持 | 顺序及 repeatable 检查保持 |
| 字段描述符 | `x: T @RangeVar(0, 10) = v` | 保持 | 描述符参数与字段默认值分开 |
| 参数/返回描述符 | `def f(x:T @Desc(...)) -> U @Desc(...):` | 保持 | 入口/返回的验证与替换 |
| 元数据加描述符 | `T @Meta @Desc(...)` | 保持 | 不把全部标记折叠成单一限定符 |
| 字段只读访问器 | `x: T @property = v` | B：存储字段 + `property x:` 中的 `__get__` | 保留默认值和只读接口；存储仍可变，区别于 final |
| 实例 getter | `@property ⏎ def x(self) -> T:` | B：`property x: ⏎ def __get__(self) -> T:` | getter 的函数体迁入该访问器 |
| 实例 setter | `@property.setter ⏎ def x(self, value:T):` | B：同一块内 `def __set__(self, value:T):` | setter 负责实际写入，编译器不再额外赋值 |
| 实例赋值后回调 | `@property.postsetter ⏎ def x(self, value:T):` | B：同一块内 `__get__` + `__set__` + `__post_set__` | 迁移工具补出旧语义隐含的存储和 getter/setter，原回调体放 __post_set__ |
| 字段回调简写 | `x:T @property.postsetter(cb1, cb2) = v` | B：存储字段 + property 块，回调依序放入 `__post_set__` | 保留初始化、回调接收者、0/1 参数及调用顺序 |
| 静态 getter | `@staticproperty ⏎ def x() -> T:` | B 配套建议：`static property x: ⏎ def __get__() -> T:` | 无 self/cls，保持静态访问 |
| 静态 setter | `@staticproperty.setter ⏎ def x(value:T):` | 同一静态块内 `def __set__(value:T):` | 承接旧静态访问器语义 |
| 静态赋值后回调 | `@staticproperty.postsetter ⏎ def x(value:T):` | 同一静态块内 `__get__` + `__set__` + `__post_set__` | 补出原有静态存储/赋值，回调体迁入 __post_set__ |
| 静态字段回调简写 | `x:T @staticproperty.postsetter(cb) = v` | 静态存储 + `static property x:` 块 | 保留原静态初始化和回调，不将实例字段默认值误改为静态字段 |
| 访问器存储槽 | `self.__value__`、`Self.__value__` | 保留兼容引用；新块可直接访问显式存储，如 `self._x` | 仅对应访问器/描述符上下文；不由属性名自动猜测 _x |
| 原生字段名 | `x:T @native_name("c_field")` | 保持 | FFI 与名称映射元信息 |

const 初始化目前不等于任意常量求值，`1 + 2` 等不能因为新拼法自动获得支持。final 的现有构造提取主要处理顶层赋值，完整控制流确定赋值另行实现。旧字段标记 final+property、final+optional、thread_local+const/final/property 等限制保持。旧 postsetter 与手写 getter/setter 互斥只是旧入口规则；新 property 块明确允许 __get__/__set__/__post_set__ 共存，不沿用该互斥检查。

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

| 块内声明/操作 | 拟定语义 |
|---|---|
| `__get__(self)` | 读取 `obj.x` 时调用；缺少时不可读 |
| `__set__(self, value)` | 写入 `obj.x = expr` 时调用；缺少时不可写 |
| `__post_set__(self, value)` | 可选；要求同块有 __set__，在 setter 正常返回后调用一次 |
| 仅 getter | 只读属性，不等于 backing field 为 final |
| 仅 setter | 只写属性，读操作给出明确诊断 |
| setter + hook | 合法组合；setter 抛错不运行 hook，hook 抛错不回滚已完成的写入 |
| 静态块 | 对应访问器无 self/cls，使用 Self 访问类成员 |

每次属性写入只求值一次接收者和 RHS，绑定本次赋值参数后执行 setter，再把该次赋值参数传给 hook；不会重读 getter 或为了回调重复执行 RHS。参数按项目既有类型/所有权规则传递，不承诺额外深拷贝；setter 消费或移动参数后仍需回调使用的情形必须由所有权检查明确处理。setter 提前正常 return 也应触发 hook，因此后端必须形成包装调用或统一正常退出路径，不能仅把回调追加到用户函数体末尾。直接写 `self._x` 不触发属性 hook；assign/new 的属性写入通过同一 setter 路径触发一次。

属性值类型由 getter 的显式返回类型、setter/hook 的 value 注解、已知 backing field 与 getter 返回表达式共同约束；可推断时允许省略注解，set/post_set 默认返回 None。省略 value 注解不能使访问器变成隐式泛型；不足、冲突或循环推导须明确报错。这是新语义层需要完善的统一推断，不能把现有有限 getter 推断当成已经完整支持。getter 的 @ref、对象存储模型等限定另行保留并检查兼容性。

旧字段属性迁移为块时，需要保留字段默认值、元数据、dataclass 构造参与规则及反射映射；生成 backing field 必须避开已有名称。旧 postsetter 的自动写入只能转换一次，不能既合成 setter 又让旧 emitter 再自动写入。迁移期旧属性写法继续接受，同名新块与旧属性声明混用报重复声明；descriptor 的类级 __get__/__set__ 协议不改为属性块。

泛型和类型语法除新增可空后缀 T? 外保持现有拼法，进入专用类型节点。

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
| 显式类型捕获 | `def f[T, _U = ...](x:T):` | 保持 | _U 在类型模式中绑定，不是普通默认值 |
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

类型 parser 只在配对括号之后存在 -> 时把该组括号识别为参数类型表；否则沿用原分组/元组类型规则。因此 `(int, float)` 是元组类型，`(int, float) -> str` 是两个参数的 Callable 类型。返回侧递归调用类型 parser，`(A) -> (B) -> C` 等价 `(A) -> ((B) -> C)`；-> 比类型应用、后缀 ? 和返回侧 @ 标记绑定更弱，外围逗号、= 和声明冒号终止当前类型。`def make() -> (int) -> str:` 的第一个 -> 属于函数声明，余下部分是返回的 Callable 类型。

-> 不加入普通表达式二元运算符表。变量/字段/参数注解、函数返回和 type 别名 RHS 直接进入类型 parser；在已有显式泛型应用的类型实参位置也使用同一规则，外层名称是否确为泛型仍由绑定检查。`value = (int, float) -> str` 不创建运行时类型对象，应报告需要类型上下文；`value = (a,b) => ...` 才是 lambda 表达式。类型别名是该 Callable 类型的别名，不创建新的名义委托类型。

与可空和引用标记组合时必须保存括号的作用范围。

| 拟定写法 | 归属 |
|---|---|
| `(int?) -> str` | 参数值可空 |
| `(int) -> str?` | 返回值可空，Callable 本身不因该 ? 可空 |
| `((int) -> str)?` | Callable 整体可空 |
| `(T @ref) -> R` | Callable 签名中的引用参数 |
| `(T) -> (R @ref)` | Callable 签名中的引用返回 |
| `((T) -> R) @ref` | 对 Callable 值本身的引用 |

-> 后未括起的 `R @ref` 仍归返回类型 R；修饰整个 Callable 的 @ref/@lazy 等标记必须括起整个箭头类型。引用签名可由语法表示，实际可调用性还需沿用并验证 ABI/生命周期规则；例如现有空槽返回 `Ret()` 的实现无法直接用于 `Ret=T&`，不能只改类型拼法就宣称引用返回已完整。

当前 PyCallable 是按值 struct，`((A) -> R)?` 按既定值类型规则形成 NullableValue(Callable)，不改为 C# delegate 引用模型。没有值的 None 与“有值但尚未绑定处理器的 Callable 空槽”不同；后者现有 bool 为 False、可调用时返回默认值或执行空操作。?? 检查外层有无值，不能用 bool(slot) 判断；! 不解包该 nullable。改变空槽行为属于另一个运行时变更。

AST 新增 `CallableTypeSyntax(parameter_types, return_type, span)`，保留括号/箭头范围；旧 Callable 拼法经绑定确认内建身份后也规范化到相同语义类型。兼容桥递归生成 `ast.Subscript(Name("Callable"), Tuple([List(parameter_types), return_type]))`，返回 None 保留无值节点；合成的内建标记不得被同名用户符号遮蔽。复用 `src/analysis/type_parse_ast.py:148` 的签名递归解析及 `:220` 的 `TypeNode.template("Callable", "PyCallable", ret, *args)`，不走 Function 的函数指针节点；最终原生绑定直接构造该 TypeNode，避免字符串重解析。可空与 @ 标记按共同类型规则处理，不能擦掉或借旧 Optional 自动取值完成桥接。

需验证新旧写法的类型相等、ABI/参数顺序、None 返回、别名/外层泛型、容器/高阶/元组的嵌套、函数声明双箭头、=> 初始化的目标签名传播、括号/缺失返回类型/非法参数表诊断，以及可空 Callable 与有值空槽的区别。现有证据为 `test/core/test_delegate.py:59` 的 Callable 参数调用、`:63` 的零参数无值调用、`:106` 的返回 Callable、`:269` 的空槽行为，以及 `templates/core/delegate.h:99` 的存储模型；这些证明已有部分能力，不代替新语法验收。

新增可空语法按 C# 14 的对应规则设计；空值仍写 None。完整的值/引用分类、短路、转换、流分析及旧 Optional 适配见[可空语义方案](./nullable-semantics.md)。

| 功能 | 当前形式 | 迁移后拟定语法及行为 |
|---|---|---|
| 可空值 | `a: int \| None` | `a: int? = None`；int 值或空，0 是有效值 |
| 可空引用 | 引用模型类及原 T\|None 标记 | `node: Node?`；与 Node 相同运行时存储，增加静态可空注解 |
| 可空位置 | 现有嵌套类型注解 | `list[int?]`、`list[int]?`、可空参数与返回值 |
| 条件成员访问 | 手写空值分支 | `a?.x`；为空返回 None，否则访问 x |
| 条件调用 | 手写分支后调用 | `a?.method(args)`；为空时实参也不求值 |
| 条件下标 | 手写分支后索引 | `a?[i]`；只保护空接收者，不吞越界/缺失 key 异常 |
| 连续条件访问 | 多级手写判空 | `a?.b?.c`；与 `a?.b.c`、`(a?.b).c` 区分链边界 |
| 空值抑制 | 无等价纯静态后缀 | `a!`、`a!.x`；只抑制可空诊断，不检查、不解包、不改变运行时值 |
| 空合并 | 显式判空后选值 | `a ?? fallback`；左值非空才采用，否则惰性求 RHS；与 or 不同 |
| 空合并赋值 | 判空后初始化 | `a ??= create()`；左侧为空才求值/赋值，左侧求值一次 |
| 条件赋值 | 判空后写入 | `a?.x = make()`、`a?[i] = make()`；按 C# 14 合法引用目标规则，空时跳过索引/RHS/setter/hook |
| 条件复合赋值 | 判空后更新 | `a?.x += delta()`、合法目标上的 `a?.x ??= make()`；保护读改写，不能作为可取引用变量 |

关键类型约束：`n: int?` 时 `x: int = n!` 仍是类型错误，取值须用 ?? 提供默认或显式取值/转换。引用类型的 ! 不保证运行时非空，随后普通解引用仍可能抛空引用异常；新引用语义须补齐运行库失败路径。泛型 T? 按声明处约束解释，未约束 T 实例化为 int 不自动变成 int?。现有 select 字符串 DSL 的 ? 仍按自身规则，不与主语言条件访问混用。

类型条件需要区分三套现有能力。

| 功能 | 当前写法 | 迁移后 | 边界 |
|---|---|---|---|
| 函数类型分支 | `if T is int: ... elif T is str: ... else: ...` | 保持 | 每个函数一条类型链，不能并列/嵌套多条 |
| 无 else 的类型分支 | `if T is int: ...` | 保持 | 未匹配的实例化产生静态断言；首分支为 is not 时仍要求 else |
| 类型集合分支 | `T in [int, float]`、`T not in {str, bool}` | 保持 | 编译期类型比较，非运行时类型对象集合 |
| 类型形状匹配 | `T is list[...]`、`T is dict[str, ...]` | 保持 | ... 为类型模式通配 |
| 类型捕获与守卫 | `T is list[_U] and _U in [int,float]` | 保持 | 函数头先声明 _U = ... |
| 正向析取 | `T is int or T is float` | 保持 | 当前 OR/AND 支持受限，不代表任意布尔式 |
| 负向类型判断 | `T is not int` | 保持已有范围 | 当前首分支/else 等限制保持 |
| 泛型类类型分支 | `class C[T]: ⏎ if T is int: ... else: ...` | 保持 | docstring 后首条；可跟共享成员；不能用于 protocol/enum/union |
| 条件类型别名 | `type Elem[T, _U = ...] = _U if T is list[_U] else T` | 保持 | 当前是正向 is 模式；不是函数类型 if 的全部条件能力 |
| 条件别名链 | `A if T is P else B if T is Q else C` | 保持 | 当前语法必须有最终 else |
| 不匹配拒绝 | `type Only[T, _U = ...] = _U if T is list[_U] else Never` | 保持 | 显式 Never，不采用无 else 的假语法 |
| 宏条件 | `if "WIN32" in __macro__: ...`、`elif "X" not in __macro__:` | 保持 | 宏名常量字符串；独立宏分支链 |

这些旧入口与新增 inline if 及推荐的 type match 分开保留。旧函数 type if 的具体类型优先/类型模式匹配、无 else 时的未覆盖诊断，以及类 type if 的位置/else 限制，不能通过加 inline 或改成 type match 机械迁移；宏条件的选择发生在 C++ 预处理阶段，也不等于前端已知的布尔常量。新静态分支的源序选择与实例剪枝规则见下文。

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
| 构造及附加字段初始化 | `new(positional, field=value)` | 保持 | 匹配 __init__ 的关键字用于构造，其余合法可写字段/property 在构造后赋值；optional 可参与，final/frozen 不允许事后写入 |
| 批量字段赋值 | `obj.assign(x=1, y=2)` | 保持 | 编译期展开、字段可写性检查 |
| 选项对象批量赋值 | `obj.assign(**opt)`，opt 来自 `**kwargs: Options` | 保持 | 选取 Options 与接收者共有的可写字段，不要求字段集合相同，不是任意动态 dict 展开 |
| 委托操作 | `d += handler`、`d -= handler`、`d(x)` | 保持 | 包括现有受限 lambda/绑定方法 |
| 无参数 lambda | `lambda: 1` | B：`() => 1` | 表达式体，调用时返回 1 |
| 单参数 lambda | `lambda x: 2*x` | B：`x => 2*x` 或 `(x) => 2*x` | 一个普通参数，可省略参数括号 |
| 多参数 lambda | `lambda a,b: a+b` | B：`(a,b) => a+b` | 参数括号必需，不是元组解构 |
| 旧 lambda 写法 | `lambda x: x + 1` | 继续接受，与箭头形式共用语义 | Callable/委托/聚合 key 等当前支持范围见下文 |

箭头 lambda 的参数和函数体规则如下；它是现有 lambda 的替代拼法，沿用 Py2Cpp 的参数绑定和对象模型。

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
| `x => y => x+y` | `x => (y => x+y)`；嵌套闭包语义另行验收 |
| `fallback ?? (x => x)` | 合并已有 callable 与 lambda；括号明确 lambda 边界 |
| `f(x => x+1, y)` | f 的两个实参，第一个是 lambda |
| `x => (x, x+1)` | lambda 体是显式括起的元组表达式 |
| `(x => x+1)(2)` | 语法上调用括起的 lambda；通用立即调用路径尚待实现 |

自有 AST 使用 `LambdaExpr(parameters, expression_body, syntax_kind, span)`，syntax_kind 区分旧 lambda 与箭头来源，不形成不同 callable 类型。Lexer 将相邻的 => 识别为独立 token，与 =、==、>=、-> 区分；字符串/注释内容不改写。Parser 在表达式起始位置前瞻 NAME => 或完整括号参数头后的 =>；没有 => 时仍解析普通分组/元组，已看到 => 却遇到非法参数头或缺少函数体时给出定点诊断。不能先把 (a,b) 变成元组值再逆推出参数，也不能用正则把箭头转换为冒号。

兼容桥对当前支持的参数形状构造 `ast.Lambda`，普通参数放 `ast.arguments.args`，不放 posonlyargs；保留参数头、箭头及函数体的 SourceMap。旧 lambda 与新写法通过同一绑定/类型/捕获流程。若函数体含 ?.、??、??= 等需要分支或临时变量的节点，lowering 必须保持这些计算在 lambda 调用体内；当前表达式 AST 装不下时使用明确的内部函数体/HIR，不能在创建 callable 时提前执行。

当前语义支持仍是局部路径：Callable 变量、委托处理器、部分已有 Callable 目标类型的实参/字段初始化及 min/max 的 key。`src/emit/delegate_emit.py:157` 仅验证普通位置参数、无默认值，却漏查 posonlyargs；`src/translator.py:5232` 默认把无注解参数设为 int，`src/emit/delegate_emit.py:28` 把推断返回槽固定为 int，首次 Callable 注解变量路径 `:217` 也没有把目标形参传给 lambda 发射器。开放箭头时应共用并补齐目标签名传播、函数体返回检查和已支持上下文的推断；无足够类型信息时明确诊断，不能把这些 int 回退当作永久语言规范。显式 Callable 示例也须验证实际参数/返回类型，不能只验证容器类型。

现有函数作用域 lambda 实际使用引用捕获 `[&]`（`src/translator.py:5263`）；`templates/core/delegate.h:556` 已拥有 lambda 对象，但不延长引用捕获的局部变量或 self 的生命期。首期沿用有效的受限捕获能力，逃逸时须满足被捕获对象生命周期；完整逃逸闭包、直接返回 lambda、立即调用和嵌套 lambda 还缺通用表达式发射与环境管理。解析器可以识别这些形状，未完成语义支持的组合必须明确诊断，不能凭生成 ast.Lambda 就称为已支持。

待实现验收包括三种用户指定写法与旧 lambda 的规范化 AST/行为等价，普通括号与参数表消歧、尾逗号/重名/非法参数头、缺失函数体、逗号和右结合、Callable/委托/key 上下文中的参数与返回检查、捕获的有效生命周期，以及 ?. / ?? / ??= 的副作用只在调用体内发生。同时记录立即调用/返回/嵌套等尚未开放场景的诊断；本次仅更新方案。

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

控制流、异常和异步语法如下。

| 功能 | 当前写法 | 迁移后 | 边界 |
|---|---|---|---|
| 普通分支 | `if/elif/else` | 保持 | 运行时分支 |
| 显式编译期分支 | 当前仅有特定位置的常量 if 折叠，没有统一入口 | B：`inline if cond: ... elif cond2: ... else: ...` | 首个命中分支在编译期选定；条件须可求值，不回退为运行时 if |
| 显式编译期模式分支 | 现有 match 与字段 annotation 匹配各有专用路径 | B：`inline match subject: ⏎ case pattern if guard: ...` | 编译期按源序选择首个模式及守卫均命中的 case；guard 可省略；静态值与模式范围见后文 |
| 显式类型匹配 | 现有类型 if，没有类型模式的 match 入口 | B 推荐：`type match T: ⏎ case list[int]: ... ⏎ case str: ...` | case 中裸名称为类型引用，_ 为通配；天然编译期分支，无隐式变量捕获 |
| 条件表达式 | `a if cond else b` | 保持 | 与条件类型别名分开 |
| while | `while cond:` | 保持 | 静态可发射表达式 |
| for | `for x in xs:` | 保持 | 普通目标以简单名为主 |
| range 循环 | `for i in range(n):`、`for i in range(a,b):`、`for i in range(a,b,s):` | 保持 | 非循环表达式 range(...) 仍是库对象 |
| enumerate/zip | `for i,x in enumerate(xs):`、`for a,b in zip(xs,ys):` | 保持 | 专门平坦解构路径 |
| 循环 else | `for/while ... else:` | 保持 | 用户 break 抑制 else |
| 流程跳转 | `break`、`continue`、`return`、`return value` | 保持 | 所处循环/函数限制保持 |
| 空语句 | `pass` | 保持 | 原生/抽象桩仍要求 ... |
| 删除下标 | `del obj[i]`、允许容器的 `del obj[i:j]` | 保持 | 单下标目标；不是通用 del |
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

本次不将 inline 泛化到任意 iterable、prange、推导式或 async for，也不增加 inline def；`inline for i in inlineRange(...)` 是重复标记，给出诊断。旧 for i in inlineRange(...) 与新写法都规范化为 `ForStmt(..., expansion=InlineRange)`；绑定后生成统一的 `RangeBounds(start, stop, step)` 求值计划。不得通过删除 inline 而保留普通 range 来实现，否则会变为运行时循环。

兼容桥生成带来源信息的 `ast.For(iter=Call(Name("inlineRange"), 原实参), ...)`，保留目标和 body，走同一个展开器。展开必须等待宿主常量可用：mixin 路径保持 iterFields/fixed-vararg 之后的位置（`src/passes/mixins.py:586`、`:610`），普通方法保持现有发射前的上下文（`src/emit/loops_emit.py:582`）。parser 只建立语法节点，不提前解析 Self._dim；克隆节点记录原循环及迭代值，诊断定位到新循环头/原循环体。

验收包括三种参数数量、默认边界、正负步长/空范围/零步长、宿主常量和嵌套依赖、常量 if 折叠及运行时副作用顺序，确认新旧展开结果相同且没有对应运行时循环；同时覆盖动态边界、非法运算、for-else、目标和 break/continue 的既有拒绝行为，及 inline 作为普通名称。已有依据为 `src/passes/inline_range.py:69`、`:120`、`:220`、`src/tests/test_inline_range.py` 和 `test/lang/test_inline_range.py`；本次仅更新方案，未迁移库源码或实现新 parser。

新增 inline if 表示显式编译期选择，语法为：

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

设计目标覆盖函数/方法语句、普通类成员和模块声明位置；所选语句仍须满足该位置已有规则，不为 enum/protocol 等受限声明体增加任意语句。模块中的条件 import 只在选择后登记依赖；类中的条件字段/方法只进入当前有效成员集合，参与布局、dataclass 和反射。相同名称若只出现在互斥分支，不因未选声明报重复；与实际保留的其他声明冲突仍报错。函数中的局部绑定与返回类型检查以所选分支为准，未选分支不满足也不妨碍当前实例的确定赋值。未实例化泛型保存条件树，各特化有独立的有效声明集合。

声明条件只能依赖在选择前独立可求的值/类型。先建立不含条件分支成员的声明骨架与常量依赖图，提供外层类型形参、宿主身份及无条件常量，再选择分支，最后建立完整的 ClassInfo/成员集合。若常量、导入或反射成员集合反过来依赖该条件正在控制的声明，报告依赖循环，不能通过先注册所有分支来求值。受控模块导入的发现、属性/dataclass 展开和反射收集都须使用选择后的视图；类型/NTTP 相关条件在特化前不得过早合并分支。

本项与现有能力的兼容边界如下。

| 现有能力 | 与 inline if 的关系 |
|---|---|
| 普通常量 if 折叠 | 原入口保持；新 inline if 增加强制编译期求值与未选分支隔离，不能只删除 inline |
| inlineRange/inline for 内折叠 | 新节点必须先求条件再展开选中体；旧 `_flatten_stmt` 先遍历两个分支，不能原样接入 |
| inline for 的跳转限制 | 仍先扫描原循环体的 break/continue；`inline if False:` 包住 break 也不能绕过已约定的结构限制 |
| 旧函数/类 type if | 保留原分派语义；具体类型优先/模式匹配及无 else 的静态断言不改成新链的源序/no-op；迁移须逐例验证 |
| `if "X" in __macro__` | 保持现有 C++ #ifdef 路径；首版 inline if 不接受 __macro__。未来若加入，须显式提供目标构建宏环境并纳入依赖/缓存 |
| C++ 后端 | 保持 C++11；前端剪枝或生成等价特化分派，不能依赖 C++17 if constexpr |

具体实现建立 `InlineIfStmt(branches, else_body, span)` 与 `StaticIfBranch(condition, body, span)`，保留整条链及各分支原始范围；`else: inline if ...` 与 elif 链要保存结构区别。绑定只查询判定条件所需的环境，静态求值返回 KnownBool、Dependent 或 Error；未选择前不访问分支语义。复用模块/实例的常量值、TypeId 和宿主上下文；短路求值、选中分支展开及所有权/控制流检查分层执行。克隆记录选择条件、实例参数及原分支来源。

兼容桥先对已知条件输出选中语句序列，空序列在要求非空 suite 的位置补合成 pass；不要把 InlineIfStmt 改成普通 ast.If 后交给旧 visitor。依赖条件必须留在自有节点/中立 IR 中直到特化，或经验证后生成专用的 C++11 分派，不能让旧 type_if 仅凭 `T is int` 的形状接管。mixin 与循环索引绑定后，按从外到内的顺序穿插 inline for 展开及 inline if 选择，未选分支中的无效展开边界不能报错；原有 break/continue 结构预检仍先行。

交付按两个步骤验收：先完成当前环境已知条件的函数/方法分支和 inline for 联动；再完成依赖特化与模块/类声明剪枝。在后一步落地前，对尚不支持的位置/依赖明确诊断，不把只能处理 `inline if True` 的原型标为全部完成。验收包括 if/elif/else 首次命中与无 else、严格 bool、短路避开未求值错误、宿主/索引/NTTP/TypeId 条件、嵌套及多链、未选分支不存在成员/无效展开被隔离、语法/结构错误仍报、声明/导入/布局/反射不污染、实例隔离与依赖循环，以及最终无对应运行时 if。

审计依据：`src/passes/inline_range.py:271` 先展开两个分支；`src/passes/static_reflect.py:49` 的常量比较仅覆盖 ==/!=，`src/passes/match_case.py:633` 另有有限真值/not 折叠；`src/passes/type_if.py:1162` 先匹配具体类型、`:1698` 生成无 else 的未覆盖断言；`src/passes/macro_if.py:125` 发射每个分支后交 C++ 预处理选择。上述差异均需独立处理，本次仅增加设计。

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

普通 match 保持项目现行形式，不能统一写成“支持全部 Python match”；新增 inline match 的静态选择规则紧随对照表说明。

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

type match T:
    case list[int]:
        self.processIntList()
    case int:
        self.processInt()
    case _:
        self.processOther()
```

前两个示例使用 inline match；第三个展示本轮推荐的 type match，类型 case 规则见下一节。inline 作用于整个 match，内部仍写 `case pattern [if guard]:`，至少一条 case；不增加 inline case、match-else 或 match 表达式。支持嵌套，以及与普通控制流、inline if/inline for 组合。此前 `inline match T: case U if U is int:` 的元值/守卫形式继续保留；其中 TypeId 由绑定阶段识别，普通名称模式始终是捕获，不根据主体切换为类型模式。

| 规则 | 拟定语义 |
|---|---|
| 主体求值 | 在当前编译/特化环境中求值一次，得到带目标类型的 CompileTimeValue；即使只有 case _ 也须满足编译期求值要求 |
| 选择次序 | 按源码顺序尝试模式；模式成功后才求 guard，guard 为编译期 True 或省略时选择该体并停止 |
| 守卫 | 必须得到 bool，沿用 inline if 的运算与短路规则；模式失败时不求 guard，guard 为 False 时继续下一条 case；通配模式也保留守卫 |
| 待绑定依赖 | 主体、当前所需模式值或 guard 为 Dependent 时保留尚未完成的选择；不能跳过该 case 去选后续 case _；运行时依赖为错误，不能标成 Dependent |
| 无匹配 | 产生空语句序列，不要求 _ 或穷尽性证明，也不生成隐含静态断言；与 inline if 无 else 一致 |
| 未选分支 | 全部 case 仍须通过词法、语法及必要结构检查；未选体不作常规名称/成员解析、类型检查、展开或声明登记 |
| 选中分支 | 所选语句插入原作用域和运行时位置；正文副作用仍在运行时执行，不生成对应的运行时 match/switch |
| 控制流 | 不建立新的函数或循环；return/break/continue 绑定原上下文，并保留 inline for 对整个原循环体的 break/continue 禁令 |

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

捕获是该 case 的 guard/正文内不可变的编译期局部绑定，失败模式及 guard 为假均不泄漏，也不覆盖外层同名变量；离开 case 后不可引用该捕获。正文中其他声明仍遵守原作用域规则。禁止对捕获赋值、增量赋值或取得可写引用；需要可变局部时显式复制到另一个名称。引用捕获的节点通过 SymbolId 绑定，在所选体中物化为保留目标类型的常量，避免按名称替换破坏嵌套 lambda/函数的参数遮蔽；TypeId 只进入合法类型或静态判断上下文，不物化为运行时字符串/类型对象。捕获进入 lambda 时按常量绑定处理，不产生对临时 case 变量的悬垂引用。

所有 case 的必要结构预检包括模式种类是否在当前静态 profile 内、同一模式重复捕获、OR 捕获名集合一致性，以及无 guard 的不可反驳模式必须位于末尾；带 guard 的捕获/通配模式允许后接 case。OR 内不可反驳的备选也只能位于最后，case guard 不能让被该备选遮蔽的后续备选重新可达。捕获类型一致性在有主体类型的模式绑定阶段验证。名称解析、模式值与 guard 求值仅针对实际需要尝试的路径；已经选中后，不求后续 case 的值或 guard。外层 inline for 的全子树跳转预检先行，因此未选 case 中的 break/continue 也不能绕过既有限制。

模块/类中的 inline match 与 inline if 共用声明骨架、常量依赖图及每个实例的有效声明视图：先获得独立可求的主体和模式环境，选出 case，再登记其 import、字段、方法、属性、dataclass 与反射成员。所选内容须满足当前位置规则；未选声明不制造重名或改变布局。主体/guard 依赖自己控制的声明或布局时报告循环，未实例化泛型保留原树；不能提前注册所有 case 来获得求值环境。

实现使用 `InlineMatchStmt(subject, cases, span)` 与 `StaticMatchCase(pattern, guard?, body, span)`，复用普通 Pattern 的语法结构并保留 case/guard/捕获位置。inline if 与 inline match 共用 `CompileTimeValue`、`StaticEvalResult = KnownValue / Dependent / Error`；inline if 的 KnownBool 是要求 KnownValue 为 bool 的专用结果。模式匹配返回 `Matched(bindings)`、`NotMatched`、`Dependent` 或 `Error`，在 case 局部环境中求 guard，失败就丢弃绑定，成功才展开正文。依赖键包含目标类型、特化实参和宿主/常量环境，克隆来源记录所选 case 及捕获值。

兼容桥对已选结果输出带来源的语句序列，要求非空 suite 时补 pass；依赖结果留在自有树/中立 IR，等特化后继续。不能改回普通 ast.Match 再调用 emit_match，也不能借用字段 annotation matcher：旧通配分支可能丢失 guard，union 会按变体分组，annotation 按固定元数据优先级选择。S0803 的末尾默认分支/穷尽性检查及旧 visitor 的全部 case 语义遍历应按来源隔离；普通 match 继续原有检查，不能全局关闭 strict。旧 runtime 的 bool/int 及单字符匹配与上述静态分类也有差异，迁移工具不机械给普通 match 或 annotation match 加 inline。

P3 中先与 inline if 共用已知值的函数/方法选择及 inline for 联动，再接入依赖特化和模块/类声明剪枝；结构化静态值另列增量交付。验收包括主体单次静态求值、字面量/枚举/TypeId、严格类别与整数边界、源序首个命中、带 guard 的通配、模式失败不求 guard、guard 假继续、OR guard 不重试、Dependent 不越过、无匹配为空、捕获不泄漏/只读/常量物化/遮蔽、未选体隔离与全分支结构检查，以及声明、实例和循环展开顺序。生成结果无对应运行时分派，正文副作用仍保持原位置；旧普通/union/Optional/annotation match 独立回归。

核查依据：`src/passes/match_case.py:978` 的普通模式发射、`:987` 的单字符转换、`:1462` 的通配提取；`src/passes/union_match.py:106` 的变体分组与 `:151`、`src/passes/optional_match.py:184` 的穷尽性要求；`src/passes/strict_style.py:2078` 的 S0803 与 `:4678` 的 case 语义遍历；`src/passes/match_case.py:220`、`:480` 的 annotation 特殊规则及 `src/passes/mixins.py:595` 的提前展开。这里只新增语法/实现方案，未修改这些现有路径。

本轮类型匹配建议采用显式 `type match`。用户提出的两种形式都可在自有 parser 中实现，区别在于是否让同一个名称模式随主体类别改变含义。

| 方案 | case str / case list[int] 的解释 | 取舍 |
|---|---|---|
| 普通 match 根据主体切换 | 主体绑定为类型时按类型匹配，否则按值模式 | 少一个前缀；需要先保存歧义节点，绑定后才能确定捕获与类型引用，影响后续名称作用域、重命名及语法工具 |
| 显式 type match（推荐） | 在整个块内固定按类型模式解析 | 多一个 type；parser 可独立确定模式种类，拼写错误可直接报未知类型，值匹配的捕获规则保持稳定 |

不采用“能解析为类型名就匹配类型，否则当捕获”的回退规则；否则漏写 import 或类型拼错会悄悄变成全匹配。完整的推荐分工为：

| 入口 | 匹配对象与阶段 | case 中裸名称 |
|---|---|---|
| `match value:` | 现有值模式与既有展开入口 | 捕获变量 |
| `inline match value:` | 编译期可求的值；保留此前 TypeId 元值 + guard 路径 | 编译期捕获 |
| `type match T:` | 编译期类型身份/随后扩展的类型形状 | 已声明类型引用；不隐式声明变量 |

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

type match 本身表示编译期选择，不必叠加 inline；首版只开放这一种顺序，不另加 inline type match/type inline match。T 在绑定时须代表类型，首版主体包括类型形参、已声明类型/别名及合法的已构造类型表达式；`type match value:` 若 value 是运行时对象则报错，不隐式执行 type(value) 或 isinstance。它不新增运行时动态类型检查。

| 类型模式 | 首版拟定规则 |
|---|---|
| `case str:`、`case pkg.Model:` | 解析为 TypeExpr 并绑定已声明类型，按精确类型身份比较；名称不存在时报错，不回退成捕获 |
| `case list[int]:`、`case dict[str, int]:` | 精确构造类型，包括泛型实参；不表示“某个 list 子类”或允许元素隐式转换 |
| `case list[U]:` | U 必须是外层已声明的类型参数/别名；未绑定实参则延迟匹配，不将 U 作为新捕获；未知 U 报错 |
| `case int \| float:` | case 顶层为类型模式 OR，任一精确匹配即可；匹配成功后 guard 只求一次 |
| `case _:` | 唯一的顶层通配符，不引入名称；无 guard 的通配 case 必须最后 |
| `case str if cond:`、`case _ if cond:` | 模式成功后求编译期 bool guard；False 则下一 case，Dependent 阻止越过，运行时条件报错 |
| 类型别名/限定 | 透明别名先展开，名义类型身份保留；数组维度、值实参、引用限定及 Callable 签名按统一类型相等规则处理，不比较 C++ 类型文本 |
| 可空类型 | 值类型 `int?` 与 int 不同；引用模型的 Node/Node? 只差可空注解，具有相同类型身份，不能据此分派；不读取对象当前空状态 |
| 后续类型形状 | 拟复用已有 `list[...]`、`dict[str, ...]` 的匿名形状含义，独立增量实现；不与 inline match 的运行时容器内容模式混淆 |
| 具名解构捕获 | 留待显式语法/作用域设计；首版不把 `list[U]`、`list[_U]` 或 `as U` 自动变成类型参数捕获，旧 `_U = ...` 类型 if 路径保留 |

精确相等与“继承自某类”“满足某协议”“可转换成某类型”分别建模；`case Base:` 仅匹配 Base，`case SomeProtocol:` 不表示所有实现者。需要这些关系时再增加明确的模式/静态 intrinsic，不能把运行时 is-a 语义混入首版精确匹配。泛型实参是否已绑定与名称是否存在分开诊断，前者可以是 Dependent，后者为 Error。

case 层的顶层 `|` 固定为 OR 分隔，括号/类型实参内部仍用类型文法；可空类型优先写 `case int?:`，不把 `case int | None:` 解读成可空类型整体。允许在明确类型括号内使用已支持的可空兼容拼法；不因类型匹配而新增一般 union type。Callable 的 -> 继续采用原类型优先级，参数括号与元组类型保留；case 头在顶层 if 或冒号处结束，不把 guard 当作条件类型别名 RHS。_ 仅在类型模式位置特殊，`list[_]` 不成为匿名形状的新拼法。

type match 复用 inline if/match 的源码顺序、严格 bool 守卫、Dependent/错误区分及选中体剪枝：全部分支先解析并做必要结构检查，按实际尝试路径绑定模式/guard，只选择第一个成功 case；无命中为空。泛型未绑定时保留原树，到对应特化再选，不预先选择 _。所选体插入原作用域，副作用留在运行时，未选体不登记声明或作常规语义检查。嵌套、模块/类声明视图与 inline for 全子树跳转限制也共用既定规则。完整函数仍检查所选路径的返回值与确定赋值，不因无命中为空而自动补默认返回。

语法 AST 使用独立 `TypeMatchStmt(subject_type, cases, span)`、`TypeMatchCase(pattern, guard?, body, span)`；首版 TypePattern 为 ExactTypePattern(TypeExpr)、AnyTypePattern、TypeOrPattern。parser 通过 type match 前缀进入类型模式规则，名称只产生 TypeExpr，不产生值模式的 CapturePattern；绑定器将主体和模式转为规范化 TypeId，引用可空注解与类型身份分离。随后形成共用的静态分支选择计划，但保留语法来源和模式种类。已知选择投影为语句序列，空 suite 补 pass，依赖选择保留到特化；不投影为普通 ast.Match，也不依赖 C++17 if constexpr。

可以复用 `src/analysis/type_node.py:245` 的结构化类型相等思路及 `:287` 的类型模式基础，但须先接入稳定 TypeId、别名和可空身份规则；不能沿用字符串相等作为新语义。旧 `src/passes/type_if.py:1162` 先选所有精确匹配再选形状模式，而新 type match 始终按源序；以后若将 list[...] 放在 list[int] 前，前者应先命中。旧类型 if 无 else 时的未覆盖断言、捕获声明和类体位置限制也不能机械搬来。迁移只对逐例验证等价的精确类型链提供建议，其他旧入口继续接受。

将首版 type match 精确类型/OR/_/guard 纳入 P3 静态分支框架；之后再开放匿名形状和另行确定的具名捕获。验收包括 list[int]/str、透明别名与名义类型、外层类型形参、未知类型名不会捕获、值主体拒绝、OR/guard/Dependent、无匹配返回检查、软关键字及 type match 类型别名消歧、Callable/数组/可空类型、实例隔离与未选体剪枝。后续形状模式必须补源序重叠用例；不要用旧 exact-first 发射器的结果作为这种新规则的预期。此节是本轮推荐方案，不表示编译器已经提供 type match。

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
| `del x`、`del obj.field`、多目标 del | 不在已实现删除子集 | 明确诊断 |
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
| dataclass kwOnly/kw_only、slots | 尚未形成可用目标功能 | 另行设计，不标已支持 |
| 任意 metaclass/动态 Python hook | 无完整目标模型 | 不承诺自动支持 |

核查依据主要包括：`py2cpp/builtins.py`、`src/translator.py`、`src/analysis/ir.py`、`src/analysis/analyzer.py`、`src/passes/strict_style.py`、`src/passes/type_if.py`、`src/passes/type_conditional.py`、`src/passes/field_properties.py`、`src/passes/kwargs_options.py`、`src/passes/match_case.py`、`src/emit/fstring_emit.py`、`src/emit/comprehensions_emit.py`，以及 `test/lang/` 和对应 `src/tests/` 用例。模板、select、build、FFI 另对应各自实现与文档。本清单是静态审计和迁移提案，没有为所有语法重新执行编译/运行验证。
