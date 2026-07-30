# Zeus 3D 游戏引擎设计方案

> 状态：**Phase 0–2 已落地**（`zeus\build.bat` 全绿）；本文为总设计与后续阶段计划。入口见仓库 [`zeus/README.md`](../README.md)。

Zeus 是一个基于现有 Py2Cpp 能力实现的轻量 3D 游戏引擎。第一目标不是复制 Unity / Unreal 的完整体量，而是建立一套「可运行、可编辑、可扩展、可被工具操作」的引擎骨架，并用它完成类似微信小游戏《跳一跳》的 3D demo。

风格对标：

- **tggame**：`World` / Task 主循环 / `active`·`visible` / 场景树遍历。
- **UE5**：`GameObject`（对标 Actor）**既可继承写玩法，也可挂组件**；逻辑组件与带位姿的 `Transform`（对标 SceneComponent）由对象拥有。
- **Py2Cpp**：复用 `spatial`、`design.ecs`、`prange`、`@ref`、`span`、`@union`/`match`、`@serializable` 等；**禁止在 Zeus 内重复造轮子**。命名 `snake_case`，不照搬 tggame camelCase / 元类 / Cython。

命名约定（本文定稿）：

| 名称 | 含义 |
|------|------|
| `GameObject` | 世界中的可放置对象（原草案 `GameObject3D`） |
| `Component` | 无独立世界位姿的逻辑组件（对标 `UActorComponent`） |
| `Transform` | Zeus **场景组件**（对标 `USceneComponent`）；**不是**再实现一套数学库 |
| `py2cpp.spatial.Transform3D` | 标准库 TRS/场景图数学；`zeus.Transform` **组合复用**其能力，源码中避免无前缀混用 |

---

## 1. 目标与边界

### 1.1 总目标

在仓库根目录新增 `./zeus`，实现基于 OpenGL 的 3D 引擎雏形：

- 运行时：窗口、Task 主循环、`World`、`GameObject` 树、组件生命周期、资源、输入、时间、日志。
- OpenGL：shader、mesh、material、camera、draw call。
- 编辑器：视口、层级、属性、资源、控制台、运行控制。
- 插件：manifest、生命周期、菜单/面板/命令；可注册 **对象类型与组件类型**。
- MCP：统一命令协议查询/修改工程与场景。
- 跳一跳 demo。

### 1.2 第一阶段必须达到的能力

- 创建 `GameObject` 树；对象可子类化，也可 `add_component`。
- 渲染平台/玩家/背景与简单颜色光照。
- 鼠标/键盘；蓄力跳跃、重力、落点、分数（子类和/或组件 + 简易 FSM）。
- 摄像机跟随。
- 编辑器查看层级、改参数、Play/Stop。
- 命令：创建/查找对象、改 `Transform`、增删组件、查树。

### 1.3 暂不实现

- PBR、阴影、后处理、骨骼、粒子；大型物理引擎；完整打包；资源热加载；蓝图；大规模导入；联机。
- 组件拥有组件（UE 也不鼓励）；ChildActor 式复杂嵌套序列化。
- 强制玩法走完整 ECS（ECS 为可选热路径，见 §2.7）。

---

## 2. 设计原则

### 2.1 Py2Cpp 优先

- 规范 Python：`new` / `Self` / `@dataclass` / `@mixin` / 勿手写 dunder / 无 STL。
- **`@native` 原子化**：仅窗口、GL、shader/buffer/texture、draw、平台输入叶子。
- 不手改 `generated/`；冲突在根因处解决。

### 2.2 Runtime / Editor 分层

Runtime 最小集；Editor 依赖 Runtime，反向禁止；Demo 只依赖 Runtime。

### 2.3 Native 能力集中

`zeus/platform`、`zeus/render/opengl`；其余只走 `Renderer` / `Window` / `Input`。

### 2.4 命令化编辑器

UI / 插件 / MCP 共用 `@union` 命令 + JSON 桥接。

