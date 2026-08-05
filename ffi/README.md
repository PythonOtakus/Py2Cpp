# ffi/

Py2Cpp FFI 声明（`.pyi`）统一输出目录。由根目录 `ffi.bat`（→ `scripts/gen_c_ffi.py` / `src.tools.c_ffi_pyi`）生成，见 [docs/c-ffi-pyi.md](../docs/c-ffi-pyi.md)。

| 源头文件 | `.pyi` 路径 |
|----------|-------------|
| `third_party/sqlite/sqlite3.h` | `ffi/sqlite/sqlite3.pyi`（去掉 `third_party/`） |
| 仓库内其它 `path/to/foo.h` | `ffi/path/to/foo.pyi` |
| 系统 / SDK 头（如 `…/um/windows.h`） | `ffi/windows.pyi`（仅文件名 stem） |

**约定**：模块级符号一律 `Pyi_*`（`@native_name` = C 名）；结构体/枚举 → `using Pyi_X = ::X`；有 C 注释时带 PEP 257 docstring。

**勿手改** `AUTO-GENERATED` 文件；升级第三方头后重跑生成器。

用法见 [docs/c-ffi-pyi.md](../docs/c-ffi-pyi.md)：显式 `from ffi… import Pyi_…`（禁止 `import *`）；译器写出 `generated/runtime/ffi/`（C++ `ffi::…`）；sqlite 叶子已走自动 glue，UI 等模板勿整批删除。
