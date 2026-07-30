# Zeus 3D 游戏引擎设计方案

> 状态：方案草案。本文只定义目标、边界、目录、模块与阶段计划；代码实现待确认后再进入 `./zeus`。

Zeus 是一个基于现有 Py2Cpp 能力实现的轻量 3D 游戏引擎。它的第一目标不是复制 Unity / Unreal 的完整体量，而是建立一套“可运行、可编辑、可扩展、可被工具操作”的引擎骨架，并能用它完成类似微信小游戏《跳一跳》的 3D demo。

---

## 1. 目标与边界

### 1.1 总目标

在仓库根目录新增 `./zeus`，实现一个基于 OpenGL 的 3D 游戏引擎雏形，包含：

- 运行时引擎核心：窗口、主循环、场景、实体、组件、资源、输入、时间、日志。
- OpenGL 渲染后端：基础 shader、mesh、material、camera、draw call。
- 编辑器：可视化场景视口、层级树、属性面板、资源面板、控制台、运行控制。
- 插件系统：插件 manifest、生命周期、组件/菜单/工具窗口/命令注册。
- MCP 操作接口：通过命令协议让外部工具/AI 查询和修改工程、场景与编辑器状态。
- 跳一跳 demo：基于 Zeus 开发一个可运行的 3D 小游戏 demo。

### 1.2 第一阶段必须达到的能力

第一阶段以“能开发跳一跳 demo”为验收标准：

- 能创建 3D 场景。
- 能渲染平台方块、玩家棋子、背景和简单光照/颜色。
- 能读取鼠标/键盘输入。
- 能实现蓄力、跳跃、重力、落点判断、分数。
- 能让摄像机跟随玩家前进。
- 能在编辑器里查看场景层级、修改核心参数、启动/停止 demo。
- 能通过命令接口创建实体、修改 Transform、查询场景。

### 1.3 暂不实现

第一阶段不做以下内容：

- PBR、阴影、后处理、骨骼动画、粒子系统。
- 大型物理引擎绑定。
- 多平台完整打包发布。
- 多线程资源热加载。
- 完整蓝图/可视化脚本系统。
- 大规模资产导入管线。
- 网络联机。

这些能力应在架构上预留扩展点，但不进入初版交付。

---

## 2. 设计原则

### 2.1 Py2Cpp 优先

Zeus 的主体逻辑应使用 Py2Cpp 标准写法实现：

- 标准库与引擎逻辑尽量写 Python 子集。
- 原生 C++ 只用于 OpenGL、窗口、平台输入等不可避免的叶子能力。
- 不手改 `generated/`。
- 不绕开 Py2Cpp 编码规范。
- 能复用已有 `py2cpp` 模块时不重复造轮子。

### 2.2 Runtime / Editor 分层

Zeus 分为运行时和编辑器：

- Runtime 是游戏发布时需要的最小集合。
- Editor 是开发工具，依赖 Runtime，但 Runtime 不反向依赖 Editor。
- Demo 使用 Runtime API，可被 Editor 加载和运行。

### 2.3 Native 能力集中

OpenGL / 窗口 / 输入的 native 能力集中在少量模块：

- `zeus/platform`
- `zeus/render/opengl`

其他模块不直接调用 OpenGL API，而是通过 Zeus 抽象层调用。

### 2.4 命令化编辑器

编辑器操作应统一走 command registry：

- UI 点击按钮调用命令。
- MCP 调用同一套命令。
- 插件注册命令。
- 命令可以被记录、撤销、重放。

这样可以避免“编辑器 UI 一套逻辑，MCP 一套逻辑”的分裂。

### 2.5 独立项目化

Zeus 虽然初期放在 Py2Cpp 仓库根目录 `./zeus` 下开发，但目录组织应按未来可独立拆仓设计。

因此 Zeus 内部必须自带：

- `zeus/docs`：Zeus 自身文档，不混入仓库根 `docs`。
- `zeus/templates`：Zeus 自身 C++ / runtime 模板，不混入仓库根 `templates`。
- `zeus/ffi`：Zeus 自身第三方 C/C++ FFI 声明，不混入仓库根 `ffi`。

仓库根 `docs/zeus设计方案.md` 仅作为当前 Py2Cpp 仓库中的总设计文档；真正开始实现后，Zeus 的细化设计、OpenGL 接入说明、插件协议、MCP 协议应迁移或同步到 `zeus/docs/`。