### 2.5 独立项目化

`zeus/docs`（含本文）、`zeus/README.md`、`zeus/ffi` 随 Zeus；无 `zeus/templates` / `zeus/native`（平台与 GL 为纯 Python 组合 FFI）。

### 2.6 不重复造轮子

| 需求 | 复用 |
|------|------|
| 向量 / 矩阵 / 四元数 / TRS 数学与父子合成 | `py2cpp.spatial`（`Transform3D` / `TransformMixin`） |
| 材质色 / 清屏 / 顶点色 | `py2cpp.spatial.color`（`Color` / `ColorMatrix`） |
| 2D AABB / 编辑器矩形 | `py2cpp.spatial.rect`（`Rect`；尺寸属性 `size`） |
| SoA / `@ref` 交集 | `py2cpp.design.ecs`（符号保持 `ECS*`） |
| 并行 | `prange` |
| 序列化 | `py2cpp.serde` |
| IO / UI / 弱引用 | `py2cpp.io` / `ui` / `weak.ref` |

禁止在 Zeus 重写 `Vector3` / `Matrix4` / `Quaternion`。

### 2.7 对象模型（核心定案：UE5 双通道 + ECS 预留）

```text
World（Task：detect → update → draw → refresh）
  └─ GameObject 树（可继承；拥有组件列表）
        ├─ 继承通道：class Player(GameObject): ...
        ├─ 组件通道：add_component(JumpMotor) / MeshComponent / …
        │     ├─ Component          # 逻辑，无独立世界位姿
        │     └─ Transform(Component)  # 场景组件，局部 TRS + 附件树
        │           （数学复用 spatial.Transform3D）
        └─ （预留）热数据 → design.ecs SoA + prange
```

要点：

1. **继承与组件并存**（对标 UE Actor）：专用玩法可子类化；可复用行为做成组件挂到任意 `GameObject`。
2. **仅 `GameObject` 拥有组件**；`Transform` 之间可 `attach`，但**组件不拥有组件**。
3. 每个 `GameObject` 有 **root `Transform`**（对标 RootComponent）；对象世界位姿以 root 为准；子 `GameObject` 仍可用对象树 `attach`。
4. **ECS** 与节点组件不同层：节点组件是面向对象 API；ECS 是可选 SoA 优化，对外不强制。

### 2.8 充分利用 Py2Cpp（清单）

| 特性 | Zeus 用法 |
|------|-----------|
| `spatial.Transform3D` / `@mixin` | `zeus.Transform` 组合复用；勿复制矩阵公式 |
| `spatial.Color` / `ColorMatrix` | 清屏、材质、顶点色；矩阵用 `matrix.apply(color)` |
| `spatial.Rect` | 视口/拾取 AABB、编辑器 2D；勿在 Zeus 重写 |
| `@refcount` / `WeakRef` | 对象/组件图；parent 弱引用 |
| `@boxing` | Mesh 缓冲等 |
| `@copyable` + `@dataclass` | 组件字段、命令载荷、ECS POD |
| `T @ref` | ECS 系统；组件内改共享缓冲 |
| `float[:]` / `span` | 顶点索引 |
| `@union` + `match` | 输入、FSM、命令 |
| `@serializable` | 场景（对象 + 组件列表）、工程、桥接 |
| `select` / `build` | 编辑器路径、测试构造 |
| `prange` | 后期批量；Phase 1 可不启用 |
| `@native` | 仅 platform / opengl 叶子 |

---

## 3. 目录结构规划

