# Py2Cpp 自有前端与自举编译器实现方案

初稿 2026-09-08，更新 2026-09-10。本文是尚未实现的编译器迁移方案，集中描述架构、兼容桥、工程阶段和验收。所有旧新写法、语义及兼容限制统一定义在 [syntax-migration.md](./syntax-migration.md)，本文引用相应章节，不另维护一份语言规范。

## 1. 目标与现有基础

建议固定 CPython 3.13 的词法与语法为参考基线，以当前 Py2Cpp 能编译的语言子集实现独立 Lexer、递归下降解析器及 Pratt 表达式解析器，建立自有 AST；将 enum、final 等提升为声明上下文中的软关键字。通过兼容适配层逐步复用现有 passes 和 C++11 后端，随后迁移编译器本体与模板执行器，完成 stage0 → stage1 → stage2 → stage3 自编译闭环。

保留 C++11 后端和外部 MSVC/Clang 不影响转译器自举。自举要求编译器实现语言能编译自身，生成后的编译器能独立运行；不要求同时实现机器码后端。

前期审计的事实基础如下，文件行号和统计均对应当时快照，用于估算迁移范围。

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

## 2. Parser 选型与词法边界

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
3. 递归下降处理声明、语句、参数和模式，Pratt 处理运算；比较链、lambda、推导式、赋值目标和 match arms 使用专门规则。值 Pattern、TypePattern 与普通 TypeExpr 分离，所有静态分支原样入树，不在 parser 中求值或剪枝。`record`、`frozen`、`ordered` 与既有 `ref`、`final`、`lazy` 仍由 lexer 作为 NAME 交给类头规则；该规则有限前瞻收集合法前缀，并以终结的 `class` 或 `record` 提交声明解析。`optional` 只在已确认的 record 实例字段位置识别。重复前缀、`ordered class`、`lazy record`、缺少 record 字段默认值等不能回退为普通表达式或普通成员；其他同名变量、成员和调用保持可用。优先级以 [语法规约](./syntax-migration.md#match-expression) 为唯一依据，保存括号截断条件链的边界。
4. 类型 parser 保存 Callable、可空和引用的完整层级；参数 lazy 写入 ParameterEvaluationMode，函数/属性 lazy 写入 CachePolicy，lazy class 写入 ClassConstructionPolicy，不能生成任意 LazyType。ref class 写入 ClassDecl 的 ObjectModel，与注解 ref T 分开。类型模式只在规定上下文解析 type NAME，条件类型保留 condition 与 true/false 类型的独立节点；未知名称、NTTP/协议归属和特化依赖交给绑定器处理，不靠名称拼写猜测。
5. f-string 采用状态栈与表达式 parser 协作，覆盖嵌套 replacement field、格式说明、同引号嵌套、转义和 `{x=}` 的原始文本。首批可支持编译器实现所需子集，替换旧前端前必须补齐项目已支持范围。
6. Diagnostic 保存代码、主 Span、附加位置和简要说明。批量编译首错失败即可；IDE 模式再在换行、DEDENT、闭合符号处恢复，产出显式 Error 节点。损坏语法树不能进入正式 codegen。

CPython AST 的列偏移是 UTF-8 字节位置，tokenize 的列号是字符位置，需通过 SourceManager 转换。例如 `中文 = 1` 的数字位置分别为字节列 9 和字符列 5。原生节点、旧节点适配和 IDE/LSP 的列单位必须明确定义；LSP 的 UTF-16 位置也在协议边界转换。初期不必逐字复制 CPython 错误文案，但错误位置、阶段和可理解性要纳入验收。


call/from 使用普通 Python suite，参数/返回类型及 invocation 的嵌套冒号不截断声明；所有调用括号闭合后才进入正文，见 [回调语句](./syntax-migration.md#call-from)。A–D 类通用块 lambda 仍是 [候选](./syntax-migration.md#multiline-lambda-options)。如果采用表达式中的缩进块，还须增加局部布局 frame：保存物理换行、块头前导缩进和进入时括号深度，在该深度恢复语句换行/缩进，正文新括号仍按隐式续行处理；DEDENT 后把闭括号/外围逗号交还表达式 parser。保存 suite 结束行边界，使独立赋值/return 正常终止；不依赖空行或扫描正文有无 return 判断块的种类。

## 3. 自有 AST、HIR 与存储

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

Syntax AST 表达“源码写了什么”，HIR 表达“它意味着什么”。类型 if、union 变体模式、new 的目标类型推断等在绑定/展开阶段成为明确语义节点。保留原始属性顺序、源位置和写法来源，以处理确实有顺序语义的用户 decorator；核心声明 modifier 的顺序则由语言规则明确规定。对象模型、类构造策略、CopyPolicy、引用限定、参数求值方式及声明缓存分别建模，不能收拢为一组无差别 flags。

建议通过小型 schema 定义节点及字段，由宿主脚本生成初版节点定义、遍历、clone、dump、序列化和校验代码。生成出的代码也必须属于 bootstrap 子集；自举构建可以直接使用已提交的生成源码，若要求从 schema 完整再生成，则在最后迁移 schema 生成工具。节点 schema 只描述结构，不执行任意 Python 动作。

```text
SyntaxModule(items)  // 声明和语句按统一源码顺序保存
EnumDecl(name, base_syntax?, options, members, derivation?, attributes, span)
UnionDecl(name, type_params, bases, variants, derivation?, attributes, span)
MroDerivation(root_type?, span)  // type 前缀；子 type enum 从父声明继承根类型
ClassDecl(name, type_params, bases, object_model, construction_policy, copy_policy, modifiers, record_policy?, members, attributes, span)
ObjectModel = Value / RefCount / Boxing
ClassConstructionPolicy = PerConstruction / LazySingleton
RecordPolicy = Record(ordered, span)
FunctionDecl(name, type_params, parameters, return_type?, modifiers, cache_policy?, body, attributes, span)
ParameterDecl(name, type_syntax, evaluation_mode, default?, attributes, span)
ParameterEvaluationMode = Eager / LazyMemoPerCall
ReferenceTypeSyntax(inner, span)
CachePolicy(kind, capacity?, span)  // PropertySlot / FunctionMemo；函数容量来自绑定后的 @LazyCache，缺省无界
LambdaExpr(parameters, expression_body, syntax_kind, span)  // legacy lambda / arrow
CallWithCallbackStmt(callback_decl, invocation, result_target?, span)
CallbackDecl(name, parameters, return_type?, body, span)
MatchExpr(subject, arms, span)  // 运行时值匹配，结果为表达式
MatchArm(pattern, guard?, result_expr, span)
CallableTypeSyntax(parameter_types, return_type, span)
ForStmt(target, iterable, body, else_body, expansion, span)  // 普通 / InlineRange
InlineIfStmt(branches, else_body, span)
StaticIfBranch(condition, body, span)
InlineMatchStmt(subject, cases, span)
StaticMatchCase(pattern, guard?, body, span)
TypeMatchStmt(subject_type, cases, span)
TypeMatchCase(pattern, guard?, body, span)
ExactTypePattern(type_syntax, span) / AnyTypePattern(span) / TypeOrPattern(items, span)
CaptureTypePattern(name, span)
AppliedTypePattern(head_type, argument_patterns, span)
TypePatternTest(subject_type, pattern, span)
ConditionalTypeSyntax(true_type, condition, false_type, span)
FieldDecl(name, type_syntax, storage, mutability, initializer?, record_constructor_mode, attributes, span)
RecordConstructorMode = Included / OptionalPostInit
PropertyDecl(name, is_static, accessors, cache_policy?, attributes, span)
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
SymbolId -> CapturedTypeUse(type_use, identity)      // 保留可空/引用限定的模式局部类型
NodeId -> SemanticInfo / ExpansionOrigin
DeclId -> CachePlan(owner, specialization, key_plan, result_plan, invalidation)
DeclId + TypeArguments -> SingletonPlan(constructor, storage_owner, accessor, lifetime)
DeclId -> RecordPlan(effective_fields, constructor_fields, optional_post_init_fields, generated_members, comparison_fields, serialization_fields, frozen_layout)
TypeId -> NullableValueType / NullabilityAnnotation  // 可空值与引用注解分离
ExprId + FlowPoint -> NullState                     // 不挂到共享类型上
```

NodeId 在一次编译内稳定，不能直接当作跨版本缓存身份。首版用整数 ID 与按节点种类存储的 list，子节点也用 ID，避免递归值类型、AST 环和容器扩容造成的引用失效。所有权归 Module/Compilation；禁止动态 setattr 挂载编译状态。新建节点保留 origin，克隆操作显式处理来源及语义信息失效。`py2cpp/util/arena.py` 目前是 char 临时缓冲池，不能直接作为已有 AST arena 使用。

## 4. 兼容桥与语义实现

迁移期允许一个显式、单向的 `legacy_lowering`：自有 Syntax AST 投影成现有 passes 可消费的 CPython AST 和元数据，必要时合成旧标记。这使 enum/final/ref class 等新语法可以先复用旧后端。新 parser 直接产出专有节点；旧节点仅存在于兼容边界，不能反向同步回原始树。语义模块迁移完成后删除该桥，原生编译器路径不得装载 CPython 对象。

P2 的执行桥明确采用子进程协议：原生 parser 输出带 schema 版本的 Syntax AST/Span 序列化数据，宿主读取并构造旧 AST；初版可用 JSON，不额外引入 Python 扩展 ABI。桥必须在 `ClassInfo` 构建之前执行（当前 `src/translator.py:729`）：enum 投影为 ClassDef + @enum，flag 放装饰器选项，底层/父枚举放 bases；final/const 字段投影为 AnnAssign + MatMult 标记，再统一建立旧元数据。合成标记的位置映射到原始 keyword span，不伪造源码行；诊断与导航通过 SourceMap 读取原始源码。此时 Python 宿主仍参与后续编译，只有 parser 已能独立运行。

### 4.1 声明与对象模型

[ref class](./syntax-migration.md#declarations) 的新旧入口归一为 ClassDecl.object_model=RefCount，再投影成 ClassDef + @refcount，复用既有构造、共享所有权、容器存储、WeakRef 与类型检查。重复新旧标记及对象模型冲突在投影前诊断，引用限定和原约束符号按规范分别绑定。

普通 enum 展开器目前会跳过部分非成员语句后清空类体，final 初始化仅提取构造函数顶层赋值。前者列为独立兼容缺陷，后者先保留现有限制；控制流确定赋值、局部 final 和初始化副作用顺序分别扩展。

type enum 的兼容投影为 `ClassDef + @enum.mro`，type union 后续为 `ClassDef + @union.mro`；均不叠加普通 @enum/@union。派生根放 ClassDef 的 base= keyword，子 type enum 的父枚举放 bases，声明体和开放属性按原顺序保留。CPython adapter 也须把旧 mro 写法规范化到同一种 MroDerivation，保证新旧入口的派生语义一致。

#### record、frozen、ordered 与 optional 的绑定

类头解析只保存 `RecordPolicy` 和各修饰词的原始 Span；绑定器在解析实体基类、mixin、条件声明视图和类成员后验证组合。`ordered` 要求 `RecordPolicy`，`lazy record` 与 `ordered class` 直接诊断，`ref record`、`final record` 合法；record 至多有一个实体 record 基类，带实例字段的普通实体基类不能充当该基类。`optional` 不是类型标记：它只在 record 实例字段上形成 `OptionalPostInit`，且必须带默认表达式；其他字段为 `Included`。`frozen` 可用于普通 class 和 record，仍与禁止继承的 `final` 分开建模。

完成成员选择、继承和 mixin 展开后，为每个 record 生成 `RecordPlan`。`effective_fields` 按实体 record 基类、展开的 mixin 和当前声明的源码顺序组成；`constructor_fields` 只含 Included 字段，`optional_post_init_fields` 排除在自动 `__init__` 形参外，但仍进入 `comparison_fields`、`serialization_fields`、反射和模式匹配。Plan 固定生成 `__init__`、`__eq__`、`__repr__`，缺少手写 `__str__` 时再生成转发到 `__repr__` 的 `__str__`；ordered record 生成 `__cmp__`。绑定阶段拒绝同名手写的固定生成成员（以及 ordered record 的 `__cmp__`），但允许 `__post_init__` 和手写 `__str__`。

RecordPlan 同时显式保存构造顺序：自动构造先初始化所有逻辑字段并调用 `__post_init__`；`new(..., optional_field=value)` 的剩余 optional 写入在其后执行，`assign()` 使用同一字段可写性规则。这样不能把 optional 降格为“不可比较的构造外元数据”。`@serializable` 按绑定到内建声明的身份附着到 Plan，手写 `serialize` 或 `deserialize` 时先报冲突；反序列化缺字段只可取声明默认值，否则报缺字段诊断。

`frozen_layout` 在 property/descriptor 的真实用户存储、实体基类字段、mixin 注入字段和当前字段均确定后计算，而不是只检查语法上出现的 FieldDecl。带实例字段的实体基类必须同为 frozen；可写 property、post-setter、descriptor setter 和 optional 字段均在此阶段拒绝。缓存、锁等编译器内部槽不写入 frozen_layout，也不进入记录的生成成员字段序列。

#### RecordPlan 的兼容投影

必须先完成绑定并生成 RecordPlan，随后才允许 `legacy_lowering` 合成旧 `@dataclass` 与字段 `@optional` 元数据，供尚未迁移的 pass 使用。这个投影不能是机械映射：旧路径没有完整 frozen 有效布局、record 的 `__str__` 回退、optional 参与排序/展示/序列化/反射，也不表达 `new` 在 `__post_init__` 后覆盖 optional 字段的顺序。兼容桥须显式生成这些行为，或把它们保留在中立 HIR；在两者均不可行的组合上报告尚未支持，不能静默改变新方言语义。`@serializable` 的冲突和缺字段规则同样必须在旧序列化 pass 前完成绑定，不能按装饰器名称文本猜测。

#### lazy class 的构造策略

[lazy class](./syntax-migration.md#lazy-class) 同时绑定 `ObjectModel.RefCount` 和 `ClassConstructionPolicy.LazySingleton`。它没有等价旧装饰器；只投影 @refcount 会丢失单例保证。绑定器在继承、mixin、record/legacy dataclass 和构造重载展开后验证无参契约，将隐式构造、直接类型调用、有类型上下文的 new()、泛型构造及其他已支持的构造入口统一交给 SingletonPlan；不允许序列化或复制生成器旁路分配第二个实例。基类初始化单独作用于当前 self，不误用基类的单例入口。

SingletonPlan 以规范化类声明身份和闭合类型实参为键，别名不另建槽。每个键生成唯一的访问函数与强引用存储；多模块/翻译单元只引用同一所属模块的定义，不能用头文件中的 internal-linkage static 产生多份实例。入口在原表达式求值位置执行，返回既有 PyRefCount 包装，普通值赋值/容器传递继续共享身份。

C++11 运行时增加独立 SingletonCell，状态为 Empty / Constructing(owner_thread) / Ready。首次竞争者登记 Constructing，在锁外执行完整构造，成功后以同步发布转为 Ready；其他线程等待已完成实例。构造失败销毁已经构造的部分、恢复 Empty 并唤醒等待者。初始化路径记录线程和依赖关系，检测同线程重入及跨线程等待环，避免依赖原生静态初始化的未定义重入行为或永久死锁。不得复用 MemoCache 的并发重复 miss、LRU 淘汰或清理 generation 协议。

单例强根由运行时持有，进入关闭阶段后按约定释放，禁止析构过程触发重新创建；初始化时的外部副作用沿普通异常规则处理。访问函数不开放 clearCache/reset，原构造体保持内部专用入口。同步状态、异常清理、唯一链接身份和全部构造入口接通前，对 lazy class 明确报未支持，不能把一个静态可空指针当作完成实现。

### 4.2 属性、引用与惰性参数

属性兼容桥先把旧字段属性、postsetter 简写、新 property 块和只读 property def 规范化为明确的存储绑定与 get/set/post_set，再投影。parser 在类成员上下文依据 property 后的 NAME 或 def 分派；只读简写直接建立同一个 `PropertyDecl` 及唯一 `AccessorDecl(kind=get)`，保留属性名称、property/def、参数、可选返回注解和正文的源位置及写法来源，不先登记普通方法。省略注解继续使用属性共同类型推断；静态标记进入 is_static，不合成 self/cls。只读简写与等价完整块无 hook 时投影为同名旧 @property/@staticproperty getter，保留只读访问权限，不合成 setter 或隐含存储；完整块无 hook 时可直接生成同名旧 getter/setter。有 hook 时生成普通 getter、setter 包装和按属性唯一命名的内部 setter-body/hook 方法，由包装依序调用，覆盖提前 return 的正常退出。绝不能把三种访问器机械映射成同时存在的 @property/@property.setter/@property.postsetter：ClassInfo 当前拒绝该组合，旧 emitter 还会自动赋值而忽略显式 setter。生成辅助方法受内部名称与来源管理，不成为公开反射成员。

旧 postsetter 入口在规范化时补出原隐含存储、getter 和赋值 setter，原回调放入 post_set；保持字段默认值、元数据、record/legacy dataclass 的构造参与及反射映射，不改成普通手写 _x 后丢失这些信息。self.__value__/Self.__value__ 作为旧存储兼容引用保留。S0502 等风格规则应基于源属性节点判断，对已归一化的新块不再建议退回旧 postsetter；不能用全局关闭 strict 来通过兼容桥。类型/访问权限/所有权检查仍作用于生成语义。

参数 lazy 与 ref 前缀在规范化及合法位置检查后可以回投旧 @lazy/@ref 标记，保留 ReferenceTypeSyntax 和 ParameterEvaluationMode 的不同归属，并将 SourceMap 指向原前缀。旧标记也归一到相同节点；lazy ref 的 supplier 返回值类型仍为 T，本次调用的 memo 再以引用供正文使用，不得错误地让 supplier 返回调用者引用。可空与 Callable 层级在该桥中保持，重复新旧标记应在投影前报错。引用语义、合法位置与参数求值次序沿用原规则；现有后端没有完整引用逃逸分析，悬垂引用诊断需补齐。旧 emitter 仅在读取路径物化 memo，直接对 lazy ref 形参赋值/增量赋值还须把写目标接到本地 memo，未接通前明确诊断，不能以类型投影代替实现。

### 4.3 声明缓存运行时

声明缓存不能假装成已有 @lazy 装饰器。语法层只记录无参数的 lazy 修饰词；`@LazyCache(...)` 经普通装饰器语法入树，绑定到内建配置身份后校验目标、参数和重复配置，规范化为 CachePolicy 的容量。保留装饰器及容量表达式的 SourceMap；不得在 parser 中执行配置表达式或按文本名称劫持用户装饰器，具体默认值和容量规则只在 [声明缓存规范](./syntax-migration.md#declaration-cache) 定义。

建立绑定到声明/重载/特化身份的 CachePlan，完成键/结果所有权、方法组合及失效操作检查，再由中立 IR 生成包装入口、未缓存正文入口和私有存储。所有正常调用及函数引用须落到包装入口，直接递归也经包装处理重入；参数绑定及求值仍按正常调用发生，键按绑定后的声明顺序取得。clearCache 在名称及声明绑定之后识别，del 在属性绑定后形成失效计划，不能仅按成员拼写拦截任意对象。缓存内部字段和 helper 不进入用户构造参数、相等/序列化/公开反射；值对象 copy/assign/move 的缓存清理由对象模型统一接通。隐藏槽以受控方式原位构造和发布结果，仅析构已经构造的对象，不额外要求结果类型可默认构造或可赋值。

新增 runtime LazyCell 与 MemoCache，分别维护 Empty/Computing/Ready 单槽状态或按键值/LRU，以及重入标记、锁、generation、显式失效和析构。参数的每次调用 memo 可以共享底层安全持有机制，但存储范围和求值协议必须独立。锁内只保护缓存元数据，锁外运行正文；清除通过 generation 校验防止旧计算回填，不以取消本次调用代替失效。noexcept 的正文 Result 转换之后检查 Ok/Err 再决定发布结果；公共缓存入口还须将键构造、查找/重入、结果复制和发布等缓存操作的可表示异常转换为 Err，E 必须覆盖这些错误，并确保失败解除计算状态。入口转换未接通前拒绝 noexcept 组合，不能依赖正文转换处理外围缓存错误。运行时和 codegen 完成前应诊断缓存声明为未支持，不把生成一个普通 getter/函数当作缓存已实现。

### 4.4 可空分析与求值

可空语法的桥接还需先完成绑定/流分析及求值计划，再生成旧 AST 能表达的临时变量和分支，或扩展后端接收中立 IR。T? 不能在 parser 阶段统一变成旧 T|None；当前 refcount 分支会擦掉可空性，boxing 分支又可能形成 Optional<Pointer>。新 NullableValue 的强制转换、运算提升和引用空异常应有明确运行时入口；原 Optional→T 自动 value__get 不能被新语法意外继承。流分析覆盖判空、分支/循环合流、重新赋值、参数/返回和字段初始化；别名、重复 property 调用及副作用使相应流事实失效。NullSuppressExpr 在诊断后仅投影其操作数，同时保留来源，绝不以 value__get 或非空断言代替。普通引用访问还必须统一提供空引用失败路径，现有 refcount operator->/* 的未定义行为不能充当规定的异常。旧 Optional ADT 保留，通过显式边界适配其存储、模式及成员。

### 4.5 Callable、lambda 与回调

箭头形式和旧 lambda 都规范化为 LambdaExpr；当前受支持的简单形状可投影到 ast.Lambda，普通参数放 ast.arguments.args，显式拒绝旧验证漏查的 posonlyargs 等形式，保留源头和函数体位置。若函数体需可空分支/临时变量，应在该 lambda 内部 lowering，必要时用中立函数体 IR，禁止把计算提升到 callable 创建点。旧后端没有通用 visit_Lambda；Callable/委托/key 等专用路径的类型传播、参数和返回检查必须分别接通，不能只构造 AST 就宣布所有表达式位置可用。

当前 lambda 的无目标形参/推断返回槽存在 int 回退，首次带 Callable 注解的变量声明也未向 lambda 发射器传入目标形参；这应在共同类型检查中修正，不冻结为新语法语义。函数作用域 lambda 实际引用捕获局部变量；PyCallable 只拥有 callable 对象，不延长这些引用或 self 的寿命。首期保持已有效支持的上下文并诊断未实现组合，完整逃逸闭包、直接返回 lambda、嵌套和立即调用作为明确的后续语义工作。

CallableTypeSyntax 的固定签名递归投影为旧 `Callable[[参数类型...], 返回类型]` AST，保留 None 返回和各类型/箭头的 SourceMap，合成的内建 Callable 标记避免用户同名符号遮蔽。旧 Callable 入口经绑定确认后与箭头类型生成相同 `TypeNode.template("Callable", "PyCallable", ret, *args)`，不转换成 TypeNode.function_ptr；最终原生前端直接绑定该类型。泛型形参来自外层作用域，箭头类型本身不声明泛型；类型别名不产生新的名义委托。可空、引用及元组层级不得在桥接中丢失，Callable 目标签名须传入 lambda 参数与返回检查。

Callable 桥接须保留 [可空规范](./syntax-migration.md#nullable) 中 NullableValue 与未绑定 PyCallable 空槽的两层表示。引用返回签名还需处理旧空槽路径的 `Ret()` 无法生成引用的问题；完成运行时适配前不开放该组合。

call/from 为回调建立只覆盖 invocation 与 body 的临时符号层，参数与局部变量另有函数作用域；候选 as 目标属于外围赋值作用域。使用 DeclId/SymbolId 处理遮蔽和递归，递归绑定代码及当前环境，避免环境强持有自身 callable 形成引用环。函数体采用独立 HIR/控制流图，保留多路径返回和异常清理；不能把概念上的隐藏 def + 调用展开当成完整闭包实现。在原语句位置创建环境并执行 invocation，按需保存结果；拥有环境或借用证明决定保存后的回调寿命，异常路径释放已构造环境。

### 4.6 运行时 match 表达式

MatchExpr 在 CPython AST 中没有直接对应。兼容桥必须先完成值模式绑定、guard/结果类型检查、穷尽性和所有权检查，再通过中立表达式 IR 在原求值点 lowering 为源序分支及结果合流。主体绑定独立临时值，arm 捕获用独立 SymbolId；所选结果直接构造合流值，或按需构造尚未初始化的结果槽，不先默认构造全部分支结果，也不额外要求结果类型可默认构造。结果的移动、引用、借用和析构时机沿用目标类型规则。作用域局部不代表生命周期安全：返回 capture 的借用或 `() => capture` 必须有可证明的有效生命期或拥有捕获环境，未实现时明确拒绝。

该 lowering 不得把主体、guard 或结果提升出 and/or、??、条件表达式的短路位置、lambda 的调用体或循环条件的每次求值位置。旧 ast.Match 是语句且存在分组/guard 行为差异，不能直接投影替代；通用闭包/IIFE 也不能作为默认桥接捷径，以免额外引入未实现的捕获、逃逸或移动语义。后端按运行时模式类别接通有序测试和绑定，保留失败与异常边；原位置插入和结果合流能力完成前，应报告未支持的表达式上下文。

### 4.7 编译期展开与类型模式

inline for 与旧 inlineRange 循环都规范化为 ForStmt 的 InlineRange 模式，绑定后形成 RangeBounds。兼容桥恢复 `ast.For(iter=Call(Name("inlineRange"), 原实参), ...)`，复用原展开器；不能只去掉 inline 而发射普通 range。原展开按范围顺序复制 body、替换索引读取并折叠已有静态 if，运行时副作用顺序保持。mixin 路径仍在宿主绑定及 iterFields/fixed-vararg 展开后处理，普通方法保留 ClassInfo 上下文，不扩大模块函数支持。现有索引替换不建立新作用域、不保留末次索引赋值，同名嵌套/遮蔽和索引再赋值的绑定缺口单列，不能在拼法迁移中悄悄改变。SourceMap 记录原循环头、循环体及克隆迭代来源。

inline if/match 共用带目标类型的 CompileTimeValue，静态求值返回 KnownValue/Dependent/Error；InlineIfStmt 的 KnownBool 是 KnownValue 要求为 bool 的专用结果。已知条件按源序只展开首个命中的分支并投影为旧语句序列，必要时补 pass；Dependent 保留在自有树/中立 IR，等类型/值实参或宿主绑定后选择，不能直接变为普通 ast.If。两种静态分支的目标覆盖函数/方法语句、普通类成员和模块声明；先用不含条件分支成员的声明骨架/常量依赖图提供求值环境，再选择分支，最后建立完整的 ClassInfo、受控导入依赖、布局、record 生成/legacy dataclass、属性和反射集合。每个实例保存独立的有效声明视图。条件/主体/模式依赖它正在控制的声明或布局时报告循环，不先把未选声明注册进去求值。

TypeMatchStmt、ConditionalTypeSyntax 和已有函数类型 if 共用类型 matcher，返回 Matched(bindings)/NotMatched/Dependent/Error。主体、构造头及非捕获类型先按外层环境绑定，透明别名展开后按规范化身份及实参结构比较；CaptureTypePattern 仅收集对应完整 TypeUse，AppliedTypePattern 递归匹配固定类型槽。成功才创建局部 SymbolId 并绑定正向后继，失败即丢弃本次捕获，依赖未决则保留到特化，未知类型名或值主体报 Error；不能用“未找到类型就捕获”补救。OR 各备选独立求 bindings，预检同名集合、单备选重名及不可反驳位置，不合并失败备选的捕获。guard 使用已有静态求值器；条件类型先绑定条件，再向 true 类型传播成功 bindings，false 类型仍在外层环境绑定。正向 and 的后续条件使用前面已成功的捕获，不向失败/负向路径传播。

选择结果进入共同的分支投影、特化和声明视图流程，保留语法来源；type match 始终按源码顺序，宽泛 `list[type U]` 可以先于 `list[int]` 命中，不能沿用旧 type_if 的精确模式优先排序。优先复用 type_node.py 的结构化相等/模式基础并补齐 TypeUse、别名、可空身份和稳定 TypeId，避免 C++ 字符串匹配；不能投影为普通 ast.Match，也不能把捕获伪装成新公开泛型形参。legacy adapter 根据 capture_params 与符号绑定把旧 `_U=...` 槽规范化为局部 CaptureTypePattern，迁移工具同步重写实际引用和删除捕获槽，检查显式使用原捕获实参的兼容边界，不凭名称前缀改写普通形参。已知条件类型先替换成功分支中的捕获类型再桥接，Dependent 节点保留到特化，不能为了旧 AST 可读而提前选 fallback；首轮未支持的捕获上下文明确报错。

InlineMatchStmt 先求主体，再用纯静态 matcher 处理所需 Pattern，返回 Matched(bindings)/NotMatched/Dependent/Error；成功时建立 case 局部捕获环境、求 guard，guard 假丢弃绑定，真则展开正文。不按枚举/union 类型重排 case；OR 的备选也按源序保留。已知选择降低为语句序列并物化捕获，空结果按 suite 要求补 pass，依赖选择保留到特化；不能回退为 ast.Match。CompileTimeValue 使用显式值域和 TypeId，不继承宿主 Python 的 True==1 或枚举退化成整数行为；求值/匹配缓存依赖目标类型、特化实参和宿主常量，SourceMap 记录 case/guard/捕获及实例来源。

全部 case 先做模式 profile、重复捕获、OR 捕获名集合及不可反驳模式位置等结构检查；无 guard 的不可反驳 case 必须最后，OR 内不可反驳备选也必须最后，case guard 不改变 OR 内部可达性。类型一致性在实际需要绑定模式时检查；未选正文不走旧 visitor 的常规语义遍历。S0803 末尾默认分支/穷尽性规则仅作用于普通 match，不能全局关闭 strict。当前 match_case.py:1462 将 wildcard 抽离并可能丢 guard，union_match.py:106 按变体分组，match_case.py:220 的 annotation matcher 按固定元数据优先级选择；都不能复用为新源序选择器。普通 match、union/Optional 穷尽性和字段 annotation 原有规则独立保留，不机械加 inline 迁移。

与 inline for 联动时先做已约定的结构预检，再按外层索引绑定、inline if/match 选择、所选体展开的顺序执行。旧 `inline_range.py:271` 先递归两个 if 分支再折叠，新节点不能沿用该顺序；未选体的成员/类型错误及无效展开应被隔离，而循环体原有 break/continue 全子树限制仍保留。静态比较/布尔求值及模式匹配需补齐独立实现，旧 static_reflect 的比较只支持 ==/!=，不得以 Python eval 或当前有限折叠器冒充完整功能。

旧 type if 具有具体类型优先及模式分派、无 else 时的未覆盖断言，不能机械恢复为该路径来实现新 inline if 的源序/no-op 规则；旧宏 if 会发射全部分支再由 C++ #ifdef 选择，首版新条件不接受 __macro__。需要符号类型/NTTP 的泛型分支时，在前端特化剪枝或生成经验证的 C++11 分派，不增加 C++17 if constexpr 依赖。hasattr 等静态反射只有在绑定接口提供可靠的已知结果后才能加入条件求值范围。

现有 passes 的拆分以真实依赖为准：保留 dataclass、enum/union、descriptor、mixin、generator/coroutine、decorator、protocol、final 和语义分析的现有先后关系。逐个把隐含前置条件变成输入/输出契约、PassContext 和显式数据；TypeNode 先去掉 Python Enum/dataclass 运行时，再减少 C++ 字符串反解析。首期不引入新的 SSA/LLVM 层，以当前 C++ 发射器能消费的类型化 IR 为目标。

## 5. 统一入口、bootstrap 子集与模板

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

## 6. 阶段与自举闭环

建议按以下阶段实施，每阶段均有独立可验收结果。

| 阶段 | 工作与交付 | 通过条件 |
|---|---|---|
| P0：冻结基线 | grammar/profile、语料清单、AST/API schema、依赖清单、可重复输出开关 | 确认语言支持与语义差异；记录现有有效输出、负例诊断和性能；已有失败单列 |
| P1：统一前端入口 | SourceManager、parse API、CPython adapter、不可变模块解析缓存 | 模块发现/stubs/DSL 不再散落裸 ast.parse；旧程序结果等价 |
| P2：原生前端纵向样例 | bootstrap 子集写 Lexer/Parser/NodeStore；接 legacy_lowering；实现 enum（含 type enum）/final/const/ref class | 现有编译器能编译并运行新 parser；新旧写法规范化 AST 相等；旧后端行为相同 |
| P3：覆盖已有语法与第二批扩展 | 加入 record/frozen/ordered/optional 的类头和字段解析、RecordPlan 绑定、有效布局、生成成员、C++ 发射及遗留桥；加入 lazy class 单例构造、property 块及只读简写、ref/lazy 前缀等价迁移和声明缓存 runtime、箭头 lambda/Callable 类型简写与共同类型检查、call/from 回调 HIR 与闭包检查、inline for 等价迁移和 inline if/inline match 静态选择、type match/条件类型/函数类型 if 的显式 type 捕获与共同 matcher、运行时 MatchExpr 及结果合流、可空语法及流分析/运行时支持；补齐泛型、模式、推导式、生成器/异步、f-string、FFI 语料 | 项目语料及负例预期覆盖；Python 交集与 CPython 差分、旧新标记与循环展开等价；record、单例、缓存、可空、匹配和闭包分别通过第7节验证矩阵；原生前端无 Python 回退 |
| P4：编译器内核迁移 | TypeNode、符号、analysis、passes、emit、模板 helper/evaluator 逐模块改写 | 编译器核心通过 bootstrap profile；宿主/原生结果对照；CPython AST 桥退出生产路径 |
| P5：完整原生构建 | 原生 CLI/module loader/driver，重建 runtime、模板和代表项目；版本化缓存可后补 | 无 Python 环境下正常完整编译；无宿主模板执行、隐藏解析回退或 pickle 依赖 |
| P6：自编译闭环 | 对固定编译器源码连续自编译，重跑全部回归 | C2/C3 生成结果及行为一致；保留 seed 与复现脚本 |

P3 内的 inline if/inline match 共用求值与剪枝框架，分两步交付：先实现当前环境已知值的函数/方法分支、静态标量模式及 inline for 联动，再实现待特化条件/模式和模块/类声明剪枝。后一步完成前，对未支持的位置或依赖明确诊断；不能把常量 True/False 的词法样例当作完整编译期分支支持。inline match 的序列、映射、union 等结构化静态值模型独立增量交付，解析语法可共用不表示静态求值已经可用。

record 的 P3 纵向切片先交付 native `.py2` 的 class-head/field parser、RecordPlan 和负例诊断，再接通布局与 C++ 生成，最后接 legacy_lowering。桥接阶段必须运行 Plan 驱动的生成成员、optional 的构造后覆盖和 frozen 布局检查；只让旧 `@dataclass` pass 接收一个同形 ClassDef 不算交付。旧 `@dataclass` 与后置 `T @optional` 仍由旧方言入口保留，不能在这一阶段与新 record 语法混写。

type match 同步接入上述选择/特化框架，交付精确类型、type U 显式捕获、固定形参构造模式、OR、_ 和 guard；条件类型与已有函数类型 if 复用 matcher 及成功绑定环境。list[int]/list[type U] 读取类型结构，不要求 inline match 先能静态执行 list 对象的序列模式；二者能力分别验收。匿名形状、NTTP/参数包/维度捕获及可空解构另行设计，不混入本轮 type NAME 的单类型槽语义。

MatchExpr 独立接入 P3 的运行时表达式 HIR：先完成基本值模式的源序测试、局部捕获、目标类型传播和穷尽诊断，再逐类接通已有结构化运行时模式及其载荷覆盖证明。短路、lambda、循环条件中的原位 lowering 和非默认构造结果须与基本功能一同验收；不以静态 inline matcher 或仅赋值右侧样例代替完整表达式求值方案。

ref/lazy 前缀迁移与声明缓存分两项交付：前者先通过旧 AST/HIR 与调用行为等价验证，后者必须同时交付 CachePlan、LazyCell/MemoCache、生命周期/结果保存检查及 del/clearCache 内建失效。声明缓存从同步有体的合法声明子集开始，容量配置/有限 LRU、实例/特化隔离、复制移动清理、异常/Result、重入和并发 generation 均作为开放语法前的验收条件；不以解析成功或单线程无副作用样例替代缓存语义。

lazy class 依赖 ref class 对象模型，但作为 P3 的独立构造策略交付 SingletonPlan/SingletonCell，不混入参数 lazy 或函数缓存的等价迁移。严格无参、全部构造路径一致和线程安全发布与语法一起验收。

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

call/from 的接口及候选 as、通用块 lambda 按 [规范状态](./syntax-migration.md#call-from) 逐项开放；语句入口可先复用普通 suite，表达式块入口仍需独立布局验收。

## 7. 验证矩阵与工具迁移

三条差分路径同时保留：Python 交集的 CPython adapter/原生 parser 规范化 AST 对照；旧装饰器/新语法的同一 HIR 对照；生成 C++、运行行为和负例错误阶段对照。临时节点 ID 不直接作全等比较，SourceMap 独立验证。加入有界随机/变异语料检测异常缩进、Unicode、f-string、泛型默认值、非法 modifier、崩溃和非终止。

| 能力 | 验收重点 |
|---|---|
| record/frozen/ordered/optional | 类头和字段软关键字只在规定结构生效；固定生成成员及手写冲突、`__str__` 回退、`__post_init__` 后 optional 覆盖、optional 默认值与 assign/new 写入、ordered 的完整逻辑字段比较；frozen 的实体基类/mixin/property/descriptor 有效布局、拒绝项和内部缓存槽隔离；@serializable 冲突及反序列化缺字段默认值/诊断；新旧方言不混写，桥接结果与 RecordPlan 一致 |
| ref class 与既有声明 | 旧 @refcount 的构造/赋值/身份/容器/WeakRef/继承等价；ref T 不混同；对象模型冲突、新旧重复及 enum/final 原约束 |
| lazy class | 声明/注解不构造，A()/new()/别名同一身份，首次字段和 init 仅执行一次；无参及生成/继承构造检查，特化/派生类隔离，零外部引用后仍不重建；线程竞争、重入/等待环、失败重试和部分析构；跨模块唯一槽与绕过入口拒绝 |
| 属性 | 简写/完整块归一，共同类型推断，setter 正常/异常/hook 顺序，单次求值，旧存储、record/legacy dataclass、反射及 S0502 兼容 |
| ref/lazy 参数 | 类型/ABI/supplier/memo 等价，未使用/重复/默认/透传，lazy ref 写入与借用寿命，前缀层级和非法组合 |
| 缓存 | @LazyCache 的绑定/常量参数/目标/重复诊断，缺省无界及有限 LRU/0/None；实例/声明/特化隔离、键规范化、clearCache 绑定/失效 generation、重入/并发、Result 外围错误，复制移动/安全持有/反射排除 |
| 可空 | 值/引用/泛型分类，! 不解包，访问链/括号/短路，属性和 hook 次数、运算真值表、空解引用及旧 Optional 适配；用 C# 小程序核对对应语义 |
| Callable/lambda/call | 新旧签名/ABI、目标传播、多路径返回、局部 f/外围结果作用域、零次/多次/延后回调、递归/异常/逃逸；通用块体另测局部布局 |
| inline for | 新旧展开 AST/HIR 和运行副作用等价，嵌套宿主/索引依赖、结构预检、拒绝项及 clone 来源 |
| 静态分支 | 源序、Dependent 不越过、guard/OR/捕获、未选体隔离，声明剪枝、循环依赖、特化隔离及原运行位置 |
| type match/捕获 | 精确身份与完整 TypeUse、显式 binder/OR/外层同名、成功路径作用域，旧捕获槽迁移及类型/值模式分离 |
| MatchExpr | 全 arm 类型检查、上下文传播/覆盖证明，guard/异常/副作用，短路和循环位置，非默认构造/移动结果及借用寿命 |

P0 还应处理已发现的规范漂移：手册将宿主最低版本写成 3.10，而 PEP 695 需要 3.12、泛型默认值需要 3.13；union 模式现有测试使用 `case new.Variant(...)`，手册仍有 `case Msg.Variant(...)`。record 规则已经确定：新方言使用 `record`、`frozen`、`ordered` 和前置 `optional`，其生成成员、完整 frozen 布局、排序字段与构造后覆盖规则以 [迁移规范](./syntax-migration.md#records) 为准；旧 `@dataclass`、后置 `@optional` 仅作为 legacy 兼容路径并需单独回归，不再把它们的历史漂移当作新语法待定项。

文件兼容与工具链也需要进入交付范围。新关键字文件采用 `.py2`，旧 `.py` 与 `.pyi` 保持兼容入口；import resolver 同时认识两者，同名模块同时存在时明确报错，避免悄悄改变解析优先级。首个原型可用显式 dialect 参数接入测试，正式开放前同步文件发现、构建脚本、FFI 桩扫描、nav/architect、语法高亮、格式化与错误跳转。迁移工具用 token span 修改，保留注释；Python 的 ast.unparse 无法直接输出新语法。软关键字只解决名称兼容，新语法文件仍需要相应 IDE 支持。

当前 `plugins/py2cpp-lexer` 与根目录 `lexer_preview.py2` 用于高亮检查。GPU 模型分类和 TextMate grammar 不承担 compiler AST/语义验证；示例可展示的拼法不表示上述编译器阶段已经实现。
