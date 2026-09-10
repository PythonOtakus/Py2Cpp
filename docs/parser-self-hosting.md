**Py2Cpp 自有前端与自举编译器实现方案**

设计提案，初稿 2026-09-08，更新 2026-09-10。本文描述建议实施的工作；新语法、解析器和自举流程尚未实现。

现有语法、拟定新写法及已知支持边界见配套[语法迁移对照表](./syntax-migration.md)。

T?、?.、?[]、后缀 !、??、??= 的 C# 对应规则、流分析及兼容限制见[可空语义方案](./nullable-semantics.md)。该语法族纳入第二批，属于类型系统与运行时共同变更。

箭头 lambda `() => 1`、`x => 2*x`、`(a,b) => a+b` 及 Callable 类型简写 `(int, float) -> str` 纳入第二批；分别表示匿名函数值与调用签名。参数、优先级、类型/捕获边界见语法迁移对照表，旧 lambda 和 Callable 写法继续接受。

`for i in inlineRange(...)` 改为 `inline for i in range(...)`，纳入第二批；保留编译期完全展开及现有边界，迁移期接受旧拼法。

第二批同时新增 inline if：以编译期 bool 按源码顺序选择 if/elif/else 分支，只保留选中体；泛型/宿主依赖在绑定后选择，未选分支不作常规语义检查。它有独立节点和求值规则，旧类型 if、宏条件及普通 if 保持各自语义。

第二批新增 inline match：主体在编译期求值，按源码顺序选择首个模式匹配且 guard 为 True 的 case；未匹配则为空。与 inline if 共用受限静态求值、依赖特化和声明剪枝；首版覆盖标量、枚举及类型身份的静态分支，结构化值模式另行扩展，普通 match 保持原语义。

本轮推荐在第二批增加 `type match T: case list[int]: ... case str: ...`，每个 case 实际换行并缩进。该前缀明确切换到类型模式，裸名称绑定已声明类型，不再是隐式捕获；类型匹配天然在编译期执行。普通/inline match 继续值模式规则，不根据主体或类型名称是否可见自动切换。

建议固定 CPython 3.13 的词法与语法为参考基线，以当前 Py2Cpp 能编译的语言子集实现独立 Lexer、递归下降解析器及 Pratt 表达式解析器，建立自有 AST；将 enum、final 等提升为声明上下文中的软关键字。通过兼容适配层逐步复用现有 passes 和 C++11 后端，随后迁移编译器本体与模板执行器，完成 stage0 → stage1 → stage2 → stage3 自编译闭环。

保留 C++11 后端和外部 MSVC/Clang 不影响转译器自举。自举要求编译器实现语言能编译自身，生成后的编译器能独立运行；不要求同时实现机器码后端。

当前项目的事实基础如下。文件行号以本次审计时版本为准。

| 观察 | 实现证据 | 对方案的影响 |
|---|---|---|
| 导入发现和模块装载分别调用 ast.parse | `src/analysis/import_resolver.py:411`、`src/translator.py:725` | 新前端必须覆盖导入发现，不能只换翻译主入口；可共享解析结果避免重复解析 |
| 主翻译器继承 ast.NodeVisitor | `src/translator.py:162` | AST 是整个编译器的公共数据模型 |
| 装饰器按名称拼写识别 | `src/analysis/ir.py:2051` | 当前核心装饰器实际是编译期语言标记，不是运行时调用 |
| 类型标记借用 MatMult | `src/analysis/ir.py:2193`；`x: T @final` 的 CPython AST 为 BinOp(MatMult) | 自有 AST 应直接表达类型、存储和声明修饰符 |
| 已有结构化类型 IR，但仍有字符串桥接 | `src/analysis/type_node.py:39`、`src/analysis/type_parse_ast.py:1` | 可渐进复用 TypeNode，避免另外重造一套类型系统 |
| 特性展开具有明确顺序 | `src/translator.py:463` 起 | 初期保持顺序，不能在换 parser 时同时重排所有语义 passes |
| 模板由 Python 执行 | `src/codegen/expand_py2cpp_template.py:680` | 去掉 ast.parse 后仍有 CPython 依赖 |
| 现有 bootstrap 是标准库再生成 | `scripts/_bootstrap_runtime.bat:30` | 当前尚未完成编译器自编译 |

静态统计范围为 `src/**/*.py`，排除 `src/tests`：198 个文件、80,022 物理行；123 个模块导入 ast，28 处 ast.parse，48 处 ast.unparse，66 处 ast.walk，305 处 copy.deepcopy，195 处 getattr，以及各 4 处 exec/eval 调用。这些是迁移规模指标，不代表每个调用点都需要独立重写。

本机 Python 为 3.13.14。按当前模块加载器的 BOM 预处理方式进行语法扫描，148 个标准库文件、152 个非 fail 的 test_*.py、36 个负向测试、3 个 examples 文件和 33 个 FFI .pyi 均可通过 ast.parse。这里仅验证可解析性，没有执行全量翻译、C++ 编译或行为回归。负向测试也能通过 Python 语法解析，说明很多语言约束必须由语义层维护。

现有语法应按以下维度整理，避免把所有装饰器机械合并成一组 flags。

| 维度 | 当前形式及语义 | 自有 AST 的建议表示 |
|---|---|---|
| 基础语句/表达式 | 缩进块、函数、类、import、if/for/while、with、try/except*、match、yield、async/await、推导式、f-string、受限 lambda | 保留对应的 Stmt、Expr、Pattern 节点；解析支持与语义支持分别记录 |
| 声明种类 | @enum、@union、@variant、@protocol、@mixin | EnumDecl、UnionDecl、VariantDecl、ProtocolDecl、MixinDecl |
| MRO 派生声明 | @enum.mro、@union.mro；拟改 type enum/type union | EnumDecl/UnionDecl 的显式派生模式与根类型；区别普通底层类型/继承参数 |
| 类与方法规则 | @final、@staticmethod、@virtual、@abstract、@override | ClassModifiers、MethodModifiers；协议静态要求与实体虚方法分别建模 |
| 字段存储/可变性 | T @const、T @final、T @thread_local | FieldStorage、FieldMutability、Initializer；const 是类 static constexpr，final 是实例只读 |
| 类型/参数规则 | T @ref、T @lazy、T @optional | 引用类型、惰性求值参数、字段参与自动构造的选项，分别归属；optional 字段标记与 Optional[T] 类型不同 |
| 泛型及类型语法 | PEP 695/696、type 别名、T: Protocol、A & B、oneof[...]、NTTP、可变类型参数、T[:N]、T[:, :]、T \| None | TypeExpr、TypeParam、Constraint、ArrayType；需要名称解析才能决定的类别先保留未解析表示 |
| C# 风格可空语法 | 新增 T?、?.、?[]、后缀 !、??、??=，包括 C# 14 条件赋值 | NullableTypeSyntax、ConditionalAccessChain、NullSuppressExpr、空合并节点；值可空、引用注解及流状态分开 |
| 匿名函数 | 受限 lambda；拟增加 () => expr、x => expr、(a,b) => expr | 统一 LambdaExpr，记录源写法；支持上下文、目标类型与捕获生命周期单独验证 |
| Callable 类型 | Callable[[A,B],R]；拟增加 (A,B) -> R | CallableTypeSyntax；绑定到现有 PyCallable 类型，与 Function 函数指针和多播 delegate 区分 |
| 编译期循环展开 | for i in inlineRange(...)；拟改 inline for i in range(...) | ForStmt 的 InlineRange 展开模式；绑定宿主后生成 RangeBounds，保持原展开顺序 |
| 显式编译期分支 | 新增 inline if / elif / else；旧入口只有特定常量折叠与类型/宏分支 | InlineIfStmt；静态 bool 求值、依赖特化和选中分支视图，不与旧分派混用 |
| 显式编译期模式分支 | 新增 inline match / case / guard；旧 match 与 annotation 匹配保持 | InlineMatchStmt；共享 CompileTimeValue，源序匹配及 case 局部捕获，只保留选中体 |
| 显式类型匹配（推荐） | type match T；case list[int] / str / _ | TypeMatchStmt、独立 TypePattern；类型引用按规范化身份比较，源序静态选择 |
| 对象模型 | @refcount、@boxing、@copyable、@uncopyable | ObjectModel、CopyPolicy；即使表面保留属性，也必须进入类型与存储语义 |
| 派生与开放属性 | @dataclass、@serializable、@annotation、用户 Meta(...)、@native_name | DeriveSpec、Attribute、ForeignBinding；允许不同维度组合 |
| 访问器和效果 | @property、setter/postsetter 拟改类内 property 块，含 __get__/__set__/__post_set__；@immutable、@noexcept 保持 | PropertyDecl、AccessorDecl、MethodEffects；noexcept 现有 Result 改写不能简化成 C++ 关键字 |
| 编译期结构 | 类型 if、宏 if、静态反射、new/new.Variant、select/build 字符串 DSL、@decorator/@context | 在规范化/语义阶段形成专用节点或展开计划；普通语法解析不查询类型表 |

