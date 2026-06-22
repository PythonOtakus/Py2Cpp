---
name: py2cpp
description: >-
  Py2Cpp 语言特性与标准库改动的完整开发流程：新功能须先复述理解与疑问并经用户确认、
  翻译器、passes、codegen、runtime 重生成、MSVC 编译与 unittest 回归；强调勿重复造轮子、
  严格按编码规范、实现后须自行对照规范自检、冲突须根治勿绕行、先问清再实现。在修改 py2cpp
  翻译器、添加语法、改标准库、调试 build_all/build_example 失败、MSVC 找不到 cl、
  命名空间/PyRange 编译错误、exe 运行时崩溃难定位时使用。
---

# Py2Cpp 开发与验证流程

将受限 Python 3 静态译为 C++11。**单一真相源**是仓库根 `py2cpp/`（标准库 Python）与 `src/`（译器）；`generated/` 仅由 `main.py` 生成，勿手改。

详细架构见 [docs/参考手册.md](../../../docs/参考手册.md)；标准库写法见 [docs/编码规范.md](../../../docs/编码规范.md)。

**查阅表**（Passes 顺序、`constant` / `STDLIB_REL_PATHS`、生成物、MSVC 扩展、测试矩阵）：[reference.md](./reference.md)

---

## 冲突须根治，勿绕行（重要的事情说三遍）

1. **写法出现冲突时应解决冲突**（译器、`py2cpp.h`、MSVC 宏、`#undef`、属性派发等），**不要**换一种不符合 [编码规范.md](../../../docs/编码规范.md) / CPython 对外 API 的绕行写法（例如用 `dirname` 代替 `self.parent`、手改 `generated/`）。
2. **写法出现冲突时应解决冲突**，在根因处修（如 `parent`/`suffix` Win 宏 → `py2cpp.h` + `this->parent()`；`@property` 未生成 `()` → `_class_info_for_receiver`），**禁止**用“能编译就行”的替代 API 糊弄过去。
3. **写法出现冲突时应解决冲突**：标准库与用户代码仍写规范 Python（`self.parent`、`Path.suffix`、链式比较、`Self._…` 静态调用等），冲突由基础设施层一次性消掉，**不得**把妥协扩散到业务代码。

---

## 勿重复造轮子，严格按编码规范（重要的事情说三遍）

1. **不要重复造轮子，严格按照 [编码规范.md](../../../docs/编码规范.md) 写代码**：实现前先查 `py2cpp/` 已有模块（如 `text.str` 的 `rfind`/`replace`/`split`、`io.file.path` 的 `dirname`/`basename`/`splitext`），能复用则复用，**禁止**手写 `while` 扫字符、私有 `_slice_str` 等与现有 API 等价的逻辑。
2. **不要重复造轮子，严格按照编码规范写代码**：标准库层用规范 Python（`Self` 静态调用、链式比较、`new`、勿手写 dunder、无 STL）；**切片起始为 0 时省略**（`path[:2]` 勿写 `path[0:2]`，与编码规范 §栈子区间一致）；与 CPython 3.13 语义对齐见编码规范 §8；`Path` 与 `os.path` 分工明确（pathlib 规则 vs `splitext` 等），勿混用语义。
3. **不要重复造轮子，严格按照编码规范写代码**：缺能力时优先补全/修正**已有**抽象（译器、`str`、`util`、C 层 `os_cpp`），**不要**在业务模块堆一次性 helper；写完后须走下文「实现后须自行对照规范自检」。

---

## Native 原子化（业务零 `@native`，C++ 只加速叶子）

