# C / CRT / 平台 SDK → Py2Cpp `.pyi`（FFI 声明）

状态：**生成器 + 译器识别 + sqlite glue 试点已通**；**A+B 定案**（第三方/平台 SDK **+** CRT/libc 一律经 `ffi/`；C++ STL 除外）。`.pyi` **一律自动生成，禁止手写**。

## 1. 目标

从 C/C++ **公开头文件**（第三方库、Windows SDK、UCRT）自动生成符合 Py2Cpp 编码习惯的 **`.pyi` 声明面**：

- 扩展名统一 **`.pyi`**；**勿手改** `AUTO-GENERATED` 文件，升级头后重跑 `ffi.bat`
- 函数仍标 **`@native`**（体为 `...`）
- **包含头文件解析到的全部公开 API**（函数 + 可求值常量宏 + 不透明句柄 typedef）
- 与 Python 关键字冲突时：Python 侧别名 + **`@native_name("原 C 标识符")`**
- **不透明/完整结构体 / 枚举**：模块级 **`PyiX`** 的 `@native` 类（`@native_name` = C 标签/路径）；指针 **`Pointer[PyiX]`**；typedef **`type PyiB = PyiA`**；未知/匿名字段 **`None  # C: …`**；字段规范 **camelCase**（与 C 名不同时 `T @native_name("c_field")`）
- **常量** `PyiSqliteOk: int @native_name("SQLITE_OK") = 0`；**函数** `def pyiSqlite3Open(...`
- 有 C 注释时写入 **PEP 257 docstring**（§7.1）；无注释则仅 `...`
- 构建机允许依赖 **libclang**（`clang` Python 包 + 自带/系统 `libclang`）

**范围（A+B）**：

| 纳入 FFI | 不纳入（可继续 `#include`） |
|----------|------------------------------|
| 第三方库（sqlite、…） | C++ STL / 语言设施（`<type_traits>`、`<utility>`、`<atomic>`、`<thread>`、`<chrono>`…） |
| Windows SDK（`um`/`shared`/`winrt`） | — |
| UCRT / CRT（`stdio`/`string`/`math`/…） | — |

**本阶段已做**：`@native`→C glue（sqlite）；模板 A/B include 全量迁 `"ffi/…"`（T26）；默认输出 `ffi/windows/<stem>.pyi`、`ffi/crt/<stem>.pyi`。**仍未做**：Win32/CRT 业务模板全量改调 `ffi::`、全量 glue allowlist、删光 UI 组合模板。

## 2. 分层（与业务 API 分离）

```text
third_party/foo/foo.h  |  …/um/windows.h  |  …/ucrt/stdio.h
        │  ffi.bat → scripts/gen_c_ffi.py → src.tools.c_ffi_pyi（libclang）
        ▼
ffi/foo/foo.pyi  |  ffi/windows/__init__.pyi  |  ffi/crt/stdio.pyi
        │  译器 → generated/runtime/ffi/…（glue #include <c_header>）
        ▼
py2cpp/.../*.py + templates（组合层；禁止直导 A/B 头）
```

| 层 | 内容 | 谁维护 |
|----|------|--------|
| **FFI `.pyi`** | C API 1:1 声明、`@native`、句柄别名、常量 | **仅生成器**（禁止手写） |
| **FFI glue** | `inline` 转发；唯一允许 `#include <c_header>` 处 | 译器 `ffi_glue_emit` |
| **业务 `.py` / 模板组合** | DB-API / UI / 异常映射；只调 `ffi::…` | 手写 |

## 3. 工具

| 路径 | 职责 |
|------|------|
| `src/tools/c_ffi_pyi.py` | **核心**：libclang 解析、类型映射、渲染、`generate_pyi` / `run_checks` |
| `scripts/gen_c_ffi.py` | **CLI**：`argparse` 后调用 `src.tools.c_ffi_pyi.generate_pyi` |
| `ffi.bat` | **根目录薄封装**：`ffi <header> [options]` → `python scripts\gen_c_ffi.py …` |
| `zeus\ffi.bat` | Zeus：重生成 `zeus/ffi/glfw/glfw3.pyi`、`zeus/ffi/gl/gl.pyi` |

