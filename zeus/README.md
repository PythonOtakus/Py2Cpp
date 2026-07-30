# Zeus Phase 1–2 落地说明

## 布局（对齐 Py2Cpp：`src/` + FFI 叶子）

```text
zeus/
  src/                 # Python 源（译器 project_root）
  ffi/                 # 手写 GLFW/GL 子集 .pyi（经 ffi_layout 旁路）
  test/                # 说明：可执行测例入口在 src/test_*.py
  docs/
  third_party/glfw/
  generated/
  build.bat
  setup_deps.bat
```

平台 / OpenGL 业务为**纯 Python**组合 `ffi.glfw.glfw3` / `ffi.gl.gl`；无 `zeus/templates`、`zeus/native`。

## 依赖

| 依赖 | 获取 |
|------|------|
| Py2Cpp | monorepo `py2cpp/`（`Transform3D` / `Color`） |
| MSVC | `opengl32.lib` |
| GLFW 3.4 WIN64 | `zeus\setup_deps.bat` → `zeus/third_party/glfw/` |

无 PhysX；重力见 `zeus/src/simple_world.py`（`physics/` 为占位包）。

## 构建

```bat
zeus\build.bat
```

## 验收清单

- [x] Python 在 `zeus/src/`；C 叶子为 `zeus/ffi/**/*.pyi` + 纯 Python（无 `zeus/native/` / `zeus/templates/`）
- [x] `zeus/setup_deps.bat` 拉齐 GLFW
- [x] `test_runtime.exe`：对象树 / 组件 / Transform / World / Mesh·Camera / 重力 / 序列化 — 失败数 0
- [x] `test_render.exe`：隐藏 GLFW 窗 + 清屏 + 彩色 cube — 失败数 0

## GL 测例

`Window.create(..., hidden=True)`；需本机 OpenGL 驱动。