1. **判据**：若某函数可无损写成「纯 Python + 更小的 `@native`」，则**不得**对该函数标 `@native`；语义落在 Python 组合层。
2. **`util/memory`**：``copy_buf`` / ``buf_to_str`` / ``load_u64_le`` / ``load_u64_le_bytes`` 为 ``@native``（各带 ``*_ref``）；缓冲扩容见 ``array.reserve``。
3. **`serde/json`**：``JsonEncoder`` 静态 ``append_*`` / ``fast_encode`` 纯 Python + ``JsonDecoder`` 实例 decode 组合（``load_u64_le`` 来自 ``util/memory``，``span``→``str`` 用 ``str.from_codes_span``）；``@serializable`` codegen 直调 ``dec.parse_int_at_ascii()`` / ``dec.str_assign_from_seg(seg)``。**无** ``json_scan_cpp``。
4. **C++ 可无损删除**：关掉 ``memory_cpp`` 注入后仍靠 Python 组合 + 叶子 ``*_ref`` 全绿（性能可降）。

---

## 实现后须自行对照规范自检（重要的事情说三遍）

每次**新特性落地**或**修改** `src/`、`py2cpp/`、`test/` 之后，在 bootstrap / MSVC 之前或与之并行，Agent **必须**主动对照 [编码规范.md](../../../docs/编码规范.md) 与相邻模块**自行审阅** diff，**不得**只跑编译、不查写法。

1. **实现后须自行对照规范自检**：标准库与用户测试仍写规范 Python——`new` / `Self` 静态调用、链式比较、**勿手写 dunder**、辅助数据结构用 **`@dataclass`**（勿手写 `__init__` 拼字段）、`@copyable` 等与域内范本一致；**无 STL**；能复用 `str` / `path` / `util` 现有 API 的**禁止**手写 `while` 扫串、重复 `splitext` 语义。
2. **实现后须自行对照规范自检**：对照编码规范 §2–§3、§8、§10 做清单核对——`s[:k]`（起始 0 省略 `s[0:k]`）、`not s` / `if s`（勿 `len(s)==0`）、`int64` 大常量勿用 32 位乘法溢出、测试用 `TestCaseMixin` + `override def test`；**同名符号**（如 `time` 函数 vs `datetime.time`）import 绑定与 C++ 名无歧义；依赖内建（`int(str)` 等）时确认译器已支持，否则在基础设施层补，勿在业务模块假造轮子。
3. **实现后须自行对照规范自检**：与上文「冲突须根治」联动——Win 宏、`parent`/`suffix`/`date`/`time` 等须在 `py2cpp.h` / 译器根因处理，**禁止**为通过编译改业务 API；对外可见行为变化须同步 `docs/参考手册.md` / `docs/编码规范.md` §8.1；自检未通过则继续改源树，**禁止**声称完成或只改 `generated/`。

**最小自检表**（可 mental walk，宜在回复用户前过一遍）：

| 项 | 查什么 |
|----|--------|
| 范式 | `new`、无手写 dunder、dataclass/copyable、无 STL |
| 复用 | 已搜 `py2cpp/` 同域 API，无重复路径/解析逻辑 |
| 切片/布尔 | `[:k]`、`not s`，符合 §栈子区间 / §布尔 |
| 语义 | 与 CPython 3.13 / 编码规范 §8 一致，边界与「暂不实现」未蔓延 |
| 基础设施 | import/C++ 重命名/宏/属性 `()` 在根因处修完 |
| 验证 | §0 bootstrap + 触达 `test_*.py` MSVC 全绿（见下） |
| 崩溃 | 难定位 → §「崩溃难查先用 --debug」+ `dbg.log` 最后一行 |

---

## 先问清再实现（重要的事情说三遍）

1. **先问清再实现**：新功能或**改变对外可见行为**（新语法、标准库 API、容器/切片/view 语义等）时，**须先**向用户提交「理解 + 疑问」并**等待明确同意**，再改 `src/`、`py2cpp/`、`test/`、`docs/`；未对齐前**禁止**大规模写实现代码。
2. **先问清再实现**：有歧义则继续追问，**直到彻底弄懂**再进入 §0 动手；勿凭猜测定边界、测例范围或与 CPython 的差异。
3. **先问清再实现**：用户确认（或修正理解后再次确认）后方可 bootstrap、加测试、声称完成；仅 typo/注释、用户给出无歧义完整 spec、或用户明确「直接改不用先问」可跳过完整对齐，**仍须**用一句话说明意图。

---

## 崩溃难查先用 --debug（重要的事情说三遍）