```bat
ffi third_party\sqlite\sqlite3.h
REM 默认写出 ffi\sqlite\sqlite3.pyi（去掉 third_party/ 前缀）

ffi windows
REM 或 windows.h / 完整 SDK 路径；默认写出 ffi\windows\windows.pyi

ffi stdio
ffi string
REM UCRT 裸名；默认写出 ffi\crt\stdio.pyi、ffi\crt\string.pyi

ffi gl --out zeus\ffi\gl\gl.pyi --no-include-deps
REM 裸名 gl → Windows Kits um\gl\GL.h（Zeus 推荐用 zeus\ffi.bat）

zeus\ffi.bat
REM 重生成 zeus\ffi\glfw\glfw3.pyi + zeus\ffi\gl\gl.pyi（生成物，勿手改）

ffi third_party\sqlite\sqlite3.h --check
REM --check：与已有 .pyi 比对（忽略 # Generated: 行），用于回归
```

依赖：

```bat
pip install clang libclang
```

（Windows 上 `libclang` wheel 提供 `clang/native/libclang.dll`；生成器会自动 `Config.set_library_file`。也可设 `LIBCLANG_PATH` / 安装 LLVM。）

## 4. 类型映射

| C | `.pyi` |
|---|--------|
| 不完整 `struct X` / `union` | 空 `@native` 类 `PyiX`（类体 `...`）；`@native_name("X")` |
| 完整 `struct X { fields… }` | `@native` 类 `PyiX` + 字段（bitfield 跳过；**匿名**嵌套 union/struct 字段 → `None  # C: unnamed …`） |
| `enum E` / `typedef enum` | 空 `@native` 类 `PyiEEnum`（仅真正 C enum 加 `Enum`；`...  # C enum`）；成员常量 `PyiMem: PyiEEnum @native_name("MEM") = n`；C++ `using PyiEEnum = ::E` |
| `typedef struct A B` / `typedef enum _E E` | `type PyiB = PyiA`（名不同时） |
| 结构体字段 | 规范 camelCase；与 C 名不同时 `field: T @native_name("c_field")` |
| `X*` / `struct X*` | `Pointer[PyiX]` |
| `X**`（出参） | `Pointer[Pointer[PyiX]]` |
| 按值 `struct X` / typedef / enum | `PyiX`（或 typedef 别名） |
| 模块常量 / 函数 | `PyiName` / `def pyiFn…`（`@native_name` = C 名） |
| 未知 / 非法注解 | `None  # C: …`（禁止 clang `unnamed at C:\…` 进注解；能映射则用已有类型） |
| `void*` / `PVOID` / `LPVOID` 等 | `uintptr` |
| 函数指针 / 回调 typedef | `Function[[Args…], Ret]`（`void` 返回 → `None`；见参考手册 `Function`） |
| `const char*` / `char*` | `CStr` |
| `int` / `unsigned` / 定宽整数 | `int` / `uint` / `int64` / `uint64` |
| `float` | `float`（Py2Cpp 32 位） |
| `double` / `long double` | `float64` |
| `float*` / `GLfloat*` 等 | `Pointer[float]` |
| `double*` / `GLdouble*` 等 | `Pointer[float64]` |
| 其它 `T*`（标量/完整类型） | `Pointer[T]`（`T` 已映射） |
| `void` 返回 | `None` |
| C 可变参数 ``f(fixed, ...)`` | 定参 + ``*_``（如 ``def pyiPrintf(_Format: CStr, *_) -> int``；译为 TypeVarTuple 形参包，glue ``::printf(fmt, _...)``） |
| `va_list` 等难映射 | `uintptr` + 行尾注释 |

**注意**：仅真正的 **`void*`**（及 Win32 `PVOID`/`LPVOID`/`LPCVOID` 等）用 `uintptr`；**不要**把函数指针压成 `uintptr`。

**`.pyi` 只声明**：不生成新的 C `struct`；译器发 `using PyiX = ::X`（`@native_name`），签名用 `PyiX` / `PyiX*`。禁止历史 `*_h` 与 `struct ::Tag` 阐述写法。