实现时，仓库根目录的 `templates/`、`ffi/` 仍服务于 Py2Cpp 主工程；Zeus 的 OpenGL / GLFW / 编辑器 native 模板和 FFI 声明默认进入 `zeus/templates/` 与 `zeus/ffi/`。只有当能力被明确提升为 Py2Cpp 通用标准库能力时，才考虑迁移到仓库根对应目录。

### 2.6 不重复造轮子

Zeus 不重复实现 Py2Cpp 标准库已经具备的基础能力，尤其是：

- 向量、矩阵、旋转、Transform 数学能力优先复用 `py2cpp.spatial`。
- JSON / 文档序列化优先复用 `py2cpp.serde.json`。
- 路径、文件 IO 优先复用 `py2cpp.io`。
- UI 面板和窗口能力优先复用 `py2cpp.ui`。

Zeus 内部只保留引擎领域对象，例如 `Bounds`、`Ray`、`Mesh`、`Camera`、`Material`；不要在 `zeus` 中重新写 `Vector3`、`Matrix4`、`Quaternion` 这类标准库已有类型。

---

## 3. 目录结构规划

初步目录如下：

```text
zeus/
  __init__.py
  app.py
  engine.py
  project.py
  log.py

  core/
    object.py
    event.py
    command.py
    uuid.py

  geometry/
    bounds.py
    ray.py
    plane.py

  scene/
    scene.py
    entity.py
    component.py
    transform.py
    prefab.py

  render/
    renderer.py
    camera.py
    mesh.py
    material.py
    color.py
    light.py
    opengl/
      gl_context.py
      gl_device.py
      gl_shader.py
      gl_buffer.py
      gl_texture.py
      gl_mesh.py

  platform/
    window.py
    input.py
    file_dialog.py
    timer.py

  asset/
    asset_db.py
    importer.py
    mesh_importer.py
    material_importer.py
    scene_io.py

  physics/
    collider.py
    rigidbody.py
    simple_world.py

  editor/
    editor_app.py
    layout.py
    scene_view.py
    hierarchy.py
    inspector.py
    assets_panel.py
    console.py
    toolbar.py
    gizmo.py

  plugin/
    manifest.py
    plugin.py
    registry.py
    loader.py

  mcp/
    schema.py
    server.py
    tools.py

  ffi/
    glfw/
      glfw3.pyi
    opengl/
      gl.pyi

  templates/
    platform/
      window.h
      window.inl
    render/
      opengl.h
      opengl.inl

  docs/
    README.md
    architecture.md
    opengl-backend.md
    editor.md
    plugin.md
    mcp.md

  demos/
    jump/
      main.py
      scene.py
      gameplay.py
      components.py
      assets/
```

说明：

- `zeus/core`：引擎基础设施。
- `zeus/geometry`：引擎领域几何类型，例如 `Bounds`、`Ray`、`Plane`；不重复实现向量/矩阵。
- `zeus/scene`：实体组件系统。
- `zeus/render`：渲染抽象。
- `zeus/render/opengl`：OpenGL 后端。
- `zeus/platform`：窗口、输入、时间等平台层。
- `zeus/editor`：编辑器。
- `zeus/plugin`：插件机制。
- `zeus/mcp`：MCP/命令桥接。
- `zeus/ffi`：Zeus 自身 FFI 声明，未来可随 Zeus 独立迁移。
- `zeus/templates`：Zeus 自身 C++ 模板，未来可随 Zeus 独立迁移。
- `zeus/docs`：Zeus 项目内部文档。
- `zeus/demos/jump`：跳一跳 demo。

---

## 4. 引擎核心设计

### 4.1 Engine

`Engine` 是运行时入口，负责：

- 初始化平台层。
- 初始化渲染后端。
- 加载工程与场景。
- 执行主循环。
- 调度输入、更新、物理、渲染。
- 管理运行状态：`stopped` / `playing` / `paused`。

核心接口草案：

```python
class Engine:
  def init(self, project: Project) -> None: ...
  def load_scene(self, scene: Scene) -> None: ...
  def start(self) -> None: ...
  def stop(self) -> None: ...
  def tick(self) -> None: ...
```

### 4.2 Scene

`Scene` 保存实体集合与场景级配置：

- 场景名称。
- 根实体列表。
- 当前相机。
- 环境颜色。
- 场景资源引用。

接口草案：