1. **崩溃难以排查时优先用 `--debug`**：exe 无输出、`0xC0000409` / `-1073740791`、疑似栈溢出或「猜栈帧拆分」无效时，**先**重译并编译带 `--debug` 的用例，跑 exe 将 **stderr** 重定向到日志，**以最后一条** `[py2cpp] 源.py:行号 …` 定位崩溃前执行的 Python 级调用；**禁止**在未看 debug 日志前盲目拆函数或改 `generated/`。
2. **崩溃难以排查时优先用 `--debug`**：测试/示例用 `build.bat PATTERN --seq --debug`（或 `python main.py … -o generated -c --debug --exe …`）；需跟踪标准库/runtime 内调用时，**先** `python main.py py2cpp\__init__.py -o generated --no-main --debug` 再编目标用例；日志格式见 `src/codegen/debug_cpp.py`（`fprintf(stderr, "[py2cpp] …")`）。
3. **崩溃难以排查时优先用 `--debug`**：常见根因包括 **未捕获 C++ 异常**（如 `fs_*` 抛 `OSError`、非空目录 `rmdir`）——debug 常停在 `throw` 前最后一条调用；与 unittest 软断言失败区分（后者有 FAIL 汇总）。定位后再修源树；`--debug` 仅调试用，**勿**作为发布默认。

**最小流程**（宜在 §0.3 编译通过后、反复二分仍无头绪时立刻做）：

```bat
build.bat io/test_path --seq --debug
generated\test\io\test_path.exe 2> dbg.log
REM 看 dbg.log 最后一行 [py2cpp] … 对应的 .py 行号
REM 需 runtime 内跟踪：
python main.py py2cpp\__init__.py -o generated --no-main --debug
build.bat io/test_path --seq --debug
```

---

## 需求确认（新功能 / 语义变更，必做）

落实上文「先问清再实现」；实现**新功能**或**改变对外可见行为**时，Agent **不得**在未对齐前直接大规模改 `src/`、`py2cpp/`、`test/`、`docs/`。

**须先向用户提交一份「理解 + 疑问」**，并等待确认；若有歧义则继续追问，**直到彻底弄懂**再进入下文 §0 动手与实现。

建议包含（可表格，宜短）：

| 块 | 内容 |
|----|------|
| **我的理解** | 目标、边界、与现有类型/API 的关系、典型 Python 写法、预期 C++ 形态（类名、拷贝/共享、只读/可写） |
| **待确认** | 不确定点、多方案取舍、与 CPython/编码规范是否一致、测试与文档范围 |
| **暂不实现** | 明确本次不做的项，避免范围蔓延 |

**用户明确同意实现**（或修正理解后再次确认）后，方可写代码、跑 bootstrap、改测试。

**可跳过完整对齐的例外**（仍应用一句话说明意图）：纯 typo/注释、用户已给出无歧义的完整 spec 且仅要求按 spec 落地、用户明确说「直接改不用先问」。

---

## 0. 动手前检查（避免低级错误）

在改代码或声称「已修好」之前，**必须**在仓库根目录执行本机验证，不要只改生成物或假设编译器存在。

### 0.1 环境

| 项 | 要求 | 自检命令 |
|----|------|----------|
| Python | 3.10+（PEP 695） | `python --version` |
| 工作目录 | 仓库根 `Py2Cpp/` | `cd` 到含 `main.py` 的目录 |
| PYTHONPATH | 一般不需要；用 `python main.py` | — |
| MSVC（Windows） | VS 2019/2022 +「使用 C++ 的桌面开发」 | 见下 |

### 0.2 MSVC / `cl`（Windows 必做）

**现象**：`cl` 不是内部或外部命令、链接失败、Agent 说编译通过但实际未跑编译器。

**做法（按优先级）**：