## 5. 标识符与 `@native_name`

- **导出名**：类型/常量 `Pyi`+Pascal，函数 `pyi`+Pascal；尾缀 `A`/`W` 保留（`StatusW`）；`WIN32`/`DATA` → `Win32`/`Data`（勿 `WIN32`/`DatA`）；仅真正 C `enum` 类型加 `Enum`。
- 函数名、常量名若为 Python 关键字或非 `isIdentifier()`：Python 侧加后缀 `_`（或再加），并写 `@native_name("原名")`。
- 形参名冲突：仅改 Python 形参名（如 `from` → `from_`），**不**对形参使用 `native_name`（位置传参）。
- C 名可直接作 Python 标识符时：可省略 `@native_name`（生成器对**全部**函数仍写 `@native_name("c_name")`，保证与 C 符号稳定对应，便于日后 glue）。

## 6. 常量宏

仅发射**对象式**、可解析为整数或字符串字面量的 `#define`。

- **sqlite**：仍只收 `SQLITE_*` 前缀（避免 amalgamation 噪声）。
- **其它头（含 Win32 / GLFW / GL）**：收字面量对象宏，跳过空/属性宏、编译器内建前缀（`__`、`_MSC_`…）及 `WINAPI`/`CALLBACK` 等。
- **单标识符别名**（如 `#define GLFW_MOUSE_BUTTON_LEFT GLFW_MOUSE_BUTTON_1`）：多轮解析到数值后写入 `.pyi`（与字面量同形），避免 glue `#undef` 基宏后业务仍依赖 C 侧别名展开。

跳过：

- 空宏 / 属性宏（`SQLITE_API`、`WINAPI`…）
- 函数式宏（`NAME(...)`）
- 无法求值为字面量的表达式（含 `|` 组合等）

## 7. 生成物约定

- 文件头：`# AUTO-GENERATED by src.tools.c_ffi_pyi — DO NOT EDIT`
- 源路径与生成时间注释
- `from py2cpp.builtins import *`
- 段落顺序：`@native` 结构体/枚举类 → `type` typedef 别名 → 常量 → `@native` 函数

### 7.1 C 注释 → Python docstring

有 libclang `raw_comment` / `brief_comment` 时写入 PEP 257 docstring；**无注释则保持原样**（仅 `...` / 字段行）。

| 目标 | 写法 |
|------|------|
| 函数 | `def … -> …:` 下一行为 `"""…"""`，再 `...` |
| 结构体 / 枚举类 | `class PyiX:` 下同类 docstring，再字段或 `...` |
| 译器 / C++ | **不**把 docstring 编进 glue；仅 `.pyi` 可读性 |

转换约定（`doxygen_to_python_docstring`）：

- `@param` / `@return(s)` → Google 小节 `Args:` / `Returns:`
- `@errors` / `@thread_safety` / `@sa` / `@note` 等 → 对应英文小节
- `@ref Name` / `[text](@ref x)` → 剥成纯文本
- `@ingroup` 分类标签丢弃；`"""` 在正文中改成 `'''` 以免破坏三引号

类型映射旁注（`# C: …` / 返回类型行尾注释）与 docstring **分开**，互不替代。

**默认输出根目录 `ffi/`**（与源 `.h` 路径对应，不写回 `third_party/` 旁）；Zeus 用 `--out` / `zeus\ffi.bat` 写到 `zeus/ffi/`：

| 源 | 默认 / Zeus `.pyi` |
|----|-------------|
| `third_party/sqlite/sqlite3.h` | `ffi/sqlite/sqlite3.pyi`（剥掉 `third_party/`） |
| 仓库内 `path/to/foo.h` | `ffi/path/to/foo.pyi` |
| Windows Kits `…/um/windows.h` 等 `um`/`shared`/`winrt` | `ffi/windows/<stem>.pyi`（如 `ffi/windows/__init__.pyi`） |
| Windows Kits `…/ucrt/stdio.h` 等 | `ffi/crt/<stem>.pyi`（如 `ffi/crt/stdio.pyi`） |
| `zeus/.../GLFW/glfw3.h`（`--out`） | `zeus/ffi/glfw/glfw3.pyi` |
| Windows Kits `um/gl/GL.h`（裸名 `gl` + `--out`） | `zeus/ffi/gl/gl.pyi` |