```python
class Scene:
  name: str
  entities: list[Entity]

  def create_entity(self, name: str = "Entity") -> Entity: ...
  def destroy_entity(self, e: Entity) -> None: ...
  def find(self, name: str) -> Entity: ...
  def update(self, dt: float) -> None: ...
```

### 4.3 Entity / Component

Zeus 初期采用简单 Entity + Component，而不是复杂 ECS。

每个 Entity：

- 有唯一 id。
- 有名字。
- 有 Transform。
- 有父子关系。
- 持有组件列表。

每个 Component：

- 绑定一个 Entity。
- 可启用/禁用。
- 支持生命周期：`on_create`、`on_update`、`on_destroy`。

接口草案：

```python
class Entity:
  id: str
  name: str
  transform: Transform
  components: list[Component]

  def add_component[T: Component](self, comp: T) -> T: ...
  def get_component[T: Component](self) -> T: ...
```

```python
class Component:
  entity: Entity
  enabled: bool = True

  def on_create(self) -> None: ...
  def on_update(self, dt: float) -> None: ...
  def on_destroy(self) -> None: ...
```

### 4.4 Transform

Transform 是最核心组件，包含：

- local position
- local rotation
- local scale
- parent / children
- world matrix

第一阶段可简化：

- rotation 初期可只支持 yaw 或 quaternion。
- 必须支持 `forward`、`up`、`right`。
- 必须支持 parent-child 世界矩阵合成。

### 4.5 Time

`Time` 提供：

- `delta_time`
- `fixed_delta_time`
- `time`
- `frame_count`

第一阶段物理可直接每帧更新，不强制 fixed update。

### 4.6 Input

Input 抽象：

- key down / key up / key held
- mouse position
- mouse button
- pointer drag duration

跳一跳 demo 需要：

- 鼠标按下开始蓄力。
- 鼠标松开触发跳跃。
- 可选键盘空格替代鼠标。

---

## 5. OpenGL 渲染设计

### 5.1 渲染层分层

```text
Renderer API
  └─ OpenGL backend
       ├─ GLContext
       ├─ GLDevice
       ├─ GLShader
       ├─ GLBuffer
       ├─ GLTexture
       └─ GLMesh
```

Runtime 代码应依赖 `Renderer` 抽象，不直接依赖 OpenGL。

### 5.2 Renderer

Renderer 负责：

- 设置 viewport。
- 清屏。
- 设置 camera。
- 提交 mesh + material。
- 执行 draw。

接口草案：

```python
class Renderer:
  def begin_frame(self) -> None: ...
  def clear(self, color: Color) -> None: ...
  def draw_mesh(self, mesh: Mesh, material: Material, transform: Matrix4) -> None: ...
  def end_frame(self) -> None: ...
```

### 5.3 Mesh

第一阶段 Mesh 支持：

- 顶点位置。
- 顶点颜色。
- 顶点 uv 可选。
- index buffer。

内置 mesh：

- cube
- plane
- capsule 或 sphere 近似体

跳一跳 demo 只需要：

- 平台 cube。
- 玩家棋子可以先用 cube / capsule 近似。

### 5.4 Material

第一阶段 Material 简化为：

- shader 引用。
- base color。
- texture 可选。

不做复杂材质图。

### 5.5 Camera

Camera 支持：

- perspective projection。
- orthographic 可后续。
- view matrix。
- 跟随目标。

跳一跳 demo 使用透视相机，斜俯视角跟随玩家。

### 5.6 OpenGL native 边界

OpenGL 后端中的不可移植操作走 native：

- 创建窗口。
- 创建 GL context。
- 加载 OpenGL 函数。
- 编译 shader。
- 创建 buffer / vertex array / texture。
- draw call。

候选底层方案：

1. GLFW + OpenGL
   - 优点：跨平台、成熟。
   - 缺点：需要第三方库。
2. Windows 原生 WGL + OpenGL
   - 优点：少依赖。
   - 缺点：跨平台差，窗口/输入代码更多。

第一阶段建议优先 GLFW + OpenGL。如果仓库不希望引入第三方二进制，则先做 Windows WGL 最小后端。

---

## 6. 编辑器设计

### 6.1 EditorApp

EditorApp 是 Zeus 编辑器入口：

- 创建编辑器窗口。
- 初始化 Engine。
- 加载 Project。
- 管理编辑器状态。
- 驱动 UI 面板。