1. 用仓库脚本（推荐）：`build_all.bat`（全量）、`build.bat PATTERN [...]`（按子串/通配符编译匹配的 `test_*.py`）、`run.bat PATTERN [...]`（只跑已编译 exe）、`demo.bat PATTERN [...]`（编译并运行 `examples/` 下匹配的 `.py`）— `build`/`demo` 内含 `vswhere` / `vcvars64.bat` 探测。
2. 在 **「x64 Native Tools Command Prompt for VS 2022」** 中执行 `python main.py ... -c --compiler cl`。
3. 手动：`"%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"` 后再编译。

**禁止**：在未配置 `cl` 的环境下声称「MSVC 已通过」；若只能翻译不能编译，应明确说明并给出上述步骤。

### 0.3 最小验证命令（改完必跑）

按改动范围选一组，**全部 exit code 0** 才算完成：

```bat
REM 1) 重生成 runtime（改标准库 / 改会影响 runtime 的译器逻辑时必做）
python main.py py2cpp\__init__.py -o generated --no-main

REM 2) 单测快速迭代（示例：容器 + range）
python main.py test\misc\test_containers.py -o generated --no-main
call "%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cl /EHsc /W3 /std:c++14 /I generated\runtime generated\test\misc\test_containers.cpp /Fe:generated\test\misc\test_containers.exe
generated\test\misc\test_containers.exe

REM 3) 全量测试编译（发布前）
build_all.bat
```

或使用一行（脚本已调 vcvars）：

```bat
python main.py test\misc\test_containers.py -o generated -c --compiler cl --exe generated\test\misc\test_containers.exe
generated\test\misc\test_containers.exe
```

**注意**：测试/示例 TU 通常只 `#include generated/runtime/py2cpp/minimal.h`，**不要**再链 `generated/runtime/py2cpp.cpp`（易重复定义）。``compile.py`` 对 ``test/``、``examples/`` 已自动跳过 runtime TU。

### 0.4 规范自检（实现后、声称完成前）

落实上文「实现后须自行对照规范自检」三遍强调：**先**过最小自检表与相邻模块 diff 对照，**再**执行 §0.3 编译/跑测；仅编译通过不等于符合规范。

### 0.5 运行时崩溃（先用 --debug）

落实上文「崩溃难查先用 --debug」：**exe 异常退出且难以定位时**，按该节最小流程重编 `--debug`、查 stderr 最后一条 `[py2cpp]` 再改源树；勿手改 `generated/`、勿未看日志就声称「栈帧过大」。

---

## 1. 改动分类 → 改哪些文件

```text
用户要什么？
├─ 标准库 API/语义（list.append、str.split…）
│    → py2cpp/<域>/*.py（如 util/list.py、text/str.py）或包根 py2cpp/__init__.py
│    → 必要时 src/codegen/*_cpp.py（手写模板，如 tuple_cpp）
│    → 重译 runtime + 相关 test_*.py
├─ 新语法 / 新语句 / 新表达式形式
│    → src/translator.py（visit_* / _emit_*）
│    → 可能 src/passes/*.py（先脱糖再生成）
│    → src/analysis/analyzer.py、ir.py（类型/签名）
│    → 新 test/**/test_*.py（如 misc/、lang/）+ 更新 docs
├─ 装饰器 / @protocol / mixin / dataclass / yield / async
│    → src/passes/<对应>.py（须在 translator 流水线中已挂载）
│    → translator.py + protocol_traits_gen / 编码规范
├─ 运算符 / 内置函数（len、in、print、%…）
│    → `layout_emit` 展开 `+operators.{h,inl}`、emit/*_emit.py、translator 内建分发
│    → 标准库 __init__.py 桩声明
├─ 模块路径 / C++ 命名空间 / 万能头 include 顺序
│    → src/analysis/module_namespace.py
│    → src/codegen/umbrella_gen.py（py2cpp.h，单文件模板）
│    → src/emit/layout_emit.py、src/translator.py（per-module .h/.inl）
│    ⚠ 高风险：MSVC 对多个 namespace py2cpp 块、块内 #include <utility> 极敏感
└─ 仅用户示例/测试 Python
     → test/ 或 examples/，不改译器
```

**不要**直接编辑 `generated/`（下次翻译会覆盖）。

---

## 2. 标准库 API 改动流程