```text
zeus/
  __init__.py
  project.py
  log.py

  world.py              # World：Task 主循环
  node.py               # GameNodeMixin：active / visible / tags
  game_object.py        # GameObject（拥有组件 + root Transform）
  component.py          # Component 基类
  transform.py          # Transform(Component)：场景组件（复用 spatial）
  mesh_component.py     # MeshComponent(Transform)
  camera_component.py   # CameraComponent(Transform)
  task.py
  fsm.py
  event.py
  command.py
  time_clock.py

  geometry/
    bounds.py
    ray.py
    plane.py

  render/
    renderer.py
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

  asset/
    asset_db.py
    importer.py
    scene_io.py

  physics/
    simple_world.py

  ecs/
    bridge.py           # 后期可选

  editor/ …
  plugin/ …
  mcp/ …
  ffi/ …
  templates/ …
  docs/ …
  demos/jump/ …
```

说明：

- `zeus/transform.py` 是 **组件类型** `Transform`，内部调用 `py2cpp.spatial`，**不是**第二套数学库。
- 不再使用 `GameObject3D` / `SceneComponent` / `Camera3D` / `GameMesh` 作为主类型名；相机与网格以 **组件**（或对象子类 + 默认组件）表达。

---

## 4. 引擎核心设计

### 4.1 World

- 初始化平台与渲染。
- 根：`render: GameObject`、主相机对象（挂 `CameraComponent`）、可选 `aspect`（UI）。
- Task：`detect` → `update` → `draw` → `refresh`。
- 状态：`stopped` / `playing` / `paused`。

```python
class World:
  def init(self, project: Project): ...
  def clear(self): ...
  def step(self): ...
  def run(self): ...
  def quit(self): ...
  def update(self): ...
  def draw(self): ...
```

### 4.2 GameNodeMixin

`active` / `visible`、`enable`/`disable`、`show`/`hide`、`tags`；`update`/`draw` 递归与开关。

### 4.3 GameObject（对标 AActor）

```text
GameObject = GameNodeMixin + 组件容器 + root Transform
```

- `name`、父子 `GameObject` 树（世界中的对象层级）。
- `components: list[Component]`；`add_component` / `get_component` / `remove_component`。
- **root**：默认创建的 `Transform`；`GameObject` 的 position/rotation/scale 转发到 root（或显式 `self.root`）。
- **继承通道**：`class Player(GameObject)`，可在构造中默认 `add_component(...)`。
- **组件通道**：无子类也可组合行为。
- 所有权：`@refcount` 等策略；owner 反向弱引用，避免环。

```python
class GameObject:
  def add_component[T: Component](self, comp: T) -> T: ...
  def get_component[T: Component](self) -> T | None: ...
  def remove_component[T: Component](self): ...
```

生命周期：对象 `update` 时先调自身 `_update`，再调已启用组件的 `on_update`，再递归子对象；`draw` 类似（可见性）。

### 4.4 Component（对标 UActorComponent）

```python
class Component:
  owner: GameObject
  enabled: bool = True

  def on_create(self): ...
  def on_update(self, dt: float): ...
  def on_destroy(self): ...
```

- 无独立世界坐标；通过 `owner` / `owner.root` 读写位姿。
- 示例：`JumpMotor`、`ScoreBoard`、库存类逻辑。

### 4.5 Transform（对标 USceneComponent；原 SceneComponent）

```text
Transform(Component)  +  局部 TRS / 附件树（能力来自 spatial.Transform3D）
```

- 局部 `position` / `rotation` / `scale`；相对父 `Transform` 合成世界矩阵。
- `attach(child: Transform)` / `detach`；**仅**在同一 `GameObject` 拥有的组件之间（或约定允许跨对象附件时由对象层转发）。
- **禁止** `Transform` 再 `add_component`。
- 实现：优先让 `Transform` **混入或持有** `spatial.Transform3D` 的数据与矩阵 API，Zeus 只加 `owner`、组件生命周期与序列化。

命名消歧：注解与 import 写清 `from zeus.transform import Transform` 与 `from py2cpp.spatial.transform import Transform3D`；文档称前者「场景组件 Transform」，后者「spatial.Transform3D」。

### 4.6 MeshComponent / CameraComponent