### 6.2 编辑器布局

MVP 布局：

```text
+---------------------------------------------------------+
| Toolbar: [Play] [Pause] [Stop] [Save]                   |
+-------------------+-----------------------+-------------+
| Hierarchy         | Scene View            | Inspector   |
|                   | OpenGL viewport       |             |
+-------------------+-----------------------+-------------+
| Assets            | Console                             |
+---------------------------------------------------------+
```

### 6.3 Scene View

Scene View 负责：

- 显示 OpenGL 3D 视口。
- 显示相机视角。
- 支持选择实体。
- 支持基础 gizmo。

第一阶段 Gizmo：

- 显示选中实体位置。
- 支持通过 Inspector 修改数值。
- 视口内拖拽可以后续再做。

### 6.4 Hierarchy

Hierarchy 显示：

- 当前 Scene 的实体树。
- 选中实体。
- 创建 / 删除实体。
- 重命名实体。

### 6.5 Inspector

Inspector 显示：

- Entity 名称。
- Transform。
- 组件列表。
- 组件字段。

第一阶段字段类型：

- int
- float
- bool
- str
- Vector3
- Color

### 6.6 Assets

Assets 面板显示项目资源：

- scene
- material
- mesh
- texture
- plugin

第一阶段可以先做文件树 + 选中预览，不做复杂导入器。

### 6.7 Console

Console 显示：

- log
- warning
- error
- command 输出
- MCP 调用结果

---

## 7. 插件系统

### 7.1 插件目录

建议插件目录：

```text
zeus_plugins/
  my_plugin/
    plugin.json
    main.py
```

也可以允许工程内插件：

```text
project/
  plugins/
    my_plugin/
```

### 7.2 Manifest

`plugin.json` 草案：

```json
{
  "name": "jump_tools",
  "display_name": "Jump Tools",
  "version": "0.1.0",
  "entry": "main.py",
  "enabled": true,
  "dependencies": []
}
```

### 7.3 插件生命周期

```python
class ZeusPlugin:
  def on_load(self, ctx: PluginContext) -> None: ...
  def on_unload(self, ctx: PluginContext) -> None: ...
  def on_editor_start(self, ctx: PluginContext) -> None: ...
  def on_play_start(self, ctx: PluginContext) -> None: ...
  def on_play_stop(self, ctx: PluginContext) -> None: ...
  def on_update(self, ctx: PluginContext, dt: float) -> None: ...
```

### 7.4 插件可注册内容

插件可以注册：

- Component 类型。
- Editor 菜单项。
- Editor 面板。
- Asset importer。
- Command。
- MCP tool。

第一阶段优先支持：

- 注册命令。
- 注册菜单项。
- 注册组件类型。

---

## 8. MCP 操作设计

### 8.1 MCP 的定位

Zeus 的 MCP 能力不是另写一套编辑器逻辑，而是对 `CommandRegistry` 的外部暴露。

也就是说：

- UI 调用 command。
- 插件调用 command。
- MCP tool 调用 command。

### 8.2 Command Registry

命令结构：

```python
class Command:
  name: str
  description: str

  def execute(self, ctx: CommandContext, args: dict[str, str]) -> CommandResult: ...
```

命令结果：

```python
class CommandResult:
  ok: bool
  message: str
  data: str
```

第一阶段可以先使用 `dict[str, str]` / JSON 字符串，避免复杂泛型 schema。

### 8.3 初始命令清单

工程命令：

- `project.open`
- `project.save`
- `project.info`

场景命令：

- `scene.new`
- `scene.open`
- `scene.save`
- `scene.list_entities`
- `scene.create_entity`
- `scene.delete_entity`
- `scene.find_entity`

实体命令：

- `entity.rename`
- `entity.set_position`
- `entity.set_rotation`
- `entity.set_scale`
- `entity.add_component`
- `entity.remove_component`
- `entity.get_components`

运行命令：

- `play.start`
- `play.pause`
- `play.stop`
- `play.step`

编辑器命令：

- `editor.select_entity`
- `editor.focus_entity`
- `editor.log`

### 8.4 MCP server 初步形态

第一阶段可以先做内部 JSON command bridge：

```text
stdin/stdout 或 local socket
  request:  {"cmd": "scene.create_entity", "args": {"name": "Cube"}}
  response: {"ok": true, "message": "...", "data": "..."}
```

