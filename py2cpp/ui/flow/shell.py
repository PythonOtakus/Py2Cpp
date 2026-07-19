"""Flow 编辑器壳：菜单 + palette + 画布布局。"""
from ...builtins import *
from ...io.path import Path
from ..menu import UIMenuBar
from ..file_dialog import pick_open_file, pick_save_file
from ..tooltip import UITooltipHost
from ..events import UIEvent
from ..window import UIWindow
from .canvas import UIFlowCanvas
from .catalog import FlowNodeCatalog
from .palette import UIFlowPalette
from .serialize import graph_from_json, graph_to_json


PALETTE_WIDTH: int = 240


@enum
class FlowMenuId:
  FileNew = 1
  FileOpen = 2
  FileSave = 3
  FileSaveAs = 4
  FileExit = 100
  EditDelete = 201
  EditDeselect = 202
  EditUndo = 203
  EditRedo = 204
  EditCut = 205
  EditCopy = 206
  EditPaste = 207
  EditSelectAll = 208
  ViewResetZoom = 301
  RunPlay = 401
  RunPlaySelected = 402
  RunStop = 403


@dataclass(eq=False, repr=False)
class UIFlowShell:
  win: UIWindow = new()
  menu: UIMenuBar = new()
  palette: UIFlowPalette = new()
  canvas: UIFlowCanvas = new()
  catalog: FlowNodeCatalog = new()
  tooltip: UITooltipHost = new()
  doc_path: str = ""
  bound_canvas_ptr: int64 @optional = 0
  run_play: UIEvent = new()
  run_play_selected: UIEvent = new()
  run_stop: UIEvent = new()

  @native
  def register_shell(self, win: UIWindow @ref) -> None:
    """在真实 ``UIWindow`` 上注册 ``this``（``self.win`` 为值拷贝，不可写 ``flow_shell_ptr``）。"""
    ...

  @native
  def bind_canvas(self, win: UIWindow @ref, canvas: UIFlowCanvas @ref) -> None:
    """``attach`` 后在真实 ``UIWindow`` 与画布上登记指针（``self.win`` 为值拷贝）。"""
    ...

  @native
  def invalidate_all(self) -> None:
    """刷新 palette 与 ``bound_canvas_ptr`` 指向的画布。"""
    ...

  @native
  def layout_shell(self) -> None:
    """按客户区排列 palette / canvas 子窗口。"""
    ...

  @native
  def run_canvas_menu(self, cmd_id: int) -> None:
    """经 ``_canvas_ptr`` 执行编辑/视图菜单（避免 ``self.canvas`` 值拷贝）。"""
    ...

  @native
  def bound_file_new(self) -> None:
    """File → New（绑定画布）。"""
    ...

  @native
  def bound_file_open(self, text: str) -> None:
    """载入 ``.flow.json`` 文本到绑定画布并清空历史。"""
    ...

  @native
  def bound_file_save(self) -> str:
    """绑定画布 → JSON；无节点时返回空串。"""
    ...

  def attach(self, win: UIWindow @ref, canvas: UIFlowCanvas @ref) -> None:
    self.win = win
    self.register_shell(win)
    self.menu.attach(win)
    self.menu.build_flow_default()
    self.tooltip.attach(win)
    canvas.catalog = self.catalog
    canvas.font.size = canvas.style.font_size
    self.palette.catalog = self.catalog
    self.palette.style = canvas.style
    self.palette.zoom = 1.0
    self.palette.font.size = canvas.style.palette_font_size
    self.palette.rebuild_groups()
    self.palette.mount(win, 0, 0, PALETTE_WIDTH, 100)
    canvas.mount(win, PALETTE_WIDTH, 0, 100, 100)
    self.bind_canvas(win, canvas)
    self.palette.bind_canvas(canvas)
    self.layout_shell()
    self.invalidate_all()

  def layout(self) -> None:
    self.layout_shell()
    self.invalidate_all()

  def on_menu_command(self, cmd_id: int) -> None:
    empty: str = ""
    match cmd_id:
      case 1:
        self.bound_file_new()
        self.doc_path = empty
      case 2:
        picked: str = pick_open_file("Open Flow", ".flow.json")
        if picked != empty:
          doc: Path = new(picked)
          self.bound_file_open(doc.read_text())
          self.doc_path = picked
      case 3:
        if self.doc_path != empty:
          save_doc: Path = new(self.doc_path)
          save_doc.write_text(self.bound_file_save())
      case 4:
        picked_as: str = pick_save_file("Save Flow As", ".flow.json", "untitled.flow.json")
        if picked_as != empty:
          as_doc: Path = new(picked_as)
          as_doc.write_text(self.bound_file_save())
          self.doc_path = picked_as
      case 100:
        self.win.close()
      case 201:
        self.run_canvas_menu(cmd_id)
      case 202:
        self.run_canvas_menu(cmd_id)
      case 203:
        self.run_canvas_menu(cmd_id)
      case 204:
        self.run_canvas_menu(cmd_id)
      case 205:
        self.run_canvas_menu(cmd_id)
      case 206:
        self.run_canvas_menu(cmd_id)
      case 207:
        self.run_canvas_menu(cmd_id)
      case 208:
        self.run_canvas_menu(cmd_id)
      case 301:
        self.run_canvas_menu(cmd_id)
      case 401:
        self.run_play()
      case 402:
        self.run_play_selected()
      case 403:
        self.run_stop()
      case _:
        pass

  def on_flow_run(self) -> None:
    pass

  def on_flow_run_from_selected(self) -> None:
    pass

  def on_flow_stop(self) -> None:
    pass