上述内容已经超过“Python 加几个装饰器”的规模。新 parser 的支持表应以真实源码、正反测试和经确认的语言规则为依据。CPython 可以解析的语法不等于 Py2Cpp 已经实现其运行语义，例如完整动态对象、Any、任意字典关键字解包、闭包逃逸等不能因为换 parser 就自动开放。

建议首先引入下列新写法，所有示例均为拟议语法。

```text
enum ModeEnum(int64):
    Off = 0
    On = ...

enum AccessFlag(flag=True):
    Read = ...
    Write = ...

type enum KindTypeEnum(base=Animal):
    pass

final class Config:
    const BufferSize: int = 4096
    final mode: ModeEnum = ModeEnum.On

class Handler:
    final def value(self) -> int:
        return 42
```

| 旧写法 | 新写法 | 保持的语义 |
|---|---|---|
| @enum + class E | enum E | 普通枚举；默认 int，可写 int64 或一个父枚举 |
| @enum(flag=True) + class F | enum F(flag=True) | Flag 自动取下一 2 的幂；flag 是命名选项 |
| @enum.mro + class KindTypeEnum(base=Animal) | type enum KindTypeEnum(base=Animal) | MRO 闭集派生枚举；保留手动成员和 of/create 能力 |
| @enum.mro + class ChildTypeEnum(KindTypeEnum) | type enum ChildTypeEnum(KindTypeEnum) | 继承父派生枚举，子声明不再写 base= |
| @final + class C | final class C | 禁止继承 |
| @final + def f | final def f | 方法隐含 virtual，禁止覆盖；首版限原来允许的成员方法位置 |
| x: T @final | final x: T | 实例只读字段及构造初始化规则；不同时新增局部 final 变量语义 |
| x: T @const = v | const x: T = v | 类级编译期常量；不改成普通实例 const |
| @union/@variant + class | union/variant 声明 | 保留带标签载荷的联合与变体字段 |
| @union.mro + class ErrorTypeUnion(base=Exception) | type union ErrorTypeUnion(base=Exception) | 第二批加入；保留闭集、附加变体、嵌套 Enum 与转换能力 |
| @protocol/@mixin + class | protocol/mixin 声明 | 保留结构约束/编译期混入，分别实施 |
| @staticmethod/@virtual/@abstract/@override + def | static/virtual/abstract/override def | 第二批加入；先冻结组合矩阵 |
| @property/@property.setter 的同名方法 | property x: 块内 __get__/__set__ | 第二批加入；同一属性的访问器收拢到独立作用域 |
| @property.postsetter 方法或字段简写 | property x: 块内 __get__/__set__/__post_set__ | 原自动存储和写入显式展开；新 setter 正常返回后运行 hook |
| @staticproperty 及 setter/postsetter | 配套建议 static property x: 块 | 访问器不接收 self/cls，沿用 Self 和静态存储语义 |
| T\|None、显式判空分支 | T?、?.、?[]、??、??= | 第二批加入；采用 C# 对应规则，旧 Optional 的兼容转换不能只换拼法 |
| 无纯静态后缀 | expr! | 第二批加入；仅抑制可空分析，不检查、不解包、不改变运行时值 |
| lambda: e、lambda x: e、lambda a,b: e | () => e、x => e、(a,b) => e | 第二批加入；相同表达式体与受限 callable 语义，旧写法继续接受 |
| Callable[[A,B],R] | (A,B) -> R | 第二批加入；固定参数签名，返回 None 表示无值；旧拼法继续接受 |
| for i in inlineRange(...) | inline for i in range(...) | 第二批加入；相同编译期完全展开语义，旧拼法继续接受 |
| 无统一显式入口 | inline if cond: ... elif cond2: ... else: ... | 第二批加入；按源序选择编译期分支，无匹配且无 else 时为空，旧类型/宏 if 不机械改写 |
| 无统一静态模式入口 | inline match subject: ⏎ case pattern if guard: ... | 第二批加入；guard 可选，主体和所需守卫在编译期求值，首次命中后停止；无命中为空 |
| 旧类型 if 的精确类型链 | type match T: ⏎ case list[int]: ... ⏎ case str: ... | 第二批推荐；裸名称为类型引用；源序与无匹配规则须逐例核对，不机械迁移旧形状/捕获分派 |

首个可交付版本开放 enum（含 type enum）、final、const；type union 随 union 等第二批声明加入，property 块、箭头 lambda、Callable 类型简写、inline for/inline if/inline match、推荐的 type match 及可空语法族也放入第二批，以完成访问器、callable 类型传播、展开与静态分支、可空流分析、运行时支持及兼容桥。dataclass、serializable、native_name、自定义 annotation 等先保留属性写法。data class 可以是后续派生语法糖，但不能成为与 annotation/mixin 互斥的新类种类。MRO 派生采用 type enum/type union 前缀，复用已有 type 软关键字；迁移期仍接受原 @enum.mro/@union.mro + class 写法。

这些词在特定语法位置具有关键字作用，Lexer 仍可把它们输出为 NAME。解析器在语句起始处看到 `final class`、`final def`、`final NAME :` 或 `enum NAME` 时进入对应规则；普通 `enum = value`、`obj.final`、`enum(...)` 和旧的 `from py2cpp import enum` 保持名称语义。识别出明确声明前缀后提交到该规则，不能在声明写错时回退成普通表达式并吞掉错误。`@final` 与 `final class` 同时出现、重复 modifier 和非法组合应定位到相应 token 报错。

inline 同样按语句上下文识别，在 inline for/inline if/inline match 中激活循环展开或编译期分支规则；普通 inline 名称、成员和调用保留。循环头要求 `inline for NAME in range(...)`，range 在这个结构中表示固定的范围 intrinsic，不泛化为任意用户函数/iterable。保持 1–3 个位置参数、编译期边界、正负非零步长及简单目标；for-else 和整个循环体子树中的 break/continue 仍按原规则拒绝。循环边界运算沿用当前一元负号与 +、-、*、// 子集，不借新拼法扩展 constexpr 能力。