## 8. 验证（本阶段）

```bat
ffi third_party\sqlite\sqlite3.h --check
```

检查项：

- libclang 解析无致命诊断（或仅接受已知告警）
- 函数数量 > 0，且覆盖 `sqlite3_open` / `sqlite3_prepare_v2` / `sqlite3_step` 等
- 输出为合法 UTF-8 文本；抽检含 `@native` 与 `@native_name`
- **不**运行 bootstrap、**不**改 `py2cpp/sql/sqlite.py`

## 9. Windows SDK（`ffi/windows/`）

伞头几乎只有 `#include`，须**传递收集** SDK 树内声明，并带 MSVC 目标 / Kits `-I`。**所有 Win32 / SDK 声明面统一落在 `ffi/windows/`**（按头 stem 分文件；子系统头如 `commctrl.h` → `ffi/windows/commctrl.pyi`）。

| 能力 | 行为 |
|------|------|
| 入口 | `--header windows`（自动找最新 `Windows Kits\…\um\windows.h`）或完整路径 |
| clang 预设 | `--target=x86_64-pc-windows-msvc`、`-fms-extensions`、`WIN32_LEAN_AND_MEAN`、`-I um/shared/ucrt` |
| 收集范围 | `include_deps=True`（默认非 sqlite / 非 UCRT）：主文件 + 位于 SDK/`third_party`/头目录根下的传递 include |
| 常量 | 字面量对象宏（见 §6），非 `SQLITE_` 限定 |
| 校验 | 通用：`funcs≥100`；`windows.h` 另要求 `MessageBoxW` / `CreateWindowExW` / `GetMessageW` 至少命中其一 |
| 默认输出 | `ffi/windows/__init__.pyi`（module_path `ffi/windows`） |

```bat
ffi windows
ffi windows --check
```

**仍须经伞头解析**：单独喂 `winuser.h` / `commctrl.h` 会因缺基类型而 fatal（与 MSVC 用法一致）；需要子系统面时再对可独立解析的头生成到同目录。

sqlite amalgamation：默认 **不**传递收集（仅主文件），常量仍限 `SQLITE_*`；`--check` 仍校验核心符号。

## 9.1 UCRT / CRT（`ffi/crt/`）

| 能力 | 行为 |
|------|------|
| 入口 | 裸名 `stdio` / `string` / `math` / `time` / `stdlib` / … 或完整 `…/ucrt/stdio.h` |
| 默认 | `include_deps=True`（限 `ucrt/` 树）；输出 `ffi/crt/<stem>.pyi` |
| 校验 | `funcs≥5`；按头检查核心符号集合是否命中任一（如 `memcpy`/`printf`/`sin`） |
| glue | `ffi_layout` 已登记头映射；allowlist 按业务调用再扩（勿全量）；**空 allowlist** = 生成头仅 `#include <c_header>`（模板间接拿 C API） |

```bat
ffi stdio
ffi string
ffi math
```

## 10. 命名污染（`ffi/windows/__init__.pyi` 等大面）

**结论**：全量伞头（如约 3k 函数 + 1 万常量）**会**造成命名污染，但**仅在**接入译器且被 star-import / 摊进默认命名空间之后才生效。当前业务代码须**显式 import**，不会自动看见这些符号。

| 层 | 风险 |
|----|------|
| Python | `import *` 盖掉用户 / `py2cpp` 同名符号（短名常量如 `ERROR` 尤甚；长 Win32 函数名相对安全） |
| C++ | FFI 若摊进全局或 `py2cpp::`，与业务符号、以及真正 `#include <windows.h>` 后的宏互相踩 |
| 编译体量 | 全量伞头进万能头会拖垮编译（与命名污染常一起爆） |

**定案（接入译器时须遵守）**：