- `MeshComponent(Transform)`：`Mesh` + `Material`；`on_draw` / 由 World draw 收集提交 `Renderer`。
- `CameraComponent(Transform)`：投影与 view-projection；跟随可写在组件或 `FollowCamera(GameObject)` 子类。

第一阶段跳一跳可用：`Player(GameObject)` + 默认 `MeshComponent` + `JumpMotor(Component)`，或把跳跃逻辑写在 `Player` 子类——**两种都合法**。

### 4.7 TaskManager / Time / Input / FSM

同前：Task 表；`Clock`；`Input` + `@union` 事件；玩家 FSM `idle`/`charging`/`jumping`/`failed`。

### 4.8 ECS 预留

与 §2.7 一致；桥接「哪个 GameObject / 组件字段 ↔ ECS 行」。符号保持 `ECSEntity` / `ECSComponentTable`，勿与 Zeus `Component` 混名。

---

## 5. OpenGL 渲染设计

（分层、`Renderer`、`Mesh` 顶点 `float[:]`/`span`、`Material`、Camera 透视、GLFW 优先 / WGL 备选、native 边界）— 与前一版相同；draw 数据来自 `MeshComponent` 的 world 矩阵，而非已删除的 `GameMesh` 类型名。

---

## 6. 编辑器设计

Hierarchy：`GameObject` 树；展开可选显示其下 `Transform` 附件与组件列表。  
Inspector：对象字段 + 组件列表字段（含 root `Transform` TRS）。  
其余 Toolbar / Scene View / Assets / Console 同前。

---

## 7. 插件系统

可注册：命令、菜单、**GameObject 子类**、**Component / Transform 子类**。  
第一阶段优先命令 + 菜单 + 类型注册。

---

## 8. MCP 与命令设计

命令 ADT + JSON 桥接。清单：

- 工程 / 场景：同前（`scene.list_objects` / `scene.find_object` 等）。
- 对象：`object.create` / `object.delete` / `object.rename` / `object.set_position`（作用在 root `Transform`）等。
- 组件：`object.add_component` / `object.remove_component` / `object.get_components`。
- 运行 / 编辑器：`play.*`、`editor.select_object` 等。

---

## 9. 跳一跳 demo

### 9.1 推荐结构（双通道示例）

- `Player(GameObject)`：可含 FSM；默认挂 `MeshComponent` + 可选 `JumpMotor(Component)`。
- `Platform(GameObject)`：`MeshComponent` + 落点范围（字段或组件）。
- 相机：`GameObject` + `CameraComponent`（或 `FollowCamera(GameObject)`）。
- `JumpGame`：分数与平台生成（World 脚本或管理器对象）。

### 9.2–9.4

规则、简化物理、验收同前；**不必**第一阶段上 ECS。

---

## 10. 序列化与资源

```json
{
  "name": "JumpDemo",
  "root": {
    "type": "GameObject",
    "name": "Render",
    "root_transform": {
      "local_position": [0, 0, 0],
      "local_rotation": [0, 0, 0, 1],
      "local_scale": [1, 1, 1]
    },
    "components": [
      {"type": "MeshComponent", "mesh": "cube", "material": "default"}
    ],
    "children": [
      {
        "type": "Player",
        "name": "Player",
        "root_transform": {"local_position": [0, 1, 0]},
        "components": [
          {"type": "MeshComponent", "mesh": "cube", "material": "player"},
          {"type": "JumpMotor", "jump_power": 8.0}
        ]
      }
    ]
  }
}
```

---

## 11. 与现有 Py2Cpp 模块的关系

| 模块 | 用途 |
|------|------|
| `py2cpp.spatial` | `zeus.Transform` 的数学与父子合成底座 |
| `py2cpp.design.ecs` | 后期 SoA；保持 `ECS*` 前缀 |
| `concur` / `serde` / `io` / `ui` / `weak` | Task、序列化、资源、编辑器、弱引用 |

---

## 12. 阶段计划