1. **读 CPython 3.13 语义**（编码规范 §8）：实现写在 `py2cpp/<域>/<mod>.py`（如 `util/list.py`、`text/str.py`）。
2. **写法遵守** [编码规范.md](../../../docs/编码规范.md)：运算符、`Self`/`new`、勿手写 dunder、无 STL。
3. 若模块在 `py2cpp/` 下且未被 `constant` 的 `STDLIB_SKIP_*` 排除，bootstrap 会生成 `generated/runtime/py2cpp/...`。
4. **重译 runtime**：
   ```bat
   python main.py py2cpp\__init__.py -o generated --no-main
   ```
5. **加/改测试**：`test/misc/test_<area>.py` 或 `test/lang/test_<area>.py` 等子目录，`unittest` 结构见编码规范 §10（`TestCaseMixin` + `override def test` + `main` 跑 suite）。
6. **编译并运行** 对应用例；大范围改动跑 `build_all.bat`。

### 2.1 模板类 / `.inl`

- 有类型参数的类：声明在 `.h`，实现在 `.inl`（由译器写入，勿在 `.h` 末尾重复 include 破坏顺序）。
- `tuple`：逻辑在 `src/codegen/tuple_cpp.py`，Python 侧 `py2cpp/util/tuple.py` 仅为薄声明。
- `str` 的 `format` / `%`：声明 ``templates/text/+str.h``（``PY2CPP_INJECT_CLASS`` 类尾）；实现 ``templates/text/+str.inl``（paste_after）；标量 ``format`` 见 ``templates/+operators.inl``。``__mod__`` 还须 ``protocol_traits.h`` + ``operators.h`` 且声明带 `template<typename... Args>`。详见 [codegen-templates.md §8.3](../../../docs/codegen-templates.md#83-注入模板命名与路径定案)。

---

## 3. 语言特性 / 译器改动流程

### 3.1 流水线（顺序不可乱）

`main.py` → `Translator.translate_file`：

1. **解析**：`ast.parse` → `ClassInfo`、模块函数  
2. **预处理 passes**（`translator.py` 中顺序）：  
   `expand_dataclass` → `expand_default_bool` / `expand_default_iter` → descriptors → mixins → kwargs → static_reflect → **generators（在 decorators 前）** → decorators → copyable → **move_state** → protocol → member_access → **descriptor_signatures** → analyze → **check_moved_use**  
3. **分析**：`SemanticAnalyzer`（`analysis/analyzer.py`）  
4. **生成**：`.h` / `.cpp` / `.inl`；runtime bootstrap 另写 `py2cpp.h`

新增 pass：在 `src/passes/` 实现并在 `src/translator.py` **按依赖**插入调用；加 `src/tests/test_*.py`（译器单元测，非 `test/` 集成测）。

### 3.2 测试分层

| 层 | 路径 | 用途 |
|----|------|------|
| 译器单测 | `src/tests/test_*.py` | 断言生成片段、import 发现、moved 检查等 |
| 集成测 | `test/**/test_*.py` | 翻译 + MSVC 链接 + `unittest` 跑通 |
| 负向协议 | `test/fail/test_*_fail.py` | `build_fail.bat` / `build_protocol.bat` |

### 3.3 文档

- 用户可见行为：更新 `docs/参考手册.md` 对应节（§6–8、§10）。  
- 标准库写法：更新 `docs/编码规范.md`（§2.3 切片、`§3.1` 布尔真值、`§5.1` 堆 ``str`` 切片、`§8.1` 模块对照）。  
- 与本 skill 文首「勿重复造轮子」一致的写法变更（如 ``not s``、``path[:k]``）须**同步**上述文档，勿只改 skill。

---

## 4. 内置 `range` 与 MSVC（勿恢复 range_shim）

| Python 用法 | C++ 策略 |
|-------------|----------|
| `for i in range(...)` | 原生 `for (int i = …)`，**不**构造 `PyRange` |
| `len(range(n))` | 编译期算长度，**不**构造 `PyRange`（`translator._emit_range_len_expr`） |
| `r = range(n)`、`for i in r` | `(::py2cpp::util::range::PyRange)(...)`（`runtime_make_range_expr`） |

**禁止**：恢复独立 `range_shim.h/.cpp` 或自动链额外 TU（用户已明确要求删除）。

**MSVC 坑**：多个子模块头各自 `namespace py2cpp { }` 时，`using namespace py2cpp` 可能绑到**最后一个空块**（如 `io.h`），导致找不到 `PyRange`。当前稳定方案：**扁平** `py2cpp.h` include 列表 + 包根 `py2cpp.h` 中定义 `PyRange`；勿在未成套设计下改「子头去掉 py2cpp + 万能头单块包裹」（易引发 `py2cpp::std`、前向声明污染）。

---

## 5. 命名空间与头文件（高风险变更检查单）

仅在**明确要改**命名空间布局时做；须**成套**验证，不可只改 `.h` 不改 `.inl` / umbrella / `using`。

| 概念 | 规则 |
|------|------|
| 用户模块 `a/b.py` | `namespace a { namespace b { … } }` |
| 标准库 `py2cpp/util/list` | `namespace py2cpp { namespace util { namespace list { … } } }` |
| `set` 模块 | C++ 段名 **`py_set`**（`py2cpp::util::py_set`） |
| `.inl` 实现 | runtime 的 `.inl` **不**套 namespace，用全限定 `py2cpp::util::list::…` |
| `tuple` / `delegate` / `refcount` | 全局或特殊模块，见 `module_namespace.MODULES_WITHOUT_CPP_NAMESPACE` |
| `protocol_traits.h` | **全局** include；勿放进 `namespace py2cpp { #include … }`（会把 `std` 拉进 `py2cpp::std`） |
| `py2cpp.h` 聚合 | `src/codegen/umbrella_gen.py`；改 include 顺序必全量重编 `build_all.bat` |

**失败征象**：`py2cpp::text` 只有部分符号、`py2cpp::std::pair`、`C2065: Args`（`__mod__` 缺 template 行）、`PyTuple` 歧义、`PyRange` 找不到（`io` 空 namespace 块 + `using namespace py2cpp` 误绑）。

---

## 6. 完整 PR 级检查清单

复制并逐项打勾：

```text
[ ] 新功能/语义变更：已与用户对齐「理解 + 疑问」，获明确同意后再实现
[ ] 实现后已自行对照编码规范与相邻模块（见「实现后须自行对照规范自检」最小自检表）
[ ] 只改源树（py2cpp/、test/、docs/），未手改 generated/
[ ] 若动标准库或 runtime 布局：已运行
      python main.py py2cpp\__init__.py -o generated --no-main
[ ] 已为行为添加/更新 test/**/test_*.py（unittest 结构正确）
[ ] 已在 Windows 上编译（build_all.bat 或目标 test 的 -c --compiler cl）
[ ] 已运行对应 .exe，失败数为 0
[ ] 若动 @protocol：已考虑 build_protocol.bat
[ ] 若动负向用例：已考虑 build_fail.bat
[ ] 文档已同步（参考手册 / 编码规范），若对外行为变化
[ ] 未引入 range_shim、未提交 generated/（除非用户明确要求）
```

---

## 7. 常见错误速查

| 现象 | 处理 |
|------|------|
| exe 崩溃无输出 / `0xC0000409` / 难定位 | **崩溃难查先用 --debug**：`build.bat … --debug`，`exe 2> dbg.log`，看最后一条 `[py2cpp]`；见上文三节强调 |
| `cl` 找不到 | `build_*.bat` 或 vcvars64；勿假装编译通过 |
| 翻译成功但用的是旧 exe | 必须重新 `cl` 链接；看 exe 时间戳 |
| `翻译失败: NotImplementedError` | 查参考手册 §6–8 是否未实现；加 visit/ pass |
| LNK2005 重复符号 | 勿同时链 `py2cpp.cpp` 与完整 `py2cpp.h` |
| `py_open` / `format` 未解析 | 确认 `io.inl`、`py2cpp.h` 含 `operators.inl` |
| `DictKey_check` / traits 未定义 | `dict`/`str` 依赖 `protocol_traits.h`，勿只 include 被拆空的 `protocols.h` |
| `PyRange` 找不到 | 确认已 include 包根 `py2cpp.h`；用户代码用 `(::py2cpp::PyRange)(n)`；勿依赖未验证的 namespace 尾 shim |
| `PyTuple` / `Args` 编译错 | `protocol_traits` 中 `__mod__` 前须有 `template<typename... Args>`；`PyTuple` 在全局，勿误写 `py2cpp::PyTuple` |
| 头文件循环 include | `str.h`↔`list.h`：按参考手册 §8.5 拆 `protocol_traits`、调整 include |
| 测试写 `Cls(1)` / `Cls(src)` | 用 `new(...)` / `dst: Cls = src`（编码规范 §2） |
| `assertTrue(f)` 文件对象 | 勿 `f.__bool__()`；用 `assertTrue`/`assertFalse` |
| MSVC `C2059` 在 `.add` / `isdisjoint()` | 变量名勿用 `far`/`near`（Win 宏）；`isascii` 调用前需 `#undef`（见 `py2cpp.h` 尾部） |
| MSVC **C4716** ``T0 fn(…): 必须返回一个值`` | 旧版误推返回 ``T0``（已删 fallback）。无 ``return expr`` → ``void``；有 ``return expr`` → ``decltype``。见 [参考手册 §5.3.1 **4）**](../../../docs/参考手册.md#531-缺少注解时的-c-类型策略) |
| 规范写法与 MSVC/译器冲突（如 `self.parent`、`.suffix`） | **解决冲突**，勿改业务为绕行 API；见上文「冲突须根治，勿绕行」 |
| 手写 `while` 扫路径/扩展名、重复实现 `splitext` 等 | 复用 `str` / `io.file.path`；见上文「勿重复造轮子，严格按编码规范」 |
| `s[0:k]`、`len(s)==0` / `len(s)>0` | 优先 `s[:k]`、`not s` / `if s`（编码规范 §布尔、§栈子区间） |
| 未对齐就开写译器/标准库/大范围测试 | **先问清再实现**：提交「理解 + 疑问」并等用户确认；见上文三节强调 |
| 只编译通过、写法不合规范 | **实现后须自行对照规范自检**：过最小自检表后再声称完成 |
| `x in (a,b,c)` / `(a,b,c)[i]` | **不支持元组字面量作容器**；用 `in {…}`、`list[…][i]`、`match` 等，见 [reference §8.3](./reference.md#83-pythonic-字面量--内联-c查阅表) |
| `{a:x,b:y}[k]` / `{…}.get(k,z)` | ✅ 译期内联（常量键三目/IIFE；非常量键/`**` → 临时 `PyDict`），见 [reference §8.3.3.1](./reference.md#8331-内联映射字面量查表ax-ykb-ygetk-z) |
| `[a,b,c][i]` / `x in [a,b,c]` / `"abc"[i]` / `x in "abc"` | ✅ 连续下标优先 `list`；`literal_sequence_lookup`（`_tbl[]` / `\|\|` / `PyChar`），见 [reference §8.3.2](./reference.md#832-列表--成员--分支非-dict不变) |
| `"abc".find/index/rfind/rindex(sub)` | ✅ 字面量接收者内联（``_h[]`` 循环）；见 reference §8.3.2 |
| MSVC **C4805** ``PyChar`` vs ``PyStr`` 单字符比较 | ``s[i] == '"'` → ``PyChar`` 对 ``PyChar``（``_try_emit_char_scalar_compare``）；``s[i] in '"'` 已用 ``PyChar`` |
| ``__set_*_param_*`` 找不到标识符 | 模块级描述符 helper 须先于调用方生成（``_module_functions_emit_order``）；见 ``test_descriptor_func`` |
| `for i, x in enumerate(seq)` | 可索引容器 → 索引 ``for``；否则 ``enumerate_iterator``；见 reference §8.2 |
| bootstrap 报 ``new() 需类型上下文``（指向 ``py2cpp/__init__.py``） | 类体/静态字段 ``= new()`` 须左侧字段注解；译器用 ``_emit_field_default_initializer``；``@dataclass`` 的 ``= []`` 勿留在 ``field_defaults`` |
| 未注解模板形参 ``node.parent`` | 生成 ``PY2CPP_GETATTR``；注解 ``node: Node`` → ``node.get_parent()``；见参考手册 §7.8 |

---

## 8. 关键路径索引

| 用途 | 路径 |
|------|------|
| CLI | `main.py` |
| 主译器 | `src/translator.py` |
| 类型分析 | `src/analysis/analyzer.py`, `ir.py` |
| 命名空间 | `src/analysis/module_namespace.py` |
| Passes | `src/passes/*.py` |
| 单文件 C++ 模板 | `src/codegen/*_gen.py`、`expand_py2cpp_template.py` |
| AST 生成 | `src/emit/*.py` |
| 标准库 Python | `py2cpp/` |
| 模块列表 | `src/constant/stdlib_discovery.py` → `STDLIB_REL_PATHS`（遍历 `py2cpp/`） |
| 编译 | `src/compile.py` |
| 万能头 | `src/codegen/umbrella_gen.py` → `generated/runtime/py2cpp/minimal.h` |
| 生成输出 | `generated/runtime/`, `generated/test/` |

---

## 9. 命令速查

```bat
python main.py <file.py> -o generated
python main.py <file.py> -o generated -c --compiler cl --exe path\to.exe
python main.py py2cpp\__init__.py -o generated --no-main
build_example.bat
build_all.bat
build_all.bat --debug
build.bat PATTERN [...] [--seq] [--debug]
run.bat PATTERN [...]
demo.bat PATTERN [...]
build_protocol.bat
build_fail.bat
```

**`--debug`**（`src/codegen/debug_cpp.py`）：为函数调用插入 `fprintf(stderr, "[py2cpp] …")` 跟踪，并将 ``__debug__`` 编译为 ``true``。**崩溃难以排查时优先使用**（见上文「崩溃难查先用 --debug」三节强调）；仅调试用，非常态。测试 TU：`build.bat … --debug`；跟踪 runtime 内调用：bootstrap 亦加 `--debug`。

---

## 10. Agent 行为约束

1. **先问清再实现**：见上文三节强调与「需求确认」— 先给出理解与疑问，用户确认且无疑义后再动手；未确认前不写大段实现代码。  
2. **冲突须根治**：写法与编译器/译器/宏冲突时**解决冲突**，**不要**换成不符合规范的绕行写法（见上文三节强调）。  
3. **勿重复造轮子**：**严格按照编码规范**实现；先搜后写、复用已有 `py2cpp` API（见上文三节强调）。  
4. **实现后须自行对照规范自检**：每次新特性或修改后，**主动**过编码规范与最小自检表（见上文三节强调），再 bootstrap / MSVC；禁止只编译不审代码。  
5. **崩溃难查先用 --debug**：exe 异常退出且难以定位时，**优先**按上文三节强调重编 `--debug`、查 stderr 日志最后一行，再改源树；禁止未看 debug 日志就盲目拆函数或手改 `generated/`。  
6. **先读再改**：动 `translator.py` 前读模块头注释与相关 `passes/`；动标准库前读 [编码规范.md](../../../docs/编码规范.md) 与同域参考实现。  
7. **改必编**：至少编译触达的最小 `test_*.py`；标准库改动必须 bootstrap runtime。  
8. **小步提交逻辑**：命名空间 / umbrella 类改动不要与功能改动混在同一 Diff，便于回滚。  
9. **中文回复用户**，引用代码用 ```start:end:path``` 格式。  
10. **不要**未经用户要求 commit、不要恢复 `range_shim`、不要 Over-engineer 新抽象。

更多细节：[reference.md](./reference.md)、[参考手册 §14–15](../../../docs/参考手册.md)、[编码规范](../../../docs/编码规范.md)。