之后再包装成正式 MCP server。

---

## 9. 跳一跳 demo 设计

### 9.1 游戏对象

实体：

- `Player`
  - Transform
  - MeshRenderer
  - JumpController
  - SimpleCollider
- `Platform`
  - Transform
  - MeshRenderer
  - SimpleCollider
- `Camera`
  - Camera
  - FollowTarget
- `GameManager`
  - JumpGameManager

### 9.2 Gameplay

规则：

- 玩家站在当前平台。
- 按住鼠标蓄力。
- 松开后按蓄力时间计算水平速度与竖直速度。
- 玩家沿抛物线跳向下一个平台。
- 落在平台上得分并生成下一个平台。
- 落空则游戏结束。

### 9.3 Physics 简化

第一阶段不做完整物理引擎：

- 玩家状态机：
  - idle
  - charging
  - jumping
  - failed
- jumping 状态手动积分：
  - velocity.y += gravity * dt
  - position += velocity * dt
- 碰撞检测：
  - AABB 或圆形落点检测。
  - 只检测玩家落脚点是否在平台范围内。

### 9.4 Camera

摄像机：

- 斜俯视。
- 跟随玩家和当前平台中心。
- 玩家成功落地后平滑移动到新中心。

### 9.5 Demo 验收

Demo 完成标准：

- 能从 Zeus Editor 点击 Play 运行。
- 能蓄力跳跃。
- 能连续生成平台。
- 能统计分数。
- 能判断失败。
- 能通过 Inspector 调整：
  - jump power
  - gravity
  - platform distance range
  - platform size range
- 能通过 MCP 命令重置游戏、查询分数、修改玩家位置。

---

## 10. 序列化与资源

### 10.1 Scene 文件

场景可先用 JSON：

```json
{
  "name": "JumpDemo",
  "entities": [
    {
      "id": "entity-1",
      "name": "Player",
      "transform": {
        "position": [0, 1, 0],
        "rotation": [0, 0, 0, 1],
        "scale": [1, 1, 1]
      },
      "components": [
        {"type": "MeshRenderer", "mesh": "cube", "material": "player"},
        {"type": "JumpController", "jump_power": 8.0}
      ]
    }
  ]
}
```

### 10.2 Asset DB

Asset DB 管理：

- asset path
- asset id
- asset type
- importer
- loaded runtime object

第一阶段可以只做 JSON 资源索引。

---

## 11. 与现有 Py2Cpp 模块的关系

可优先复用：

- `py2cpp.spatial`：向量、矩阵、transform 数学能力。
- `py2cpp.ui`：编辑器面板与窗口基础能力。
- `py2cpp.serde.json`：场景、项目、插件 manifest 序列化。
- `py2cpp.io`：资源文件与路径。
- `py2cpp.concur.thread` / `py2cpp.concur.task`：后续可用于后台任务，但第一阶段不强制。

若现有能力不足，应优先补基础设施，而不是在 Zeus 内部堆重复 helper。

---

## 12. 阶段计划

### Phase 0：文档与原型确认

- 完成本设计文档。
- 确认 OpenGL 后端方案：GLFW 还是 Windows WGL。
- 确认 Editor UI 基于现有 `py2cpp.ui` 的集成方式。
- 确认 MCP 第一阶段是 JSON bridge 还是正式 MCP server。

交付：

- `docs/zeus设计方案.md`

### Phase 1：Zeus Runtime 骨架

新增：

- `zeus/__init__.py`
- `zeus/engine.py`
- `zeus/project.py`
- `zeus/core/*`
- `zeus/scene/*`
- `zeus/geometry/*`

能力：

- 创建场景。
- 创建实体。
- 添加组件。
- 主循环 tick。
- 日志。
- JSON 场景保存/加载初版。

验证：

- 能运行无渲染的 scene update 测试。

### Phase 2：OpenGL 最小渲染

新增：

- `zeus/platform/window.py`
- `zeus/render/*`
- `zeus/render/opengl/*`

能力：

- 创建窗口。
- 清屏。
- 渲染一个 cube。
- Camera MVP。
- MeshRenderer 组件。

验证：

- 运行 sample scene，显示 3D cube。

### Phase 3：Editor MVP

新增：

- `zeus/editor/*`

能力：

- 编辑器窗口。
- Toolbar。
- Hierarchy。
- Inspector。
- Console。
- Scene View。
- Play / Stop。

验证：

