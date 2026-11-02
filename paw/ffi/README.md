# ffi/

Py2Cpp FFI 声明（`.pyi`）统一输出目录。由根目录 `ffi.bat`（→ `scripts/gen_c_ffi.py` / `src.tools.c_ffi_pyi`）**自动生成**，见 [docs/c-ffi-pyi.md](../docs/c-ffi-pyi.md)。

**禁止手写** `AUTO-GENERATED` 文件；升级第三方/SDK/CRT 头后重跑生成器。

| 源头文件 | `.pyi` 路径 | module_path |
|----------|-------------|-------------|
| `third_party/sqlite/sqlite3.h` | `ffi/sqlite/sqlite3.pyi` | `ffi/sqlite/sqlite3` |
| Windows Kits `um/windows.h` 等 | `ffi/windows/<stem>.pyi` | `ffi/windows/<stem>` |
| Windows Kits `ucrt/stdio.h` 等 | `ffi/crt/<stem>.pyi` | `ffi/crt/<stem>` |
| 仓库内其它 `path/to/foo.h` | `ffi/path/to/foo.pyi` | 对应路径 |

```bat
ffi windows
ffi stdio
ffi string
ffi third_party\sqlite\sqlite3.h
```

**约定**：模块级符号 `Pyi…` / `pyi…`（`@native_name` = C 名）；结构体/枚举 → `using PyiX = ::X`；有 C 注释时带 PEP 257 docstring。

用法见 [docs/c-ffi-pyi.md](../docs/c-ffi-pyi.md)：显式 `from ffi… import …`（禁止 `import *`）；译器写出 `generated/runtime/ffi/`（C++ `ffi::…`）。业务/`templates/**` **禁止**直导第三方或 CRT 头；真实 `#include <c_header>` 仅出现在生成的 ffi glue。C++ STL（`<type_traits>` 等）不在本目录范围。