inline if 的 inline 作用于整条链，后续使用普通 elif/else；允许多链和嵌套，无匹配且无 else 生成空序列。条件必须得到编译期 bool，不隐式调用 __bool__；由受限静态求值器处理常量/宿主常量/索引/NTTP、整数算术比较、布尔短路及 TypeId 精确比较，未绑定依赖延迟到实例化。实际运行时依赖或未支持的静态求值须报错，不回退为普通 if。全部分支先通过语法及必要结构检查，未选体不常规绑定/展开/类型检查，选中体在原作用域和运行时位置插入。

inline match 的 inline 作用于全部 case，内部仍为 `case pattern [if guard]:`；主体编译期求值一次，模式成功后才以 case 捕获环境求严格 bool guard。guard 假继续下一 case，首个成功体选定后停止，无命中生成空序列。当前所需主体、模式或 guard 为 Dependent 时延迟选择，不能绕过它选择后续默认分支。允许嵌套并与 inline if/inline for 组合，不增加 inline case、match-else 或 match 表达式。

inline match 的静态主体首版限定 None/bool/目标整数/str/enum/TypeId，以及独立可求的常量、宿主值、索引和整数 NTTP。模式支持字面量、枚举成员、_、capture、as、OR 及 guard；整数按主体类型检查范围，bool/int/str 分开，单字符字符串不变成整数码，enum 保留 TypeId，OR 不作为 Flag 位运算。该入口中裸 `case int:` 仍是捕获，此前 `case U if U is int:` 的类型元值判断保留；直接类型 case 推荐独立 type match。共享求值器补充同类别标量 ==/!= 和 is None/is not None，供 inline if 与 guard 同时使用；TypeId 继续精确 is/is not，不调用用户比较方法。序列、映射、new/union 载荷、annotation 及 Optional/Nullable 包装等结构化静态值需另外建模后开放，不能执行运行时 getter/构造函数代替。

捕获保存完整主体与目标类型，仅在该 case 的 guard/正文可见，是不可变编译期局部符号；不泄漏、不修改外层同名变量，也不产生 case 后的运行时变量。所选正文的其他声明仍插入原作用域。OR 各备选捕获名集合与对应类型必须一致，首个匹配备选确定后 guard 只求一次，guard 假不重试同一 OR。捕获通过 SymbolId 绑定并物化为有类型的常量，保留嵌套参数遮蔽；类型捕获只用于类型/静态上下文，lambda 内的值捕获按常量处理。赋值、增量赋值或可写引用捕获须诊断。

推荐的 type match 首版支持精确 TypeExpr、顶层 OR、_、严格编译期 bool guard：`case str` 和 `case list[int]` 比较类型身份，不作继承、协议满足或转换判断；`case list[U]` 引用已有 U，未知名报错，未绑定形参延迟，不创建隐式捕获。主体须为类型形参、别名或合法构造类型，运行时对象不自动转成 type(obj)。_ 是无绑定通配；首个模式/guard 成功后停止，无匹配为空，复用 inline if/match 的剪枝、声明视图和外层结构规则。无需再叠加 inline，暂不开放 inline type match/type inline match。匿名 list[...] 形状与显式具名解构列为后续工作，旧类型 if 捕获继续兼容。

type match 模式按规范化 TypeId 比较并展开透明别名；泛型实参、数组维度、引用和 Callable 签名参与类型相等。值类型的 int/int? 不同，引用模型的 Node/Node? 仅注解不同，不能据此分派；不查询对象空状态。case 顶层 | 是 OR，内部类型语法继续原优先级，可空类型建议使用 ?，不将顶层 int | None 整体视为可空类型。case 类型在顶层 if 或冒号终止，guard 进入独立表达式规则；详细比较与迁移边界见语法对照表。

对于 type 前缀，看到 `type enum NAME` / `type union NAME` 才提交到 MRO 派生声明规则，`type match T:` 进入独立的类型模式语句；`type Name = T`、`type enum = T`、`type union = T`、`type match = T` 仍走类型别名。前瞻别名头的 =/泛型形参或匹配主体后的冒号即可分派，不查询符号表；`type(...)` 仍走表达式解析，不据此新增运行时内建。派生声明上的其他属性继续保留；原 @enum.mro/@union.mro 与对应 type 前缀同写应报告重复声明。

property 是类成员声明上下文中的软关键字，识别 `property NAME:`；静态对应形式建议为 `static property NAME:`。块内允许 docstring 和 __get__/__set__/__post_set__ 访问器，各至多一个；它们绑定到属性局部作用域，不产生普通嵌套函数，也不会覆盖宿主 descriptor 的同名方法。property 作为普通变量/成员名和旧装饰器的用途仍按原规则解析；同名新块与旧属性声明混用应报错。

属性读取调用 __get__，属性写入调用 __set__，setter 正常返回后再调用一次可选的 __post_set__；仅 getter 为只读，仅 setter 为只写，单独 hook 无 setter 要求补全声明。setter 负责实际存储，不隐式猜测或额外写入 _x；接收者和 RHS 各求值一次，setter 提前正常 return 仍应进入 hook，抛错则不进入，hook 抛错不自动回滚。hook 接收该次赋值参数，按既有类型/所有权规则处理，不重读 getter。完整示例、旧字段简写及静态形式见语法迁移对照表。

属性值类型先作为共同约束求解：已知 backing field、getter 返回注解/表达式、setter/hook 参数注解共同确定 T，再向未注解的 value 传播；不能把省略注解的访问器参数当作普通隐式泛型。set/post_set 默认返回 None。无法确定或冲突必须报错，不能沿用旧 getter 推断失败回落 void 的行为；引用返回与存储模型限定仍独立记录。

可空类型先按声明处类型类别绑定：具体非可空值类型 T? 形成 NullableValue(T)，引用类型 T? 只增加注解且存储与 T 相同；泛型未约束 T? 遵循 C# 注解规则，不能到实例化时一律套 Optional。新方言默认开启可空分析，引用诊断为可配置警告；NullableValue 到 T 不隐式转换。后缀 ! 只改该表达式的流状态，`n: int?` 后 `x: int = n!` 仍须报类型错误。

条件访问保存整个链及括号边界，接收者只求值一次，空分支跳过成员、索引和实参；非空分支的既有异常传播。??/??= 只检查空值，不能使用 and/or 真值逻辑。C# 14 条件写入在空接收者上连 RHS 和 property 的 setter/hook 都不执行；普通/复合属性写入以及 ??= 共享单次求值计划。引用 T/T? 或 expr! 之后的正常空解引用要有运行时异常路径，不能把 C++ 未定义行为作为 C# 兼容结果。

箭头 lambda 首版支持普通名称参数与单表达式体：() 必须保留，单参数可省括号，多参数须括起；不增加默认值、参数注解/解构/参数包或缩进函数体。=> 与旧 lambda 同处最低表达式层，右结合，函数体包含条件表达式及 ??，但不吞掉外围逗号。`x => a?.x ?? 0` 的所有计算在调用体内；`fallback ?? (x => x)` 用括号明确高优先级操作数中的 lambda。两种写法共用类型与捕获规则，不能因新 parser 接受嵌套或立即调用就假定后端已有完整闭包支持。

Callable 类型写作 `() -> R`、`(T) -> R`、`(A,B) -> R`，参数表括号始终保留，允许非空表尾逗号；无值返回写 None。例如 `f: (int, float) -> str = (a,b) => f"{a}:{b}"`，类型签名同时为 lambda 提供上下文。-> 只用于类型规则及已有 def 返回注解，不作为值表达式运算；与 => 独立分词。类型箭头右结合，`(A) -> (B) -> C` 返回 Callable，`((A) -> B) -> C` 接收 Callable；`(A) -> B?` 与 `((A) -> B)?` 分别修饰返回值和整个 callable。签名仍对应现有按值 PyCallable，不改变 Function、多播 delegate 或捕获生命期。

