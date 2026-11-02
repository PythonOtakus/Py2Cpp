# Zeus 本地 FFI

`zeus/engine/ffi/**/*.pyi`（及 `.paw`）为 **生成物**（`AUTO-GENERATED`），勿手改。模块级符号一律 `Pyi_*`（与仓库根 `ffi/` 相同约定，见 [docs/c-ffi-pyi.md](../../../paw/docs/c-ffi-pyi.md)）。

| 模块 | 源头 | 入口 |
|------|------|------|
| `ffi/glfw/glfw3` | `zeus/engine/thirdparty/glfw/include/GLFW/glfw3.h` | `zeus\tools\ffi.bat`（`GLFW_INCLUDE_NONE`） |
| `ffi/gl/gl` | Windows Kits `um/gl/GL.h` | `zeus\tools\ffi.bat`（裸名 `gl`） |

```bat
zeus\ffi.bat
zeus\ffi.bat --check
zeus\ffi.bat glfw
zeus\ffi.bat gl
```

译器经 `ffi_layout` 的 `zeus/engine/ffi` 旁路解析（与仓库根 `ffi/` 同 `module_path`）。Glue **allowlist** 仅业务实际调用的符号（见 `host/constant/ffi_layout.py`）。

业务在 `zeus/engine/source/zeus/runtime/platform` / `render/opengl` 用**显式 import**（如 `Pyi_glfwCreateWindow`）纯 Python 组合；禁止 `from ffi… import *`。不做 `glfw3native.h`。
