**Py2Cpp 自有前端与自举编译器实现方案**

设计提案，2026-09-08。本文描述建议实施的工作；新语法、解析器和自举流程尚未实现。

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
| 类与方法规则 | @final、@staticmethod、@virtual、@abstract、@override | ClassModifiers、MethodModifiers；协议静态要求与实体虚方法分别建模 |
| 字段存储/可变性 | T @const、T @final、T @thread_local | FieldStorage、FieldMutability、Initializer；const 是类 static constexpr，final 是实例只读 |
| 类型/参数规则 | T @ref、T @lazy、T @optional | 引用类型、惰性求值参数、字段参与自动构造的选项，分别归属；optional 字段标记与 Optional[T] 类型不同 |
| 泛型及类型语法 | PEP 695/696、type 别名、T: Protocol、A & B、oneof[...]、NTTP、可变类型参数、T[:N]、T[:, :]、T \| None | TypeExpr、TypeParam、Constraint、ArrayType；需要名称解析才能决定的类别先保留未解析表示 |
| 对象模型 | @refcount、@boxing、@copyable、@uncopyable | ObjectModel、CopyPolicy；即使表面保留属性，也必须进入类型与存储语义 |
| 派生与开放属性 | @dataclass、@serializable、@annotation、用户 Meta(...)、@native_name | DeriveSpec、Attribute、ForeignBinding；允许不同维度组合 |
| 访问器和效果 | @property、setter/postsetter、@immutable、@noexcept | PropertyDecl、Accessor、MethodEffects；noexcept 现有 Result 改写不能简化成 C++ 关键字 |
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
| @final + class C | final class C | 禁止继承 |
| @final + def f | final def f | 方法隐含 virtual，禁止覆盖；首版限原来允许的成员方法位置 |
| x: T @final | final x: T | 实例只读字段及构造初始化规则；不同时新增局部 final 变量语义 |
| x: T @const = v | const x: T = v | 类级编译期常量；不改成普通实例 const |
| @union/@variant + class | union/variant 声明 | 保留带标签载荷的联合与变体字段 |
| @protocol/@mixin + class | protocol/mixin 声明 | 保留结构约束/编译期混入，分别实施 |
| @staticmethod/@virtual/@abstract/@override + def | static/virtual/abstract/override def | 第二批加入；先冻结组合矩阵 |

首个可交付版本只开放 enum、final、const；其余声明关键字按同一模型后续加入。dataclass、serializable、native_name、自定义 annotation 等先保留属性写法。data class 可以是后续派生语法糖，但不能成为与 annotation/mixin 互斥的新类种类。enum.mro/union.mro 属于编译期派生能力，继续支持已有入口，暂不增加 mro 关键字。

这些词在特定语法位置具有关键字作用，Lexer 仍可把它们输出为 NAME。解析器在语句起始处看到 `final class`、`final def`、`final NAME :` 或 `enum NAME` 时进入对应规则；普通 `enum = value`、`obj.final`、`enum(...)` 和旧的 `from py2cpp import enum` 保持名称语义。识别出明确声明前缀后提交到该规则，不能在声明写错时回退成普通表达式并吞掉错误。`@final` 与 `final class` 同时出现、重复 modifier 和非法组合应定位到相应 token 报错。

普通枚举首项仍须显式值，后续 `...` 取前项加一；flag 可以从 `...` 开始；父枚举合并和 flag 继承规则保持现状。枚举值计算、类型检查、重复成员与继承解析属于语义阶段。enum 的语法体应明确允许 docstring/成员声明，拒绝其他语句。当前 `enum_expand.py:68` 会跳过部分非成员语句，之后清空类体；这应作为独立缺陷修复并记录兼容影响，不能被当作新规范。

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
2. Lexer 维护缩进栈、括号深度、显式续行和字符串/f-string 模式栈。实现 INDENT/DEDENT/NEWLINE、空白行、混合 Tab、CRLF、数字前缀/下划线、字符串前缀/拼接及 Unicode 标识符规则；采用固定版本 Unicode 分类/规范化表或明确公布的受限规则，不偷偷依赖 Python unicodedata。
3. 递归下降处理模块、声明、语句、参数、类型形参、类型表达式和模式。Pratt 处理表达式主体；比较链、is not/not in、条件表达式、lambda、推导式以及赋值目标另设明确规则。以 `-2**2`、`2**-1` 等检验优先级和结合性。
4. 类型解析保存语法结构。`T: SomeName` 是协议约束还是 NTTP，`Name[...]` 指代类型还是其他符号，由后续绑定决定。保留类型条件、oneof、切片数组、引用和现有开放字段注解；不能让通用表达式优先级意外改变标记归属。
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
EnumDecl(name, base_syntax?, options, members, attributes, span)
ClassDecl(name, type_params, bases, modifiers, members, attributes, span)
FunctionDecl(name, type_params, parameters, return_type?, modifiers, body, attributes, span)
FieldDecl(name, type_syntax, storage, mutability, initializer?, attributes, span)
TypeExpr / Expr / Stmt / Pattern