普通枚举首项仍须显式值，后续 `...` 取前项加一；flag 可以从 `...` 开始；父枚举合并和 flag 继承规则保持现状。枚举值计算、类型检查、重复成员与继承解析属于语义阶段。普通 enum 的语法体应明确允许 docstring/成员声明，拒绝其他语句。当前 `enum_expand.py:68` 会跳过部分非成员语句，之后清空类体；这应作为独立缺陷修复并记录兼容影响，不能被当作新规范。

type enum/type union 的声明体沿用原 MRO 派生规则，包括自动收集、手动附加成员/变体及既有空体形式。根声明中的 `base=Animal`/`base=Exception` 表示派生根类型，不是普通枚举底层类型或实体继承。type enum 子声明可单继承另一 type enum，此时继承根类型且禁止再次写 base=；type union 保持当前 base= 要求，不新增同类继承能力。TypeEnum/TypeUnion 命名后缀与 of/create 等现有接口保持。

final 必须保留三个不同的语义域。尤其当前字段初始化仅提取构造函数顶层赋值（`src/passes/final_expand.py:54`），不是完整控制流上的确定赋值分析。首版保留现有限制；将“分支中的 final 初始化”“局部 final 变量”“初始化表达式的副作用/执行顺序”分别作为以后有专门测试的语义工作。

解析器选型建议如下。

| 路线 | 价值 | 成本及适用范围 |
|---|---|---|
| 直接 fork CPython C parser | Python 语法与诊断覆盖最好 | grammar 的动作、tokenizer、AST、arena、异常和 Unicode 深度依赖 CPython；可做宿主参考，移植工作大 |
| Python pegen | grammar 扩展验证快 | 独立包不等于可独立运行的 C parser；仍需 tokenizer、AST、运行时迁移，并核对 PEP 696 覆盖 |
| 自有 Lexer + 递归下降 + Pratt | 易写入当前可编译子集，便于优先闭合自举 | 要自行覆盖模式、赋值目标、推导式、f-string 等；需要强语料差分测试；建议主线 |
| 自有 PEG 生成器输出 Py2Cpp 子集 | grammar 可直接维护，长期可扩展 | 增加生成器和运行时的自举范围；须处理左递归、回溯、cut、memo 和诊断动作 |

主线选择手写解析器，CPython grammar 用作参考规格，Py2Cpp 语言文档和测试定义实际支持范围。不要同时维护手写 parser 与另一套完整 PEG parser。如果以后确实需要持续同步接近完整 CPython grammar，可以单独评估迁移到 PEG：生成器先运行于宿主 Python，产物必须从第一天就是可被 Py2Cpp 编译的代码，最终再迁移生成器。自举不要求先造一个 parser generator。