进度约定：每阶段结束须 `zeus\build.bat`（或阶段新增测例）全绿；只改源树，不手改 `generated/`。

### Phase 0 — 文档与选型（已完成）

- 本文档定案；布局 `zeus/src` + `zeus/ffi`；GLFW（非 WGL）为首版窗口后端。
- MCP / UI 嵌 GL 列为后续，不阻塞 Runtime。

### Phase 1 — Runtime 骨架（已完成）

| 交付 | 路径 / 测例 |
|------|-------------|
| `World` / Task 槽 | `src/world.py`、`src/task.py` |
| `GameObject` / `Component` / `Transform` | `src/scene.py` |
| 组件生命周期 + `kind` 查找 | `test_runtime`：`ComponentLifecycleTests` |
| 简易重力 | `src/simple_world.py` |
| 场景序列化烟测 | `SceneSerializeSmokeTests` |

验收：`test_runtime.exe` 失败数 0。

### Phase 2 — OpenGL 烟雾（已完成）

| 交付 | 路径 / 测例 |
|------|-------------|
| GLFW 窗（可 hidden） | `src/platform/window.py` + `ffi/glfw` |
| 立即模式清屏 + 彩色 cube | `src/render/opengl/gl_device.py`、`src/render/mesh.py` |
| `MeshComponent` / `CameraComponent` | `src/scene.py` |

验收：`test_render.exe` 失败数 0（本机需 OpenGL 驱动）。

### Phase 3 — Editor MVP

目标：可看、可选、可改、可 Play 的最小编辑器（依赖 Runtime；反向禁止）。

| 项 | 内容 |
|----|------|
| **Hierarchy** | `GameObject` 树；展开显示组件列表与 root `Transform` |
| **Inspector** | 对象 `name`/`active`/`visible`；组件字段（含 TRS）；`add`/`remove` 组件入口 |
| **Scene View** | 复用 Phase 2 渲染视口（可独立窗；UI 嵌 GL 可后置） |
| **Toolbar** | Play / Pause / Stop → `World` 状态机 |
| **工程** | 打开/保存场景 JSON（扩展 Phase 1 序列化：类型名、组件表、子树） |
| **测例** | `test_editor_smoke`：无 UI 也可测命令层「选中 / 改字段 / Play 一步」 |

**暂不实现（Phase 3）**：完整 Assets 浏览器、撤销栈、多视口、材质编辑器。

**验收**：编辑器进程能加载场景 → 改 root 位移 → Play 若干帧 → 保存再加载一致。

### Phase 4 — 命令系统

目标：Editor / 插件 / MCP **共用**同一套命令 ADT（`@union` + JSON）。

| 项 | 内容 |
|----|------|
| **命令表** | `project.*` / `scene.*` / `object.*` / `component.*` / `play.*` / `editor.*`（见 §8） |
| **执行器** | `CommandBus.dispatch(cmd) -> Result`；Play 态限制写命令 |
| **桥接** | JSON ↔ 命令（`serde`）；无第二套字符串协议 |
| **测例** | `test_commands`：create/find/set_position/add_component/remove 往返 |

**验收**：纯命令驱动即可完成「建对象 → 挂 Mesh → 改位姿 → 步进」；Editor UI 只发命令。

### Phase 5 — 插件 + MCP

| 项 | 内容 |
|----|------|
| **插件** | manifest（id/版本/入口）；生命周期 `on_load`/`on_unload`；注册菜单项与命令 |
| **类型注册** | 插件可注册 `GameObject` 子类、`Component`/`Transform` 子类（编译期或表驱动，忌运行期任意 `eval`） |
| **MCP** | 对外 JSON-RPC/stdio（或仓库既有 MCP 形态）包装同一 `CommandBus` |
| **测例** | 示例插件注册一条命令；MCP 客户端发 `object.create` 成功 |

**验收**：外部工具仅经 MCP/命令即可改场景，无需点 UI。