NodeId -> NodeStore
SymbolId -> SymbolTable
TypeId -> TypeStore
NodeId -> SemanticInfo / ExpansionOrigin
```

NodeId 在一次编译内稳定，不能直接当作跨版本缓存身份。首版用整数 ID 与按节点种类存储的 list，子节点也用 ID，避免递归值类型、AST 环和容器扩容造成的引用失效。所有权归 Module/Compilation；禁止动态 setattr 挂载编译状态。新建节点保留 origin，克隆操作显式处理来源及语义信息失效。`py2cpp/util/arena.py` 目前是 char 临时缓冲池，不能直接作为已有 AST arena 使用。

迁移期允许一个显式、单向的 `legacy_lowering`：自有 Syntax AST 投影成现有 passes 可消费的 CPython AST 和元数据，必要时合成旧标记。这使 enum/final 新语法可以先复用旧后端。新 parser 直接产出专有节点；旧节点仅存在于兼容边界，不能反向同步回原始树。语义模块迁移完成后删除该桥，原生编译器路径不得装载 CPython 对象。

P2 的执行桥明确采用子进程协议：原生 parser 输出带 schema 版本的 Syntax AST/Span 序列化数据，宿主读取并构造旧 AST；初版可用 JSON，不额外引入 Python 扩展 ABI。桥必须在 `ClassInfo` 构建之前执行（当前 `src/translator.py:729`）：enum 投影为 ClassDef + @enum，flag 放装饰器选项，底层/父枚举放 bases；final/const 字段投影为 AnnAssign + MatMult 标记，再统一建立旧元数据。合成标记的位置映射到原始 keyword span，不伪造源码行；诊断与导航通过 SourceMap 读取原始源码。此时 Python 宿主仍参与后续编译，只有 parser 已能独立运行。

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
| P2：原生前端纵向样例 | bootstrap 子集写 Lexer/Parser/NodeStore；接 legacy_lowering；实现 enum/final/const | 现有编译器能编译并运行新 parser；新旧写法规范化 AST 相等；旧后端行为相同 |
| P3：覆盖已有语法 | 补齐泛型、模式、推导式、生成器/异步、f-string、FFI 等语料；完善位置与诊断 | 项目语料及负例预期覆盖；支持交集与 CPython 差分；原生前端无 Python 回退 |
| P4：编译器内核迁移 | TypeNode、符号、analysis、passes、emit、模板 helper/evaluator 逐模块改写 | 编译器核心通过 bootstrap profile；宿主/原生结果对照；CPython AST 桥退出生产路径 |
| P5：完整原生构建 | 原生 CLI/module loader/driver，重建 runtime、模板和代表项目；版本化缓存可后补 | 无 Python 环境下正常完整编译；无宿主模板执行、隐藏解析回退或 pickle 依赖 |
| P6：自编译闭环 | 对固定编译器源码连续自编译，重跑全部回归 | C2/C3 生成结果及行为一致；保留 seed 与复现脚本 |

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

P0 还应处理已发现的规范漂移：手册将宿主最低版本写成 3.10，而 PEP 695 需要 3.12、泛型默认值需要 3.13；optional 字段是否参与 assign 的描述与实现不一致；dataclass 的 kwOnly/kw_only、frozen 和手写 init/post_init 说明有过时部分；union 模式现有测试使用 `case new.Variant(...)`，手册仍有 `case Msg.Variant(...)`。这些问题先形成决策与回归，不把某次实现的偶然行为直接冻结成永久语言规则。

文件兼容与工具链也需要进入交付范围。建议新关键字文件使用独立扩展名 `.py2`（扩展名为提案），旧 `.py` 与 `.pyi` 保持兼容入口；import resolver 同时认识两者，同名模块同时存在时明确报错，避免悄悄改变解析优先级。首个原型可用显式 dialect 参数接入测试，正式开放前同步文件发现、构建脚本、FFI 桩扫描、nav/architect、语法高亮、格式化与错误跳转。迁移工具用 token span 修改，保留注释；Python 的 ast.unparse 无法直接输出新语法。软关键字只解决名称兼容，新语法文件仍需要相应 IDE 支持。

建议第一批实现范围固定为 P0/P1 加 P2 的纵向样例：统一全部解析入口，定义 SourceSpan 和 enum/final/const 的节点及规范化规则，用现有编译器编译一个可以读取这些声明的原生前端，再通过兼容桥驱动现有后端。此阶段同时证明语法、语义等价、源码位置和 bootstrap 数据模型可行，然后扩大覆盖与迁移本体。无需先一次重写 8 万行，也无需先更换成熟的 C++11 后端。
