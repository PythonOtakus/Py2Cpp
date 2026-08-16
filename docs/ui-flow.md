# `py2cpp.ui.flow` — 蓝图式工作流编辑器

Py2Cpp 标准库扩展：在 Win32 画布上编辑**节点图**（类似 UE5 Blueprint）。节点由宿主类上 **`@annotation` 标注的方法** 译期注册；引脚由**方法签名**自动生成。

- **Panel 对照**：[`py2cpp/ui/panel.py`](../py2cpp/ui/panel.py) 用 `@UILabelMeta` / `@UIButtonMeta` + `Self.iterFields` / `Self.iterMethods`；Flow 用 `@FlowNodeMeta` 等 + **新增**方法签名反射 API。
- **架构总览**：[参考手册 §10.10](./参考手册.md#1010-uiflow蓝图编辑器)（摘要 + 链接本文）。
- **状态**：**P0/P1 已落地**（画布、壳层、palette、JSON、`UIFlowMixin`）；**P2.1 已落地**（内置 Branch/ForLoop、`FlowRuntime`、Run 菜单启用）。

---

## 1. 目标与边界

| 项 | 说明 |
|----|------|
| **模块路径** | `py2cpp/ui/flow/`（`meta`、`model`、`catalog`、`builtins`、`runtime`、`layout`、`style`、`canvas`、`panel`、`shell`、`palette`、`serialize`）；基础设施 `py2cpp/ui/` 含 `menu`、`tooltip`、`canvas` |
| **P0** | 可视化编辑器：网格画布、节点框、Exec/Data 引脚、贝塞尔连线、平移缩放、拖拽与连线；**方法 → 节点** 译期目录 ✅ |
| **P1** | 编辑器壳（顶菜单 + 左 palette + 中画布）、palette 拖拽创建、tooltip、Delete/Esc、JSON 存盘 ✅ |
| **P2.1** | `flow/runtime.py` + 内置 Branch/ForLoop；Exec walk + Pure 求值；宿主 `flow_invoke_*`（译期 `getattr`）；**Run** Play / Play from Selected / Stop ✅ |
| **平台** | 与现有 `UIApp` 一致：Windows Win32 + GDI；非 Windows `UIApp.isAvailable()` 为 false 时 no-op |

---

## 2. 与 UE5 Blueprint 的对应关系

UE5 里常见三类「可放进图里的 callable」：

| UE5 概念 | 图上的样子 | 执行语义 |
|----------|------------|----------|
| **BlueprintCallable**（非 Pure） | 白色 **Exec In** + **Exec Out**（Then）+ 数据引脚 | 控制流到达时**执行**函数，再从 Then 继续 |
| **BlueprintPure** | **无** Exec 引脚，仅有数据 In/Out | **不**参与控制流；需要输出值时**求值**，可多处复用、无副作用于 Exec 链 |
| **Event**（如 Begin Play、Custom Event） | 入口事件常**只有 Exec Out**（引擎或图内「触发」） | 控制流的**起点**或**异步入口**；Begin Play 不能被别的节点 Exec 连入 |

Py2Cpp 用三个注解表达上述语义（见 §3）。

---

## 3. 注解语义（`py2cpp/ui/flow/meta.py`）

### 3.1 `@FlowNodeMeta` — 默认「可调用节点」（≈ BlueprintCallable）

```python
@annotation
@dataclass
class FlowNodeMeta:
  """方法级蓝图节点（非 Pure、非 Event 入口）。

  - ``@FlowNodeMeta()`` → 节点标题 = 方法名
  - ``@FlowNodeMeta("Take Damage", category="Combat")``
  """
  title: str = ""
  category: str = ""       # palette 分组；空 → ``Self.__name__``
  hidden: bool = False     # 注册但不进 palette
  inheritable: bool = True # ``Self.iterMethods[FlowNodeMeta](mro=True)`` 时合并基类方法
```

**实际意义**：该方法在图里是一个**带控制流的步骤**。上游 Exec 连到 `execute` 引脚后，将来（P2）会调用 `self.method(…)`，再从 `then` 引脚继续。适合「做一件事并往下走」的逻辑：`fire`、`apply_damage`、`spawn_actor`。

**引脚（由签名 + 本注解自动生成，见 §6）**：

- Exec：**In** `execute`、**Out** `then`
- Data：每个形参（除 `self`）→ **In**；若 `Self.getMethodReturnType(method) is not None` → **Out** `Return Value`

---

### 3.2 `@FlowPureMeta` — 纯函数节点（≈ BlueprintPure）

```python
@annotation
@dataclass
class FlowPureMeta:
  """纯节点：无 Exec 引脚，仅数据 In/Out（类似 UE ``BlueprintPure``）。"""
  title: str = ""
  category: str = ""
  hidden: bool = False
  inheritable: bool = True
```

**实际意义**：

1. **不参与控制流**：图中没有白色 Exec 线连进/连出该节点；P2 执行时不会在 Exec 链上「调用」它，而是在需要某个**数据输入**的值时对该节点**求值**。
2. **语义约束（约定）**：方法应**无副作用**或仅只读（如 `return self.hp`）。Py2Cpp **不在编译期强制** Pure，但连线 UI 与 P2 调度按 Pure 处理（无 Exec）。
3. **典型用途**：getter、`min(a,b)` 式计算、查询状态，供 Data 线消费。

**引脚**：

- **无** Exec
- Data：形参 → **In**；有返回值 → **Out** `Return Value`

实现上可在 mixin 展开时把 `FlowPureMeta` **视为** `pure=True` 的节点模板，与 `FlowNodeMeta(pure=True)` 等价（若保留单一 `FlowNodeMeta` 的 `pure` 字段，则 `FlowPureMeta` 仅为糖注解）。

---

### 3.3 `@FlowEventMeta` — 入口事件（≈ Event BeginPlay / 图入口）

```python
@annotation
@dataclass
class FlowEventMeta:
  """入口事件：仅 Exec Out，无 Exec In（类似 UE ``Event BeginPlay`` 一类入口）。"""
  title: str = ""
  category: str = "Events"
  hidden: bool = False
  inheritable: bool = True
```

**实际意义**：

1. **控制流起点**：P2 从这类节点开始沿 Exec 边 walk 图；**没有** `execute` 输入引脚，因此**不能**被其它节点的 `then` 连入（与 Begin Play 一致）。
2. **不是普通函数调用**：表示「当某事件发生时的入口」（生命周期、自定义事件名等）。用户写 `def onBegin(self) -> None: ...`，在 palette 里拖入 `Event Begin Play` 节点，Exec 从该节点**流出**到后续 Callable。
3. **与 Callable 的区别**：Callable 必须等上游 Exec 到达才运行；Event 由**运行时/编辑器**「触发」或作为**默认根**（例如 `onFlowReady` 预置一个 Begin 节点）。

**引脚**：

- Exec：仅 **Out** `then`（无 In）
- Data：P0 **不**从形参生成 Data In（事件方法建议 `-> None` 且无业务参数）；P1 可扩展 payload 字段

**注意**：UE 的 **Custom Event** 往往**既有 Exec In 又有 Exec Out**（可被 Call Function 触发）。那属于 **Callable** 语义，应标 `@FlowNodeMeta`，**不要**用 `@FlowEventMeta`。`FlowEventMeta` 专指**不可被 Exec 连入的入口**。

---

### 3.4 三者对照表

| 注解 | Exec In | Exec Out | Data In | Data Out | UE 近似 | 典型方法 |
|------|---------|----------|---------|----------|---------|----------|
| `@FlowNodeMeta` | ✅ `execute` | ✅ `then` | 形参 | 返回值（若有） | BlueprintCallable | `def fire(self, n: int) -> bool` |
| `@FlowPureMeta` | ❌ | ❌ | 形参 | 返回值（若有） | BlueprintPure | `def getHp(self) -> int` |
| `@FlowEventMeta` | ❌ | ✅ `then` | ❌（P0） | ❌ | Event BeginPlay | `def onBegin(self) -> None` |

---

## 4. 译期方法反射 API（新增）

与 `Self.iterMethods[Ann]()` / `Self.getMethodAnnotation[Meta](method)` 同层，由 `src/passes/method_meta.py` 展开（**非** CPython 运行时）。

| API | 形式 | 译期行为 |
|-----|------|----------|
| 方法名列表 | `Self.iterMethods[FlowNodeMeta](mro=True, publicOnly=…, glob=…)` | 已有；带 `@FlowNodeMeta` 的方法名（声明序） |
| 形参名 | `Self.iterMethodParams(method)` | `for param in Self.iterMethodParams(method):` → 展开为各形参标识符；**跳过 `self`** |
| 形参类型 | `Self.getMethodParamType(method, param)` | 折叠为类型本身；通过 `T is int` 等类型分派转换为 Flow typeId |
| 返回类型 | `Self.getMethodReturnType(method)` | 折叠为类型本身或 `None`；`-> None` 或无返回注解 → **`None`** |
| 是否有返回值 | `Self.getMethodReturnType(method) is not None` | 译期折叠为 `True`/`False` |

### 4.1 用法示例（`_ensureFlowCatalog` 内）

```python
for method in Self.iterMethods[FlowNodeMeta](mro=True):
  meta = Self.getMethodAnnotation[FlowNodeMeta](method)
  ...
  for param in Self.iterMethodParams(method):
    if Self.getMethodParamType(method, param) is int:
      typeId: str = "int"
    catalog.add_data_in_pin(kindId, param, typeId)
  return_type = Self.getMethodReturnType(method)
  if return_type is not None:
    catalog.add_data_out_pin(kindId, "Return Value", return_type)
```

### 4.2 实现要点（译器）

- **解析源**：宿主 `ClassInfo` 上 `ast.FunctionDef` 的 `args`（含 `posonlyargs` + `args`，跳过首个 `self`）与 `returns`。
- **`get_param_type` / `get_return_type`**：将注解 AST 映射为 typeId 字符串（§6.2）；不支持泛型/联合的精细区分，P0 用 `"object"`。
- **`iterMethodParams` 展开**：在 `for param in Self.iterMethodParams(method_var)` 中，`method_var` 须为**常量方法名**（与 `iterMethods` 循环 unroll 联用，或外层已 unroll 为 `ast.Constant`）。
- **挂载**：在 `src/passes/mixins.py` 的 mixin 展开流水线中，于 `expand_iter_methods_*` 之后增加 `expand_iter_method_params` / `expand_method_type_queries`；`reflect/mixin.py` 增加同名 stub（IDE 友好）。
- **单测**：`src/tests/test_method_meta.py` 增加 param/return 折叠用例。

---

## 5. 模块与文件

```text
py2cpp/ui/
  canvas.py         # UICanvas / UIPaintContext（通用 GDI 画布；flow 继承）
  menu.py           # UIMenuBar（P1）
  tooltip.py        # UITooltipHost（P1）
  flow/
    meta.py         # FlowNodeMeta, FlowPureMeta, FlowEventMeta
    model.py        # FlowPinEnum, FlowPin, FlowNode, FlowEdge, FlowGraph
    catalog.py      # FlowNodeCatalog, FlowNodeTemplate
    builtins.py     # 内置 Branch / For Loop 模板注册
    runtime.py      # FlowRuntime：图执行
    layout.py       # 节点尺寸、引脚坐标、screen↔graph、hit_test
    style.py        # UIFlowStyle
    canvas.py       # UIFlowCanvas(UICanvas)
    panel.py        # UIFlowMixin（含 Run 接线与 flow_invoke_*）
    shell.py        # UIFlowShell：layout + 菜单 + palette/canvas 协调
    palette.py      # UIFlowPalette：分组列表、拖拽源
    serialize.py    # FlowGraph ↔ JSON

templates/ui/
  +canvas.inl       # 子 HWND 双缓冲 + 指针/滚轮 → Python
  +menu.inl         # HMENU / WM_COMMAND（P1）
  +palette.inl      # 侧栏子窗口（P1）
  +tooltip.inl      # ToolTip 控件（P1）
  +file_dialog.inl  # GetOpenFileName / GetSaveFileName（P1）

test/ui/test_flow.py
examples/ui_flow_demo.py
```

**基础设施登记**：

- `src/constant/stdlib_modules.py`：`ui/canvas`、`ui/flow/*` 及 P1 模块路径与 `UMBRELLA_PRIORITY_MODULES` 顺序（在 `ui/window` 之后）。
- 注入模板：`ui/canvas` → `ui/+canvas.inl`（`UIFlowCanvas` 继承 `UICanvas`，**无**独立 `+flow_canvas.inl`）。

---

## 6. 引脚与类型

### 6.1 `FlowPinEnum`

```text
ExecIn, ExecOut, DataIn, DataOut
```

### 6.2 注解 → `typeId`（`get_param_type` / `get_return_type`）

| Python 注解 | typeId |
|-------------|---------|
| `bool` | `"bool"` |
| `int` | `"int"` |
| `float` / `float64` | `"float"` |
| `str` | `"str"` |
| `None` / `-> None` | （不产生 Data Out） |
| 其它 / 缺失 | `"object"` |

Exec 引脚无 typeId；UI 着色：Exec 白/灰；Data 按 typeId 色板（与 UE 相近即可）。

### 6.3 节点标识

```text
kindId = Self.__name__ + "." + methodName    # 如 "ShooterLogic.fire"
```

图实例 `FlowNode` 含 `id`（实例）、`kindId`、`x`/`y`（`float64`）、运行时引脚 id 列表。

### 6.4 连线规则（P0）

| 规则 | 行为 |
|------|------|
| Exec | 仅 `ExecOut` → `ExecIn` |
| Data | 仅 `DataOut` → `DataIn` |
| 类型 | `typeId` 相同，或 **In** 端为 `"any"`（P0 不生成 any 引脚；目标 In 为 `object` 时视为宽进） |
| 输入唯一 | 每个 **DataIn** / **ExecIn** 最多一条边；新连线替换旧边 |
| 禁止 | 自连；`FlowEventMeta` 节点无 ExecIn，故无连入 |

---

## 7. 架构分层

### 7.1 P0（当前）

```text
┌─────────────────────────────────────────────────────────┐
│  Python：FlowGraph / FlowNodeCatalog / UIFlowMixin      │
│  译期：iterMethods + iterMethodParams + get_*_type   │
│  交互：UIFlowCanvas.on_pointer_* / onWheel → graph     │
├─────────────────────────────────────────────────────────┤
│  @native：UICanvas mount / invalidate + +canvas.inl     │
├─────────────────────────────────────────────────────────┤
│  UIApp / UIWindow / UIEventDelegate                             │
└─────────────────────────────────────────────────────────┘
```

### 7.2 P1 编辑器壳（`UIFlowShell`，参考 UE5 / Qt Designer）

```text
┌──────────────────────────────────────────────────────────────┐
│  File  Edit  View  Run                          [窗口标题]    │  UIMenuBar
├─────────────┬────────────────────────────────────────────────┤
│ ▼ Events    │                                                │
│   Begin Play│           UIFlowCanvas                         │
│ ▼ Combat    │           （网格 + 节点 + 连线）                  │
│   Fire      │                                                │
└─────────────┴────────────────────────────────────────────────┘
  UIFlowPalette（~240px，固定宽）     画布占剩余客户区（扣除菜单栏高度）
```

| 组件 | 职责 |
|------|------|
| `UIFlowShell` | 挂载 menu / palette / canvas；`layout_children`；palette→canvas 拖放桥接 |
| `UIMenuBar` | Win32 `HMENU`；`WM_COMMAND` → `shell.onMenuCommand(id)` |
| `UIFlowPalette` | 按 `category` 分组折叠列表；拖拽 `kindId` 到画布创建节点 |
| `UIFlowCanvas` | 不变为主编辑面；接收 drop、画布内 hover tooltip |
| `UITooltipHost` | palette 项 / 画布节点 / 引脚悬浮提示 |

**Native 原子化**：业务逻辑在 Python；C++ 仅 GDI 绘制、Win32 消息与文件对话框叶子（同 `UIPanelMixin`）。

---

## 8. `UIFlowMixin` 与编辑器壳

### 8.1 Mixin API

```python
@mixin
class UIFlowMixin:
  _flowShell: UIFlowShell = new()      # P1：含 canvas / palette / menu
  _flowCanvas: UIFlowCanvas = new()    # 兼容：shell.canvas 同一实例
  _flowCatalog: FlowNodeCatalog = new()
  _flowCatalogReady: bool = False
  _flowWin: UIWindow = new()

  def _ensureFlowCatalog(self) -> None: ...
  def drawFlow(self, win: UIWindow @ref) -> None: ...   # P1：shell.attach(win)
  def createFlow(self, title: str = "", width: int = -1, height: int = -1) -> UIWindow: ...
  def showFlow(self, title: str = "", width: int = 1280, height: int = 720) -> int: ...
  def onFlowReady(self) -> None:
    """可选 override：预置 Event 节点等。"""
    pass
  def onFlowRun(self) -> None:
    """P1 占位；P2 由 Run 菜单调用 FlowRuntime。"""
    pass
  def onFlowRunFromSelected(self) -> None:
    """P2：从选中 Event 节点开始执行。"""
    pass
  def onFlowStop(self) -> None:
    """P2：中止执行（同步首版可 no-op）。"""
    pass
```

**P0**：`drawFlow` 曾全客户区 mount 画布。**P1**：改经 `UIFlowShell` 布局（菜单 + 左 palette + 中画布）。

`_ensureFlowCatalog` 须用 `Self.getMethodAnnotation[…](method)` 读取 `.title` / `.category` / `.hidden`（与 `UIPanelMixin` 同模式），跳过 `hidden=True` 的模板。

### 8.2 菜单栏（P1）

命令 ID 由 `FlowMenuIdEnum`（`py2cpp/ui/menu.py` 或 `flow/shell.py`）枚举；`WM_COMMAND` 的 `LOWORD(wParam)` 映射到 `UIFlowShell.onMenuCommand`。

| 菜单 | 项 | 快捷键 | 行为 | 阶段 |
|------|-----|--------|------|------|
| **File** | New | Ctrl+N | 清空 `FlowGraph`（保留 catalog） | P1 |
| | Open… | Ctrl+O | JSON 载入（`.flow.json`） | P1 |
| | Save | Ctrl+S | 保存到当前路径 | P1 |
| | Save As… | Ctrl+Shift+S | 另存为 | P1 |
| | Exit | Alt+F4 | 关闭窗口 / `UIApp.quit()` | P1 |
| **Edit** | Delete | Del | 删除选中节点及关联边 | P1 |
| | Deselect | Esc | 取消选中 / 取消拖线 / 取消 palette 拖放 | P1 |
| **View** | Reset Zoom | Ctrl+0 | `zoom=1`，`pan=0` | P1 |
| **Run** | Play | F5 | 从图中全部 Event 入口沿 Exec 拓扑执行 | **P2.1** ✅ |
| | Play from Selected | Ctrl+F5 | 从选中节点执行（Event 或带 `execute` 的节点） | **P2.1** ✅ |
| | Stop | Shift+F5 | 设置 `FlowRuntime.cancelled`（协作式） | **P2.1** ✅ |

**Run / `FlowRuntime` 语义（P2.1）**：

1. **Play**（`onFlowRun` → `runAll`）：对每个 Event 节点从 `then` 沿 Exec 边 walk；Callable 经宿主 `flowInvokeCallable`（译期展开 `getattr`）；Pure 在 Data 边求值时经 `flowInvokePure`（带节点缓存）。
2. **Branch**（`flow.builtin.branch`）：`condition`（bool DataIn）→ `OnTrue` / `OnFalse` ExecOut。
3. **For Loop**（`flow.builtin.for_loop`）：`count`（int DataIn）→ 循环 `LoopBody`，结束后 `Completed`。
4. **Stop**：`cancelled=True`；节点边界检查退出。
5. 首版 Callable 形参按 **单个 int 形参**（或 0 参）求值并调用；多参/复杂类型后续扩展。

### 8.3 Palette 侧栏（P1）

- 宽 **240px** 固定（P2 再考虑可拖拽分隔条）。
- 按 `FlowNodeCatalog.categories()` 分组；组头点击折叠/展开；`Events` 组优先。
- 左键拖拽项 → 在画布客户区释放 → `addNodeFromKind(kindId, gx, gy)`（`screenToGraph`）。
- Exec / Pure / Event 行首色点区分（白 / 蓝 / 橙，对齐 `UIFlowStyle`）。

### 8.4 Tooltip（P1）

| 悬浮目标 | 内容 |
|----------|------|
| Palette 项 | `title`、`kindId`、引脚摘要（由 catalog 拼 `str`） |
| 画布节点 | `node.title` + 引脚列表 |
| 画布引脚 | `pin.name` + `typeId` + In/Out |

可选 P1.1：``@FlowNodeMeta(tip="…")`` 覆盖自动生成文案。

### 8.5 JSON 序列化（P1）

模块 `flow/serialize.py`，用 `serde/json`：

```json
{
  "nodes": [{"id": 1, "kindId": "ShooterLogic.fire", "title": "Fire", "x": 320, "y": 80, "pins": []}],
  "edges": [{"fromPin": 2, "toPin": 5}]
}
```

Open 时未知 `kindId` 跳过该节点；`UIFlowShell._doc_path` 供 Save / Save As。

---

## 9. 画布交互（P0 默认）

| 操作 | 绑定 |
|------|------|
| 平移 | **右键拖拽** + **中键拖拽**（均支持） |
| 缩放 | **滚轮**（以光标为中心） |
| 选节点 | 左键点击节点 |
| 拖节点 | 左键拖拽节点 |
| 连线 | 从 **Out** 引脚拖到 **In** 引脚 |
| 取消拖线 | 在空白处松开 |

---

## 10. 完整用法示例

```python
from py2cpp import *
from py2cpp.ui.flow.meta import FlowEventMeta, FlowNodeMeta, FlowPureMeta
from py2cpp.ui.flow.panel import UIFlowMixin


@dataclass
class ShooterLogic(UIFlowMixin):
  hp: int = 100
  ammo: int = 30

  @FlowEventMeta("Begin Play")
  def onBegin(self) -> None:
    pass

  @FlowNodeMeta("Fire", category="Combat")
  def fire(self, shots: int) -> bool:
    if self.ammo < shots:
      return False
    self.ammo -= shots
    return True

  @FlowPureMeta("HP")
  def getHp(self) -> int:
    return self.hp

  def onFlowReady(self) -> None:
    # 可选：在 (x,y) 放置 Begin Play 节点
    self._flowCanvas.addNodeFromKind("ShooterLogic.onBegin", 80.0, 80.0)


def main() -> int:
  logic: ShooterLogic = new()
  return logic.showFlow("Shooter Blueprint", 1280, 720)
```

P1 起：左侧 palette 按 `category` 分组（`Events` / `Combat` / 类名等），拖拽到画布创建节点；**Run → Play**（F5）在 P2 执行图逻辑。

---

## 11. 绘制（`ui/canvas` + `UIFlowCanvas.onPaint`）

- 通用层 `UICanvas` / `UIPaintContext`：`ctx.draw_*` 录命令；**`commit()` 为纯 Python** `match` 分发到 `_gdi_*` 叶子（`+canvas.inl`）。Bezier 控制点在 Python（`_bezierControls`）；`mount` / `containsScreenPoint` 尺寸与命中算术在 Python，Win32 仅 `_win_*` / `clientFromScreen` / `setBounds` / `invalidate`。圆角 / 连线 / 椭圆走 **GDI+** AA；矩形与文字仍用 GDI。`WndProc` + 双缓冲仍为 C++ 回调胶水。
- 双缓冲 `BitBlt`；背景 `#1E1E1E`；网格 minor/major（画布坐标，不随 graph pan 缩放步长）。
- 节点：圆角框（`NodeCornerRadius`）+ 标题栏 / 边框随 `zoom` 缩放；引脚旁显示 `pin.name`（输入左对齐、输出右对齐）；画布字号默认 15pt（随 `zoom`）；palette 侧栏固定 15pt（`UIFlowStyle.paletteFontSize`，不随画布缩放）。
- 连线：三次贝塞尔，切线水平离开引脚。
- Palette 侧栏为 UI chrome，**不**使用 graph `zoom`。

---

## 12. 测试与验证

| 层 | 路径 | 内容 |
|----|------|------|
| 译器单测 | `src/tests/test_method_meta.py` | `iterMethodParams` / `get_param_type` / `get_return_type` / `is not None` 折叠 |
| 集成测 | `test/ui/test_flow.py` | `FlowGraph.connect` 规则、`catalog` 引脚数、`createFlow` 句柄非 0 |
| 演示 | `examples/ui_flow_demo.py` | 交互式三节点图 |

```bat
python main.py py2cpp\__init__.py -o generated --no-main
build.bat ui/test_flow --seq
```

---

## 13. 分阶段交付

### P0 ✅

- [x] 译期 API：`iterMethodParams`、`get_param_type`、`get_return_type`
- [x] `FlowNodeMeta` / `FlowPureMeta` / `FlowEventMeta` + `_ensureFlowCatalog`
- [x] `FlowGraph` / `FlowNodeCatalog` / 连线规则
- [x] `UIFlowCanvas`（继承 `UICanvas`）+ `+canvas.inl`
- [x] `UIFlowMixin.showFlow`、demo、集成测
- [x] **不含**图执行

### P1（进行中）

- [ ] `UIFlowShell` + `UIMenuBar`（File / Edit / View / **Run**）
- [ ] `UIFlowPalette` 分组列表 + 拖拽创建
- [ ] `UITooltipHost`（palette + 画布）
- [ ] `_ensureFlowCatalog` 读 `getMethodAnnotation`（title / category / hidden）
- [ ] `FlowGraph.removeNode`、Delete / Esc
- [ ] JSON 序列化（`flow/serialize.py` + `serde/json`）
- [ ] `@FlowPinMeta("显示名")` 引脚标签
- [ ] Run 菜单三项注册；P2 前 **disabled** 或调 `onFlowRun*` 空壳

### P2.1 ✅

- [x] `flow/builtins.py`：Branch / For Loop 内置模板
- [x] `flow/runtime.py`：`FlowRuntime` Exec walk + Pure 求值 + Branch/ForLoop
- [x] `UIFlowMixin.flow_invoke_*` + Run → Play / Play from Selected / Stop
- [x] `test/ui/test_flow.py` 线性 / Branch / ForLoop 图执行用例

### P2 后续（可选）

- [ ] 多参 Callable / 非 int 数据引脚全类型
- [ ] 执行日志或状态栏
- [ ] While / 带 Index 的 ForEach

---

## 14. 明确不做（P0–P2.1）

- 图编译为 C++、VM、**断点调试**（Run 菜单不含 Break / Step）
- 右侧属性 Inspector（Qt Designer 式细节面板）
- Comment 框、Minimap
- Custom Event（带 Exec In）—— 用 `@FlowNodeMeta` 表达
- Palette 可拖拽分隔条（固定 240px）

---

## 15. 编码规范自检（实现时）

- 标准库写法：`new`、`Self`、``@dataclass`` / ``@copyable``、无 STL、无手写 dunder。
- 复用 `UIApp` / `UIWindow` / `UIEventDelegate` / `ui_theme_scale`；勿重复造 Panel 窗口逻辑。
- `ui/flow/__init__.py` **勿** re-export 子模块（与 `ui/__init__.py` 一致）。
- 文档：本文 + [参考手册 §10.10](./参考手册.md#1010-uiflow蓝图编辑器) + [编码规范 §8.1](./编码规范.md#81-模块--cpython-对照) 模块表。
