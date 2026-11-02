# Zeus

基于 Paw 的轻量 3D 游戏引擎（GLFW + OpenGL）。布局对齐 Unreal：`engine/` + `samples/` + `tools/` + `out/`。

- **总设计**：[docs/zeus-engine.md](docs/zeus-engine.md)
- **构建**：`zeus\build.bat`（runtime / render / editor / commands / jump）
- **编辑器**：`zeus\editor.bat`
- **有窗跳一跳**：`zeus\demo.bat`
- **资产**：场景等用 `.zas`（Zeus Asset）；模型用 `.fbx`（ASCII 子集）

## 布局

```text
zeus/
  README.md
  docs/
  engine/
    source/zeus/          # 译器 project_root = engine/source
      runtime/            # core / platform / render / assets / physics
      editor/
      developer/          # CommandBus 等
      programs/           # editor_main + tests/
    ffi/                  # 生成物：GLFW/GL .pyi（tools\ffi.bat）
    thirdparty/glfw/
  samples/
    jump/
      source/             # jump 包 + jump_demo.py（伴生搜索根）
      content/scenes/
  tools/                  # build / demo / editor / ffi / setup_deps
  out/                    # 译器生成物（对齐 Paw）
  build.bat               # → tools\*.bat 转发
```

平台 / OpenGL 为**纯 Python**组合 `ffi.glfw.glfw3` / `ffi.gl.gl`（符号 `Pyi_*`）；无 `zeus/templates`、`zeus/native`。
重生成 FFI：`zeus\ffi.bat`（或 `zeus\ffi.bat --check`）。

## 依赖

| 依赖 | 获取 |
|------|------|
| Paw | monorepo `paw/lib/paw/`（`Transform3D` / `Color`） |
| MSVC | `opengl32.lib` |
| GLFW 3.4 WIN64 | `zeus\setup_deps.bat` → `zeus/engine/thirdparty/glfw/` |

无 PhysX；重力见 `zeus/engine/source/zeus/runtime/core/simple_world.py`（`physics/` 为占位包）。

## 当前进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 0–2 | 文档、Runtime 骨架、GLFW 清屏 + cube | **已完成**（`build.bat` 全绿） |
| 3 | Editor MVP（一体主窗 Hierarchy/Scene/Inspector/`CommandBus`/`.zas`） | **已完成** |
| 4 | Play 写限制 + `test_commands`（建对象→Mesh→步进） | **必要子集已完成**（不做 Phase 5） |
| 6 | 跳一跳 headless + `.fbx`/`.zas`（`test_jump`） | **可玩闭环已完成** |
| 6+ | 有窗 demo + Inspector `jump_power` + 平移 gizmo | **已完成** |
| 5 / 7 | 插件+MCP / ECS | **暂不做** |

## Phase 1–2 验收

- [x] Python 在 `engine/source/zeus/`；C 叶子为 `engine/ffi/**/*.pyi` + 纯 Python
- [x] `zeus/setup_deps.bat` 拉齐 GLFW
- [x] `test_runtime.exe`：对象树 / 组件 / Transform / World / Mesh·Camera / 重力 / 序列化 — 失败数 0
- [x] `test_render.exe`：隐藏 GLFW 窗 + 清屏 + 彩色 cube — 失败数 0
- [x] `test_editor_smoke.exe`：命令 / `.zas` 往返 / Session / Inspector Apply / 一体窗+Scene View — 失败数 0
- 打开编辑器：`zeus\editor.bat`（加载 `zeus/samples/jump/content/scenes/main.zas`）
- [x] `test_commands.exe`：Play 写限制 + 命令管线 — 失败数 0
- [x] `test_jump.exe`：满蓄力落地得分 + FBX/ZAS 往返 — 失败数 0
- 有窗跳一跳：`zeus\demo.bat`（空格/左键蓄力）

## GL 测例

`Window.create(..., hidden=True)`；需本机 OpenGL 驱动。