### Phase 6 — 跳一跳 Demo

| 项 | 内容 |
|----|------|
| **玩法** | `Player` / `Platform` / 蓄力跳跃 / 重力 / 落点判定 / 分数 |
| **输入** | 键盘或鼠标（`platform/input`）；FSM：`idle`→`charging`→`jumping`→`landed`/`failed` |
| **相机** | `CameraComponent` 跟随 |
| **渲染** | 平台与角色 mesh + 纯色材质（仍可立即模式；可引入薄 shader 叶子） |
| **入口** | `examples/jump` 或 `zeus/src/demos/jump` + `demo.bat` 式脚本 |
| **测例** | headless：固定输入序列断言分数/落点；可选有窗烟雾 |

**验收**：可玩一局；编辑器能改 `jump_power` 等字段并 Play 验证。

### Phase 7（可选）— ECS / prange 热路径

| 项 | 内容 |
|----|------|
| **边界** | 仅批量变换/物理候选数据进 `design.ecs` SoA；节点 API 不变 |
| **桥接** | GameObject/组件字段 ↔ ECS 行映射表 |
| **并行** | `prange` 更新候选子集 |
| **测例** | 同玩法下 N 平台更新正确性；可选计时对比 |

**验收**：玩法不强制改写为 ECS；开关或配置启用热路径后结果一致。

### 阶段依赖（简图）

```text
Phase 0–2（已完成）
    → Phase 3 Editor MVP
    → Phase 4 命令（可与 3 尾部重叠：先 Bus 再挂 UI）
    → Phase 5 插件 + MCP（依赖 4）
    → Phase 6 跳一跳（依赖 2；编辑器用 3–4 更佳）
    → Phase 7 ECS（可选，依赖 6 或独立微基准）
```

---

## 13. 技术风险

- OpenGL / 视口嵌入 / 插件编译期注册 / Play 态命令权限：同前。
- **命名冲突**：`zeus.Transform` vs `spatial.Transform3D` — 强制限定导入与文档用语。
- **双通道滥用**：指南优先「可复用 → 组件；强绑定玩法 → 子类」；避免又继承又堆无意义组件。
- **组件与对象双树**：对象树（子 GameObject）与 Transform 附件树职责写清，编辑器分层显示。
- **FFI 宏**：`GL_*` / `GLFW_*` 与 C 头同名 — 译器 FFI glue 须 `#undef`（已落地，勿在业务改名绕行）。

---

## 14. 验收清单

### Runtime / Render（Phase 1–2）

- [x] `World`；`GameObject` 树 attach/find
- [x] 子类化组件（如 `ScoreBoard`）可 `on_update`
- [x] `add_component` / `find_component`；`Transform` 附件与合成
- [x] 场景序列化烟测；GLFW 清屏 + cube

### Editor（Phase 3）

- [ ] Hierarchy + Inspector + Play/Stop
- [ ] 保存/加载含组件列表的场景，字段可改

### 命令 / 插件 / MCP（Phase 4–5）

- [ ] 命令总线覆盖 §8 清单核心子集
- [ ] 示例插件注册；MCP 可改 root `Transform` 与组件字段

### Jump / ECS（Phase 6–7）

- [ ] 跳一跳可玩；编辑器可调参
- [ ] （可选）ECS 热路径结果一致

---

## 15. 下一步建议

1. **Phase 3**：场景 JSON 图式定稿 → Hierarchy/Inspector 最小 UI（或先做无 UI 的编辑命令测例）。
2. **Phase 4**：落地 `CommandBus` + `@union` 命令，Editor 只发命令。
3. **Phase 5**：manifest 插件 + MCP 包装同一总线。
4. **Phase 6**：跳一跳 demo；输入与 FSM。
5. 有 profiling 数据后再上 **Phase 7** ECS。

实现新阶段前若改对外 API / 序列化格式，仍按 py2cpp-design「先问清再实现」对齐后再改 `zeus/src`。