1. **全量 `.pyi` 是目录，不是默认导入面**；业务与标准库 **禁止** `from ffi.windows import *`（及对其它巨型 FFI 面的 star-import）。
2. **显式 import**：`import ffi.windows as win` 或 `from ffi.windows import pyiCreateWindowExW, PyiWmPaint`（类型 `Pyi…`、函数 `pyi…`、常量 `Pyi…`）。
3. **C++ 命名空间隔离**：落到独立空间（`ffi::windows` / `ffi::crt::stdio` / `ffi::sqlite::sqlite3` 等，**不**挂 `py2cpp::`），**不**进 `minimal.h` 默认路径。
4. **业务零 re-export 全量**：`py2cpp/ui/...` 只拉所需叶子；用户只碰业务 API。
5. **模块级 `Pyi`/`pyi` 前缀**统一隔离；仍依赖命名空间 + 显式 import，勿 star-import。

**一般不推荐**：把全量 `ffi/windows/__init__.pyi` 塞进 runtime umbrella。

可选后续（非阻断）：生成器 `--allowlist` 减体积；或对可独立解析的子系统头生成 `ffi/windows/commctrl.pyi` 等。

## 11. 模板迁移（策略：组合可留，禁止直导 A/B）

**定案**：`templates/**` 与业务 C++ 注入**可保留组合/胶水**，但**禁止**再 `#include` 第三方库或 CRT 头（译期 **T26**）；平台/CRT 经 `#include "ffi/…"`；真实 `#include <c_header>` **仅**出现在生成的 ffi glue（`generated/runtime/ffi/…`）。`stdint.h`/`stdarg.h`/`float.h`/`math.h` 改用 C++ 包装 `<cstdint>`/`<cstdarg>`/`<cfloat>`/`<cmath>`（属允许的 STL，不进 `ffi/`；`math.h`→`<cmath>` 亦避免 `py_types.h`↔`ffi/crt/math.h` 环依赖）。

| 类型 | 例子 | 与 `.pyi` 的关系 |
|------|------|------------------|
| 薄 C 转发 | `+sqlite.inl` 调 `::ffi::sqlite::sqlite3::…`；**已去掉**直导 `<sqlite3.h>` | 异常、`PyStr` 转换、bind 循环继续下沉 Python 组合 |
| 平台 API + 大量胶水 | `+canvas.inl`、`+window.inl`… | include 已迁 `"ffi/windows/…"`；WndProc/双缓冲等组合层分批改调 `ffi::`，**勿一次整文件删模板** |
| CRT 叶子 | `+str.inl`、`util/+memory`；``system/time`` / ``system/environ`` / ``console/native_sys`` / ``io`` / ``io/file`` 已下沉为 Python + ``ffi::`` | include 已迁 `"ffi/crt/…"`；业务调用继续分批改 `ffi::crt::…` |
| 译器基础设施 | `operators.*`、`protocol_traits`、`tuple`、异常 ctor；`<type_traits>` 等 **C++ STL** | **不在** A+B 迁移范围 |

**迁移原则**：

- **已完成**：`templates/**` A/B 直导 → `"ffi/…"` / C++ 包装头；映射表 `src/constant/template_ffi_includes.py`；bootstrap 强制 enqueue 模板所需 ffi 模块。
- **禁止**手写 `.pyi`；**禁止** star-import；**禁止**全量 Win32 进 `minimal.h`。
- 组合语义（消息循环、GDI+ 生命周期）仍可留在模板或 Python，直到有等价组合层。
- GDI+ 为 C++ `namespace`：用 `third_party/windows/gdiplus_pyi_seed.h` 生成声明面；glue 仍 `#include <gdiplus.h>`。

## 12. 译器接入（识别 + glue + sqlite 试点）