- 能打开 demo scene。
- 能选实体。
- 能修改 Transform。
- 能点击 Play 运行。

### Phase 4：插件与命令系统

新增：

- `zeus/plugin/*`
- `zeus/core/command.py`

能力：

- 加载 plugin manifest。
- 注册命令。
- 注册菜单项。
- 注册组件类型。

验证：

- 示例插件能创建菜单项。
- 示例插件能注册 `jump.reset` 命令。

### Phase 5：MCP / 外部操作

新增：

- `zeus/mcp/*`

能力：

- JSON command bridge。
- 基础 MCP tools 映射。
- 查询/修改场景。
- 控制 Play / Stop。

验证：

- 外部命令创建实体。
- 外部命令修改 Transform。
- 外部命令启动/停止 demo。

### Phase 6：跳一跳 Demo

新增：

- `zeus/demos/jump/*`

能力：

- 平台生成。
- 玩家跳跃。
- 分数。
- 失败判定。
- 摄像机跟随。
- 可编辑参数。

验证：

- Editor 中打开并运行。
- 可玩一局完整流程。

---

## 13. 技术风险

### 13.1 OpenGL / 窗口依赖

风险：

- Py2Cpp 当前未必已有窗口 + OpenGL context 的完整 FFI。
- GLFW 引入方式需要确定。

应对：

- 优先做最小 native backend。
- native API 收敛在 `zeus/platform` 和 `zeus/render/opengl`。
- 不让 OpenGL 调用扩散到游戏逻辑。

### 13.2 编辑器视口嵌入

风险：

- 现有 `py2cpp.ui` 是否支持嵌入 OpenGL viewport 需要验证。

应对：

- 第一阶段允许独立 OpenGL 窗口 + Editor 控制面板。
- 后续再做嵌入式 Scene View。

### 13.3 插件动态加载

风险：

- Py2Cpp 编译型环境下动态加载 Python 插件并不等同 CPython import。

应对：

- 第一阶段插件可以是编译期注册。
- manifest 用于发现和启用。
- 后续再探索动态库或脚本解释层。

### 13.4 MCP 与运行时状态一致性

风险：

- MCP 命令可能在 Play 状态修改场景，产生状态冲突。

应对：

- CommandContext 标记当前模式：edit / play / paused。
- 每个命令声明允许模式。
- 不允许的命令返回错误。

---

## 14. 验收清单

### Runtime

- [ ] 能创建 Engine。
- [ ] 能创建 Scene。
- [ ] 能创建 Entity。
- [ ] 能添加 Component。
- [ ] 能 update。
- [ ] 能保存/加载 Scene。

### Render

- [ ] 能创建窗口。
- [ ] 能创建 OpenGL context。
- [ ] 能清屏。
- [ ] 能编译 shader。
- [ ] 能渲染 cube。
- [ ] 能使用 Camera。

### Editor

- [ ] 有 Toolbar。
- [ ] 有 Hierarchy。
- [ ] 有 Inspector。
- [ ] 有 Console。
- [ ] 有 Scene View 或独立 viewport。
- [ ] 能 Play / Stop。

### Plugin

- [ ] 能读取 manifest。
- [ ] 能注册命令。
- [ ] 能注册菜单项。
- [ ] 能注册组件类型。

### MCP

- [ ] 能列出命令。
- [ ] 能创建实体。
- [ ] 能修改 Transform。
- [ ] 能查询场景树。
- [ ] 能启动/停止 Play。

### Jump Demo

- [ ] 能蓄力。
- [ ] 能跳跃。
- [ ] 能落点判定。
- [ ] 能生成平台。
- [ ] 能计分。
- [ ] 能失败重置。
- [ ] 能通过 Editor 修改参数。
- [ ] 能通过 MCP 查询/控制。

---

## 15. 下一步建议

建议下一步按以下顺序推进：

1. 确认 OpenGL 后端选择：GLFW 或 Windows WGL。
2. 创建 `./zeus` 目录和最小 Runtime 骨架。
3. 加 `test/zeus/test_scene.py`，先验证无渲染场景逻辑。
4. 接入最小窗口 + OpenGL 清屏。
5. 渲染 cube。
6. 做 Editor MVP。
7. 做 command registry。
8. 做跳一跳 demo。

只有当 Runtime + Render + Editor 三条主线都能最小跑通后，再扩展插件和 MCP 的完整能力。
