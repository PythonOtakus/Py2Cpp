# Zeus 本地 FFI

手写子集 `.pyi`（`glfw/glfw3.pyi`、`gl/gl.pyi`），经译器 `ffi_layout` 的 `zeus/ffi` 旁路解析。

业务在 `zeus/src/platform` / `render/opengl` 用**纯 Python**组合；无 `zeus/templates` / `zeus/native`。