| 项 | 行为 |
|----|------|
| Import | `from ffi.sqlite.sqlite3 import …` / `from ffi.windows import …` / `from ffi.crt.stdio import …` |
| 源文件 | 仓库根 `ffi/**/*.pyi`；其次 `zeus/ffi/**/*.pyi`（同 module_path，见 `find_ffi_source_file`） |
| module_path | `ffi/windows`、`ffi/crt/stdio`、`ffi/sqlite/sqlite3` |
| 生成物 | `generated/runtime/ffi/….h` + 有 C 头映射时 `.inl`（`#include "ffi/…"`） |
| C++ 命名空间 | `ffi::…`（**不**挂 `py2cpp::`；路径段 = 命名空间段） |
| 结构体 / 枚举 | `using PyiX = ::X`；签名 `PyiX` / `Pointer[PyiX]`；枚举成员作常量；无 `struct ::Tag` |
| docstring | 仅 `.pyi` 可读性；**不**编进 glue（§7.1） |
| Umbrella | **不**进 `minimal.h` / bootstrap bulk；仅 import 闭包写入 |
| Star-import | **禁止** `from ffi… import *`（strict / 解析期报错，§10） |
| S27 | FFI 模块允许 `from py2cpp.builtins import *`（生成器风格） |
| `@native` glue | `src/emit/ffi_glue_emit.py`：`inline` 转发；`#include <c_header>`；指针/按值直传；白名单 `ffi_glue_allowlist`；Win32 导入库经 `ffi_msvc_comment_libs` 发 `#pragma comment(lib, …)`（如 `shellapi` → `shell32.lib`） |
| sqlite 业务 | `py2cpp/sql/sqlite.py` 用 `Pointer[PyiSqlite3]`；`templates/sql/+sqlite.inl` 调 `::ffi::sqlite::sqlite3::…`（经 ffi 头间接拿到 C API） |

回归：`python -m unittest src.tests.test_ffi_import`；`build.bat sql/test_sqlite`；夹具 `src/tests/_ffi_entry_sqlite.py`。

## 13. 后续（未做）

1. 业务模板全面去掉 CRT/Win32 直导，改调 `ffi::` + 扩 allowlist  
2. sqlite 组合层进一步下沉 Python（缩小 `+sqlite.inl`）  
3. C++ 头（重载/类/模板）进 `.pyi`  
4. Win32 宏函数（如 `MAKEINTRESOURCE`）与宽/窄别名；可选 `--allowlist`  

## 14. 相关文件

| 路径 | 说明 |
|------|------|
| `src/constant/ffi_layout.py` | FFI 路径 / include / C 头映射 / 根目录约定 |
| `src/emit/ffi_glue_emit.py` | `@native` → C 薄转发 `.inl` |
| `src/analysis/import_resolver.py` | `.pyi` 发现与 `ffi.*` 映射 |
| `src/tools/c_ffi_pyi.py` | 生成器核心（**唯一**写 `.pyi` 的途径） |
| `ffi.bat` | 根目录入口（sqlite / windows / CRT 裸名） |
| `zeus\ffi.bat` | Zeus GLFW / OpenGL `.pyi` 生成入口 |
| `scripts/gen_c_ffi.py` | CLI 封装 |
| `third_party/sqlite/sqlite3.h` | 输入（C 源仍在 `third_party/`） |
| `ffi/sqlite/sqlite3.pyi` | sqlite 声明面（生成） |
| `ffi/windows/__init__.pyi` | Win32 伞头声明面（生成） |
| `ffi/crt/*.pyi` | UCRT 声明面（生成） |
| `zeus/ffi/glfw/glfw3.pyi` | GLFW 声明面（`zeus\ffi.bat` 生成） |
| `zeus/ffi/gl/gl.pyi` | OpenGL 兼容配置声明面（`zeus\ffi.bat` 生成） |
| `generated/runtime/ffi/` | 译器按需写出的 `.h` / `.inl`（与 `py2cpp/` 并列） |
| `src/tests/test_ffi_import.py` | 译器单测 |
| `templates/sql/+sqlite.inl` | 组合层（经 ffi，勿直导 `<sqlite3.h>`） |
| `py2cpp/sql/sqlite.py` | 业务 API |
| `docs/编码规范.md` §9.4 | `@native` 原子化 + FFI |
| `docs/sql-orm.md` | SQL/ORM 业务层设计 |