CPython 参考来源：固定 3.13 的具体 tag/commit，记录来源与许可证；参考 [Grammar/python.gram](https://github.com/python/cpython/blob/3.13/Grammar/python.gram)、[Parser/Python.asdl](https://github.com/python/cpython/blob/3.13/Parser/Python.asdl)、[Parser/pegen.h](https://github.com/python/cpython/blob/3.13/Parser/pegen.h)、[Parser/lexer/lexer.c](https://github.com/python/cpython/blob/3.13/Parser/lexer/lexer.c)。3.13 grammar 含 `_PyAST_*`、`_PyPegen_*`、异常与 arena 操作，不能只删除语义动作就得到独立解析器。独立 [pegen 项目](https://github.com/we-like-parsers/pegen/blob/3b9f936a30d6c929d2538437cdc0465fa521b8f3/README.md) 也明确区分其 Python 输出与 CPython 私有 C 输出依赖。

Lexer 和 parser 的具体边界建议如下。

1. SourceManager 负责 UTF-8 源文件、文件身份、行索引、BOM/换行策略；Span 统一用 `(FileId, start_byte, end_byte)` 半开区间。Token 保存种类、原始范围和必要的字面量信息，注释与空白保留为 trivia，供重构和格式化使用。
2. Lexer 维护缩进栈、括号深度、显式续行和字符串/f-string 模式栈。实现 INDENT/DEDENT/NEWLINE、空白行、混合 Tab、CRLF、数字前缀/下划线、字符串前缀/拼接及 Unicode 标识符规则；采用固定版本 Unicode 分类/规范化表或明确公布的受限规则，不偷偷依赖 Python unicodedata。区分 ?.、?[、??、??=、!= 与单独 ?/!，f-string 转换分隔中的 ! 按模式处理；相邻 => 形成 ARROW token，与 =、==、>=、-> 独立。
3. 递归下降处理模块、声明、语句、参数、类型形参、类型表达式和模式。inline for 进入带 InlineRange 模式的 ForStmt，inline if 及其 elif/else 链进入 InlineIfStmt；保存与 else 内嵌套 if 的区别。inline match 进入 InlineMatchStmt，保留有序 case、原始 Pattern 和 guard；type match 进入 TypeMatchStmt，主体及 case 中的类型进入 TypeExpr/TypePattern，不生成隐式 CapturePattern。parser 不提前求值或删除任何分支。Pratt 处理表达式主体；比较链、is not/not in、条件表达式、lambda/箭头 lambda、推导式以及赋值目标另设明确规则。条件访问/后缀 ! 在成员访问层；?? 低于 or、高于条件表达式且右结合，??= 在赋值层。两种 lambda 同处最低表达式层并右结合；前瞻 NAME => 或括号参数头后 =>，与普通分组/元组消歧，函数体不吞外围逗号。保存括号对条件链的截断。以 `-2**2`、`2**-1`、`a?.b.c`、`(a?.b).c`、`a ?? b ?? c`、`x => a ?? b`、`x => y => x+y`、`f(x => x, y)` 等检验优先级和结合性。
4. 类型解析保存语法结构。配对括号后接 -> 时生成 CallableTypeSyntax，否则保留原分组/元组类型；返回侧递归解析并右结合，-> 比 ?/类型应用/返回侧 @ 标记绑定更弱。`def make() -> (int) -> str:` 中两个箭头分别由声明 parser 和类型 parser 消费。注解、别名和显式泛型应用的类型实参统一使用类型规则，外围名称仍由绑定检查。`T: SomeName` 是协议约束还是 NTTP，`Name[...]` 指代类型还是其他符号，由后续绑定决定。保留类型条件、oneof、切片数组、引用和现有开放字段注解；不能让通用表达式优先级意外改变标记归属。
5. f-string 采用状态栈与表达式 parser 协作，覆盖嵌套 replacement field、格式说明、同引号嵌套、转义和 `{x=}` 的原始文本。首批可支持编译器实现所需子集，替换旧前端前必须补齐项目已支持范围。
6. Diagnostic 保存代码、主 Span、附加位置和简要说明。批量编译首错失败即可；IDE 模式再在换行、DEDENT、闭合符号处恢复，产出显式 Error 节点。损坏语法树不能进入正式 codegen。

CPython AST 的列偏移是 UTF-8 字节位置，tokenize 的列号是字符位置，需通过 SourceManager 转换。例如 `中文 = 1` 的数字位置分别为字节列 9 和字符列 5。原生节点、旧节点适配和 IDE/LSP 的列单位必须明确定义；LSP 的 UTF-16 位置也在协议边界转换。初期不必逐字复制 CPython 错误文案，但错误位置、阶段和可理解性要纳入验收。

统一前端的目标数据流：

```text
legacy .py/.pyi ─ CPython 3.13 ─ from_cpython ─┐
                                             ├─ SyntaxModule + SourceMap
native/legacy ─ 自有 Lexer + Parser ───────────┘
                                                    │
                           声明/属性规范化、名称绑定、受控展开
                                                    │
                              类型明确的 HIR + TypeNode
                                                    │
                                现有 C++11 发射能力
```

Syntax AST 表达“源码写了什么”，HIR 表达“它意味着什么”。类型 if、union 变体模式、new 的目标类型推断等在绑定/展开阶段成为明确语义节点。保留原始属性顺序、源位置和写法来源，以处理确实有顺序语义的用户 decorator；核心声明 modifier 的顺序则由语言规则明确规定。

建议通过小型 schema 定义节点及字段，由宿主脚本生成初版节点定义、遍历、clone、dump、序列化和校验代码。生成出的代码也必须属于 bootstrap 子集；自举构建可以直接使用已提交的生成源码，若要求从 schema 完整再生成，则在最后迁移 schema 生成工具。节点 schema 只描述结构，不执行任意 Python 动作。

```text
SyntaxModule(items)  // 声明和语句按统一源码顺序保存
EnumDecl(name, base_syntax?, options, members, derivation?, attributes, span)
UnionDecl(name, type_params, bases, variants, derivation?, attributes, span)
MroDerivation(root_type?, span)  // type 前缀；子 type enum 从父声明继承根类型
ClassDecl(name, type_params, bases, modifiers, members, attributes, span)
FunctionDecl(name, type_params, parameters, return_type?, modifiers, body, attributes, span)
LambdaExpr(parameters, expression_body, syntax_kind, span)  // legacy lambda / arrow
CallableTypeSyntax(parameter_types, return_type, span)
ForStmt(target, iterable, body, else_body, expansion, span)  // 普通 / InlineRange
InlineIfStmt(branches, else_body, span)
StaticIfBranch(condition, body, span)
InlineMatchStmt(subject, cases, span)
StaticMatchCase(pattern, guard?, body, span)
TypeMatchStmt(subject_type, cases, span)
TypeMatchCase(pattern, guard?, body, span)
ExactTypePattern(type_syntax, span) / AnyTypePattern(span) / TypeOrPattern(items, span)
FieldDecl(name, type_syntax, storage, mutability, initializer?, attributes, span)
PropertyDecl(name, is_static, accessors, attributes, span)
AccessorDecl(kind, parameters, return_type?, body, attributes, span)  // get / set / post_set
NullableTypeSyntax(inner, span)
ConditionalAccessChain(receiver, steps, span)  // 步骤记录条件/普通访问，保留链边界
ParenthesizedExpr(inner, span)
NullSuppressExpr(operand, span)
CoalesceExpr(left, right, span)
CoalesceAssignExpr(target, value, span)
TypeExpr / Expr / Stmt / Pattern

NodeId -> NodeStore
SymbolId -> SymbolTable
TypeId -> TypeStore
NodeId -> SemanticInfo / ExpansionOrigin
TypeId -> NullableValueType / NullabilityAnnotation  // 可空值与引用注解分离
ExprId + FlowPoint -> NullState                     // 不挂到共享类型上
```

NodeId 在一次编译内稳定，不能直接当作跨版本缓存身份。首版用整数 ID 与按节点种类存储的 list，子节点也用 ID，避免递归值类型、AST 环和容器扩容造成的引用失效。所有权归 Module/Compilation；禁止动态 setattr 挂载编译状态。新建节点保留 origin，克隆操作显式处理来源及语义信息失效。`py2cpp/util/arena.py` 目前是 char 临时缓冲池，不能直接作为已有 AST arena 使用。

迁移期允许一个显式、单向的 `legacy_lowering`：自有 Syntax AST 投影成现有 passes 可消费的 CPython AST 和元数据，必要时合成旧标记。这使 enum/final 新语法可以先复用旧后端。新 parser 直接产出专有节点；旧节点仅存在于兼容边界，不能反向同步回原始树。语义模块迁移完成后删除该桥，原生编译器路径不得装载 CPython 对象。

P2 的执行桥明确采用子进程协议：原生 parser 输出带 schema 版本的 Syntax AST/Span 序列化数据，宿主读取并构造旧 AST；初版可用 JSON，不额外引入 Python 扩展 ABI。桥必须在 `ClassInfo` 构建之前执行（当前 `src/translator.py:729`）：enum 投影为 ClassDef + @enum，flag 放装饰器选项，底层/父枚举放 bases；final/const 字段投影为 AnnAssign + MatMult 标记，再统一建立旧元数据。合成标记的位置映射到原始 keyword span，不伪造源码行；诊断与导航通过 SourceMap 读取原始源码。此时 Python 宿主仍参与后续编译，只有 parser 已能独立运行。

type enum 的兼容投影为 `ClassDef + @enum.mro`，type union 后续为 `ClassDef + @union.mro`；均不叠加普通 @enum/@union。派生根放 ClassDef 的 base= keyword，子 type enum 的父枚举放 bases，声明体和开放属性按原顺序保留。CPython adapter 也须把旧 mro 写法规范化到同一种 MroDerivation，保证新旧入口的派生语义一致。

属性兼容桥先把旧字段属性、postsetter 简写和新 property 块规范化为明确的存储绑定与 get/set/post_set，再投影。新块无 hook 时可直接生成同名旧 getter/setter；有 hook 时生成普通 getter、setter 包装和按属性唯一命名的内部 setter-body/hook 方法，由包装依序调用，覆盖提前 return 的正常退出。绝不能把三种访问器机械映射成同时存在的 @property/@property.setter/@property.postsetter：ClassInfo 当前拒绝该组合，旧 emitter 还会自动赋值而忽略显式 setter。生成辅助方法受内部名称与来源管理，不成为公开反射成员。

旧 postsetter 入口在规范化时补出原隐含存储、getter 和赋值 setter，原回调放入 post_set；保持字段默认值、元数据、dataclass 构造参与及反射映射，不改成普通手写 _x 后丢失这些信息。self.__value__/Self.__value__ 作为旧存储兼容引用保留。S0502 等风格规则应基于源属性节点判断，对已归一化的新块不再建议退回旧 postsetter；不能用全局关闭 strict 来通过兼容桥。类型/访问权限/所有权检查仍作用于生成语义。

可空语法的桥接还需先完成绑定/流分析及求值计划，再生成旧 AST 能表达的临时变量和分支，或扩展后端接收中立 IR。T? 不能在 parser 阶段统一变成旧 T|None；当前 refcount 分支会擦掉可空性，boxing 分支又可能形成 Optional<Pointer>。新 NullableValue 的强制转换、运算提升和引用空异常应有明确运行时入口；原 Optional→T 自动 value__get 不能被新语法意外继承。NullSuppressExpr 在诊断后仅投影其操作数，同时保留来源，绝不以 value__get 或非空断言代替。旧 Optional ADT 保留，通过显式边界适配其存储、模式及成员。

箭头形式和旧 lambda 都规范化为 LambdaExpr；当前受支持的简单形状可投影到 ast.Lambda，普通参数放 ast.arguments.args，显式拒绝旧验证漏查的 posonlyargs 等形式，保留源头和函数体位置。若函数体需可空分支/临时变量，应在该 lambda 内部 lowering，必要时用中立函数体 IR，禁止把计算提升到 callable 创建点。旧后端没有通用 visit_Lambda；Callable/委托/key 等专用路径的类型传播、参数和返回检查必须分别接通，不能只构造 AST 就宣布所有表达式位置可用。

当前 lambda 的无目标形参/推断返回槽存在 int 回退，首次带 Callable 注解的变量声明也未向 lambda 发射器传入目标形参；这应在共同类型检查中修正，不冻结为新语法语义。函数作用域 lambda 实际引用捕获局部变量；PyCallable 只拥有 callable 对象，不延长这些引用或 self 的寿命。首期保持已有效支持的上下文并诊断未实现组合，完整逃逸闭包、直接返回 lambda、嵌套和立即调用作为明确的后续语义工作。

CallableTypeSyntax 的固定签名递归投影为旧 `Callable[[参数类型...], 返回类型]` AST，保留 None 返回和各类型/箭头的 SourceMap，合成的内建 Callable 标记避免用户同名符号遮蔽。旧 Callable 入口经绑定确认后与箭头类型生成相同 `TypeNode.template("Callable", "PyCallable", ret, *args)`，不转换成 TypeNode.function_ptr；最终原生前端直接绑定该类型。泛型形参来自外层作用域，箭头类型本身不声明泛型；类型别名不产生新的名义委托。可空、引用及元组层级不得在桥接中丢失，Callable 目标签名须传入 lambda 参数与返回检查。

现有 PyCallable 是按值槽位，有值的未绑定空槽与可空 Callable 的 None 不同。前者 bool 为 False，旧调用按返回类型返回默认值或空操作；后者由 NullableValue 表达，?? 只检查外层有无值，! 不解包。引用返回签名还需处理空槽 `Ret()` 对引用不成立的问题；不能把新写法的可解析性等同于所有签名的运行时可用性。

inline for 与旧 inlineRange 循环都规范化为 ForStmt 的 InlineRange 模式，绑定后形成 RangeBounds。兼容桥恢复 `ast.For(iter=Call(Name("inlineRange"), 原实参), ...)`，复用原展开器；不能只去掉 inline 而发射普通 range。原展开按范围顺序复制 body、替换索引读取并折叠已有静态 if，运行时副作用顺序保持。mixin 路径仍在宿主绑定及 iterFields/fixed-vararg 展开后处理，普通方法保留 ClassInfo 上下文，不扩大模块函数支持。现有索引替换不建立新作用域、不保留末次索引赋值，同名嵌套/遮蔽和索引再赋值的绑定缺口单列，不能在拼法迁移中悄悄改变。SourceMap 记录原循环头、循环体及克隆迭代来源。

inline if/match 共用带目标类型的 CompileTimeValue，静态求值返回 KnownValue/Dependent/Error；InlineIfStmt 的 KnownBool 是 KnownValue 要求为 bool 的专用结果。已知条件按源序只展开首个命中的分支并投影为旧语句序列，必要时补 pass；Dependent 保留在自有树/中立 IR，等类型/值实参或宿主绑定后选择，不能直接变为普通 ast.If。两种静态分支的目标覆盖函数/方法语句、普通类成员和模块声明；先用不含条件分支成员的声明骨架/常量依赖图提供求值环境，再选择分支，最后建立完整的 ClassInfo、受控导入依赖、布局、dataclass/属性和反射集合。每个实例保存独立的有效声明视图。条件/主体/模式依赖它正在控制的声明或布局时报告循环，不先把未选声明注册进去求值。

TypeMatchStmt 的主体和精确模式直接经类型绑定获得规范化 TypeId，OR 与通配由独立 TypePattern 处理，guard 使用同一静态求值器；选择结果进入共同的分支投影、特化和声明视图流程，保留语法来源。当前需要的类型尚依赖泛型实参则保留 Dependent；未知类型名或值主体报 Error。不能用“未找到类型就捕获”补救，也不能投影成普通 ast.Match。优先复用 type_node.py 的结构化相等/模式基础并补齐别名、可空身份和稳定 TypeId，避免沿用旧 type_if 的 C++ 字符串匹配。后续 list[...] 等匿名形状也须按源码顺序选择，不能先把精确模式提升到前面。

InlineMatchStmt 先求主体，再用纯静态 matcher 处理所需 Pattern，返回 Matched(bindings)/NotMatched/Dependent/Error；成功时建立 case 局部捕获环境、求 guard，guard 假丢弃绑定，真则展开正文。不按枚举/union 类型重排 case；OR 的备选也按源序保留。已知选择降低为语句序列并物化捕获，空结果按 suite 要求补 pass，依赖选择保留到特化；不能回退为 ast.Match。CompileTimeValue 使用显式值域和 TypeId，不继承宿主 Python 的 True==1 或枚举退化成整数行为；求值/匹配缓存依赖目标类型、特化实参和宿主常量，SourceMap 记录 case/guard/捕获及实例来源。

全部 case 先做模式 profile、重复捕获、OR 捕获名集合及不可反驳模式位置等结构检查；无 guard 的不可反驳 case 必须最后，OR 内不可反驳备选也必须最后，case guard 不改变 OR 内部可达性。类型一致性在实际需要绑定模式时检查；未选正文不走旧 visitor 的常规语义遍历。S0803 末尾默认分支/穷尽性规则仅作用于普通 match，不能全局关闭 strict。当前 match_case.py:1462 将 wildcard 抽离并可能丢 guard，union_match.py:106 按变体分组，match_case.py:220 的 annotation matcher 按固定元数据优先级选择；都不能复用为新源序选择器。普通 match、union/Optional 穷尽性和字段 annotation 原有规则独立保留，不机械加 inline 迁移。

与 inline for 联动时先做已约定的结构预检，再按外层索引绑定、inline if/match 选择、所选体展开的顺序执行。旧 `inline_range.py:271` 先递归两个 if 分支再折叠，新节点不能沿用该顺序；未选体的成员/类型错误及无效展开应被隔离，而循环体原有 break/continue 全子树限制仍保留。静态比较/布尔求值及模式匹配需补齐独立实现，旧 static_reflect 的比较只支持 ==/!=，不得以 Python eval 或当前有限折叠器冒充完整功能。

旧 type if 具有具体类型优先及模式分派、无 else 时的未覆盖断言，不能机械恢复为该路径来实现新 inline if 的源序/no-op 规则；旧宏 if 会发射全部分支再由 C++ #ifdef 选择，首版新条件不接受 __macro__。需要符号类型/NTTP 的泛型分支时，在前端特化剪枝或生成经验证的 C++11 分派，不增加 C++17 if constexpr 依赖。hasattr 等静态反射只有在绑定接口提供可靠的已知结果后才能加入条件求值范围。

现有 passes 的拆分以真实依赖为准：保留 dataclass、enum/union、descriptor、mixin、generator/coroutine、decorator、protocol、final 和语义分析的现有先后关系。逐个把隐含前置条件变成输入/输出契约、PassContext 和显式数据；TypeNode 先去掉 Python Enum/dataclass 运行时，再减少 C++ 字符串反解析。首期不引入新的 SSA/LLVM 层，以当前 C++ 发射器能消费的类型化 IR 为目标。

统一 API 可先落成以下边界，之后替换其内部实现：

```text
parse_module(source_id, dialect) -> ParsedModule
parse_expression(source_slice, dialect) -> ExprId
parse_type(source_slice, dialect) -> TypeExprId
parse_pattern(source_slice, dialect) -> PatternId
```

所有 `ast.parse` 调用都要登记用途：模块发现、入口装载、stdlib/FFI stubs、模板参数、select/build 子表达式、mixin 替换、类型反解析、architect 校验。由共同 SourceManager 缓存不可变解析结果，缓存键包含源码摘要、dialect、parser/schema 版本。旧 passes 的可变工作树另行构造，避免导入发现和编译阶段互相污染。缓存依赖更新也要覆盖新前端目录。

第一阶段建议新增的模块职责如下，均为规划路径：

| 规划路径 | 职责 |
|---|---|
| `src/frontend/api.py` | 宿主统一解析入口、前端选择和缓存协调 |
| `src/frontend/cpython_adapter.py` | 固定 CPython AST 到自有语法模型的转换 |
| `src/frontend/legacy_lowering.py` | 自有语法模型到旧 AST/元数据的单向兼容桥 |
| `compiler/frontend/source.py`、`tokens.py`、`lexer.py` | 使用可编译子集实现源文本、Token 和词法状态机 |
| `compiler/frontend/syntax_nodes.py`、`parser.py`、`diagnostic.py` | 节点存储、语法解析、错误位置与输出协议 |
| `src/tests/test_frontend_*.py`、`test/frontend/` | 宿主差分测试、原生 parser 程序与正反语料 |

`src/frontend` 只承担宿主适配，不另写一套语法实现；新解析器代码置于可自举的 `compiler` 源码树。后续按模块把语义与发射能力迁入该树，宿主 `src` 保留为冻结参考，最终退出生产构建路径。节点协议/schema 只有一份定义，避免双模型漂移。

自举实现语言需要另行冻结一个小而足够的 bootstrap profile。编译器实现源码先保持旧编译器可接受的语法，显式类型、普通函数/类、enum/union、list/dict、稳定 ID 和显式循环优先；避免动态 getattr/setattr、裸 object/Any、任意 Python callable、dataclasses.replace、Python 异构变长 tuple、动态 import 和隐含闭包。少数代码写法也有真实差异：src 中大量 `x in (...)`，目标语言当前却拒绝该形式；Options(**dict) 也不等同于目标的结构化 kwargs。应逐模块改写或为确实必要的特性独立实现支持。

现有库提供可用基础：`py2cpp/serde/pyml.py` 已有语言内 Value 联合、解析及求值逻辑，`py2cpp/io/path.py` 有读写文本，`py2cpp/console/parse.py` 有参数解析，`py2cpp/console/popen.py` 可驱动外部编译器。它们需要编译器规模的容量、生命周期、错误路径与性能验证，不能仅因 API 存在就假定足够。

模板执行器是必须明确处理的一条依赖。`docs/codegen-templates.md:42` 承诺“任意合法 CPython 表达式或语句”；若继续保留这个完整承诺，原生工具仍要携带 CPython 或等价解释能力。建议把承诺收敛为版本化的编译期模板子集，并迁移已有用法。早期可以预生成模板作为 seed 输入，但从模板源码全量重建的验收必须使用原生执行器。

本次静态扫描生产模板 61 个文件（排除 ~macro、单列 ~test，去 IGNORE 与注释）：167 个 ECHO 和 3 个 EVAL 的参数均为名称；23 个 BEGIN 包括 1 个局部 def、4 个名称序列 for、9 个 if 和 9 个 else；4 个 EXEC 都调用同一局部模板函数；另有 TYPE、INCLUDE、SCOPE 和 INJECT_CLASS。复杂计算主要在 Python helper 中，模板本身的可移植子集较小。

建议 StaticValue 支持明确的整数、浮点、bool、字符串、序列及必要记录；CppFragment、CppTypeName 与字符串值分开。TemplateFunctionId/固定 helper 表代替动态 callable，helper 移植为类型明确的普通编译器函数，语义查询通过专门的 context 结构传入。先覆盖名称替换、函数绑定、循环、条件和宏作用域，再覆盖现有测试中的算术、索引、赋值、range 与受控输出。超出 profile 的写法明确诊断，原生构建不能静默调用宿主 Python。

模板差分验收至少包含：

| 真实用例 | 迁移重点 |
|---|---|
| `templates/minimal.h:8` | 局部函数、参数绑定、名称序列循环及多次调用 |
| `templates/core/~protocol_erase_spec.inl` | `protocol_erase_gen.py` 生成的签名、vtable、复制/移动及泛型上下文 |
| `templates/core/~exception_group_dynamic_impl.inl` | 类型继承查询、确定性排序与动态匹配实现生成 |
| EVAL 循环体与独立展开 | 旧实现分别可能输出裸片段和字符串字面量，不能统一 str(value) 后假定等价 |
| `templates/~test/~syntax_showcase.inl` | 测试覆盖的表达式、局部赋值、range、条件链及运行时 C++ 分支回退 |

缓存首期可以关闭；完整编译稳定后以带版本的显式格式替换 pickle（`src/codegen/bootstrap_incremental.py:154`、`:171`）。原生 CLI、路径/进程 API 和构建驱动随后迁移。libclang 的 FFI 声明生成器、IDE 打包等开发工具可以暂留宿主；应声明哪些产物作为已提交源码输入，避免把辅助开发工具的 Python 依赖混入正常编译闭包。

建议按以下阶段实施，每阶段均有独立可验收结果。

| 阶段 | 工作与交付 | 通过条件 |
|---|---|---|
| P0：冻结基线 | grammar/profile、语料清单、AST/API schema、依赖清单、可重复输出开关 | 确认语言支持与语义差异；记录现有有效输出、负例诊断和性能；已有失败单列 |
| P1：统一前端入口 | SourceManager、parse API、CPython adapter、不可变模块解析缓存 | 模块发现/stubs/DSL 不再散落裸 ast.parse；旧程序结果等价 |
| P2：原生前端纵向样例 | bootstrap 子集写 Lexer/Parser/NodeStore；接 legacy_lowering；实现 enum（含 type enum）/final/const | 现有编译器能编译并运行新 parser；新旧写法规范化 AST 相等；旧后端行为相同 |
| P3：覆盖已有语法与第二批扩展 | 加入第二批声明、property 块、箭头 lambda/Callable 类型简写与共同类型检查、inline for 等价迁移和 inline if/inline match 静态选择、推荐的 type match 精确类型入口、可空语法及流分析/运行时支持；补齐泛型、模式、推导式、生成器/异步、f-string、FFI 语料 | 项目语料及负例预期覆盖；Python 交集与 CPython 差分、新旧 lambda/Callable 写法及循环展开等价、值/类型模式分离、静态分支源序/捕获/隔离与特化/声明剪枝、可空规则与 C# 参照用例对照；原生前端无 Python 回退 |
| P4：编译器内核迁移 | TypeNode、符号、analysis、passes、emit、模板 helper/evaluator 逐模块改写 | 编译器核心通过 bootstrap profile；宿主/原生结果对照；CPython AST 桥退出生产路径 |
| P5：完整原生构建 | 原生 CLI/module loader/driver，重建 runtime、模板和代表项目；版本化缓存可后补 | 无 Python 环境下正常完整编译；无宿主模板执行、隐藏解析回退或 pickle 依赖 |
| P6：自编译闭环 | 对固定编译器源码连续自编译，重跑全部回归 | C2/C3 生成结果及行为一致；保留 seed 与复现脚本 |

P3 内的 inline if/inline match 共用求值与剪枝框架，分两步交付：先实现当前环境已知值的函数/方法分支、静态标量模式及 inline for 联动，再实现待特化条件/模式和模块/类声明剪枝。后一步完成前，对未支持的位置或依赖明确诊断；不能把常量 True/False 的词法样例当作完整编译期分支支持。inline match 的序列、映射、union 等结构化静态值模型独立增量交付，解析语法可共用不表示静态求值已经可用。

推荐的 type match 同步接入上述选择/特化框架，先完成精确类型、OR、_ 和 guard，再扩展匿名形状及另行确定的具名解构捕获。list[int] 精确匹配读取类型结构，不要求 inline match 先能静态执行 list 对象的序列模式；二者能力分别验收。

自举流程可具体定义为：令 S 为可被 seed 接受的编译器源码，S 必须包含自己的 lexer/parser、语义分析、展开、模板执行与 C++ 发射实现。C0 是冻结版本的现有 Python 编译器；C1、C2、C3 是生成的原生编译器。

```text
C0(S) -> stage1/ 完整产物树 -> 固定 C++ toolchain -> C1
C1(S) -> stage2/ 完整产物树 -> 固定 C++ toolchain -> C2
C2(S) -> stage3/ 完整产物树 -> 固定 C++ toolchain -> C3

compare(stage2/manifest, stage3/manifest)
compare(C2 编译的回归程序行为, C3 编译的回归程序行为)
```

C1 能编译普通项目称为原生编译器；C1 能编译 S 才达到自编译。先用旧写法实现 S，C1 具备新语法后，再由 C1 编译转换为新关键字写法的 S'，并对同一个 S' 完成后续闭环，避免第一代 seed 读不了新语法的循环依赖。原生 parser 能解析自己的源码本身不是编译器自举。

首次 C0 → C1 在安装 CPython 的引导环境中执行；无 Python 的全量重建验收使用已经构建的 C1 或已发布 C2 作为原生 seed。该环境只保留原生 seed 可执行文件、声明的源码/生成源码、runtime 和模板输入，以及 C++ 工具链；让 Python 不可用并检查构建链仍成功。manifest 记录完整生成文件集合及内容摘要，包括 .cpp/.h/.inl、runtime 和模板展开结果，不能只比较入口 cpp。当前输出包含生成时间（`src/translator.py:525`），需固定或移除；同时规范化源路径、排序、换行和工具配置。比较前只排除约定的非语义元数据，不能宽泛清洗差异掩盖 bug；确定可复现构建后再要求二进制字节一致。

验收需要三种互补的差分：普通 Python 语法交集比较 CPython adapter 与原生 parser 的规范化 AST；旧装饰器/新关键字等价用例比较同一 HIR；最终比较生成 C++、运行行为与负例错误阶段。名称 ID 和临时节点编号不直接全等比较，来源位置单独校验。加入异常缩进、嵌套 f-string、泛型默认值、非法 modifier、enum 成员、final 初始化和中文位置用例，并以有界随机生成/变异语料检测崩溃和非终止。

property 块另外验收：多个属性的同名访问器互不冲突，省略注解的共同类型推断，只读/只写诊断，setter 提前 return/抛错与 hook 抛错，接收者/RHS 单次求值，assign/new 属性写入，以及旧字段默认值、postsetter 回调顺序、静态存储、dataclass 和反射结果等价。旧互斥规则与 S0502 的迁移必须纳入验证，避免新 parser 可读但旧语义层拒绝用户新写法。

可空语法另测：值/引用/泛型 T? 分类、! 不做运行时检查或值解包、空状态合流、?. 链和括号、索引/实参惰性求值、0/False 不触发 ??、??= 属性读写次数、条件写入 hook 次数、可空值运算真值表、运行时空异常，以及旧 Optional 跨方言转换。后端有实现前只声明为待实现能力，不以 CPython 不能解析的语法样例通过文档检查作为功能完成依据。

箭头 lambda 另测：三种基本写法与旧 lambda 的 AST/HIR/行为等价，参数括号与元组消歧、非法参数/缺失函数体诊断、逗号边界与右结合，Callable/委托/key 的目标参数及返回检查，有效捕获的生命周期，以及可空函数体中副作用只在调用时发生。立即调用/直接返回/嵌套等形状的解析验收与语义支持分开；没有完成对应 lowering 前保持明确诊断。

Callable 类型另测：新旧签名类型及 ABI 等价、零/单/多参数、None 返回、元组参数/返回、高阶类型右结合、别名/泛型/容器、def 返回 Callable 的双箭头、lambda 目标签名传播、非法头/缺失返回类型及错误类型上下文；分别验证可空返回值、可空 callable、引用限定，以及有值空槽不会触发 ?? 的语义。

inline for 另测：三种 range 参数数量、正负步长/空范围/零步长、宿主常量、不同索引名的嵌套依赖、if 折叠和运行时副作用顺序；比较旧 inlineRange 的展开 AST/HIR 与生成行为，确认无对应运行时循环。保留动态边界、非法常量运算、for-else、非简单目标及 break/continue 的拒绝行为，并验证 inline 名称兼容及原始位置映射。

inline if 另测：源序首个命中、后续 elif 不求值、无 else 的空序列、严格 bool 与短路、嵌套/多链、宿主/索引/TypeId/NTTP 绑定、未选分支语义隔离但语法/结构检查保留、模块导入与类布局/成员不受未选声明污染、实例隔离和依赖循环。确认分支体副作用仍在运行时且无对应运行时 if；旧 type if 和宏 if 独立回归。

inline match 另测：主体单次静态求值、None/bool/int/str/enum 分类与整数范围、类型主体及 TypeId 守卫、源序选择、带 guard 的通配、模式失败不求 guard、guard 假继续、OR 只求一次 guard、Dependent 不越过、无命中为空。覆盖捕获只读/不泄漏/遮蔽/有类型常量物化、未选体隔离及结构错误、inline for 的跳转预检、声明剪枝/实例隔离/循环依赖；最终不产生对应运行时分派，正文副作用留在原位置。旧普通、union/Optional 和 annotation match 单独回归，不将已有 wildcard guard 或字符码匹配行为误用为新规则。

type match 另测：list[int]/str 精确匹配、别名/名义身份/泛型实参、引用可空注解不改变身份、值可空区别、数组/Callable/引用限定、未知类型名报错且不捕获、运行时值主体拒绝、外层类型参数与 Dependent、OR/guard/源序/no-op/返回检查，以及 type match 类型别名消歧和错误位置。共享静态分支的未选体隔离、声明视图和实例检查；后续形状模式补 list[...] 在 list[int] 前的源序例，旧 type_if 的精确优先结果不作为新语义预期。

P0 还应处理已发现的规范漂移：手册将宿主最低版本写成 3.10，而 PEP 695 需要 3.12、泛型默认值需要 3.13；optional 字段是否参与 assign 的描述与实现不一致；dataclass 的 kwOnly/kw_only、frozen 和手写 init/post_init 说明有过时部分；union 模式现有测试使用 `case new.Variant(...)`，手册仍有 `case Msg.Variant(...)`。这些问题先形成决策与回归，不把某次实现的偶然行为直接冻结成永久语言规则。

文件兼容与工具链也需要进入交付范围。建议新关键字文件使用独立扩展名 `.py2`（扩展名为提案），旧 `.py` 与 `.pyi` 保持兼容入口；import resolver 同时认识两者，同名模块同时存在时明确报错，避免悄悄改变解析优先级。首个原型可用显式 dialect 参数接入测试，正式开放前同步文件发现、构建脚本、FFI 桩扫描、nav/architect、语法高亮、格式化与错误跳转。迁移工具用 token span 修改，保留注释；Python 的 ast.unparse 无法直接输出新语法。软关键字只解决名称兼容，新语法文件仍需要相应 IDE 支持。

建议第一批实现范围固定为 P0/P1 加 P2 的纵向样例：统一全部解析入口，定义 SourceSpan 和 enum（含 type enum）/final/const 的节点及规范化规则，用现有编译器编译一个可以读取这些声明的原生前端，再通过兼容桥驱动现有后端。此阶段同时证明语法、语义等价、源码位置和 bootstrap 数据模型可行，然后扩大覆盖与迁移本体。无需先一次重写 8 万行，也无需先更换成熟的 C++11 后端。
