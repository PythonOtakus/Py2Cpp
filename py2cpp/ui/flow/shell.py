"""Flow 编辑器壳：菜单 + palette + 画布布局。"""
from ...builtins import *
from ...io.path import Path
from ..menu import UIMenuBar
from ..file_dialog import pickOpenFile, pickSaveFile
from ..tooltip import UITooltipHost
from ..events import UIEventDelegate
from ..window import UIWindow
from .canvas import UIFlowCanvas
from .catalog import FlowNodeCatalog
from .palette import UIFlowPalette
from .serialize import graphFromJson, graphToJson


PaletteWidth: int = 240


@enum
class FlowMenuIdEnum:
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
  docPath: str = ""
  boundCanvasPtr: int64 @optional = 0
  runPlay: UIEventDelegate = new()
  runPlaySelected: UIEventDelegate = new()
  runStop: UIEventDelegate = new()

  @native
  def registerShell(self, win: UIWindow @ref) -> None:
    """在真实 ``UIWindow`` 上注册 ``this``（``self.win`` 为值拷贝，不可写 ``flowShellPtr``）。"""
    ...

  @native
  def bindCanvas(self, win: UIWindow @ref, canvas: UIFlowCanvas @ref) -> None:
    """``attach`` 后在真实 ``UIWindow`` 与画布上登记指针（``self.win`` 为值拷贝）。"""
    ...

  @native
  def invalidateAll(self) -> None:
    """刷新 palette 与 ``boundCanvasPtr`` 指向的画布。"""
    ...

  @native
  def layoutShell(self) -> None:
    """按客户区排列 palette / canvas 子窗口。"""
    ...

  @native
  def runCanvasMenu(self, cmdId: int) -> None:
    """经 ``_canvasPtr`` 执行编辑/视图菜单（避免 ``self.canvas`` 值拷贝）。"""
    ...

  @native
  def boundFileNew(self) -> None:
    """File → New（绑定画布）。"""
    ...

  @native
  def boundFileOpen(self, text: str) -> None:
    """载入 ``.flow.json`` 文本到绑定画布并清空历史。"""
    ...

  @native
  def boundFileSave(self) -> str:
    """绑定画布 → JSON；无节点时返回空串。"""
    ...

  def attach(self, win: UIWindow @ref, canvas: UIFlowCanvas @ref) -> None:
    self.win = win
    self.registerShell(win)
    self.menu.attach(win)
    self.menu.buildFlowDefault()
    self.tooltip.attach(win)
    canvas.catalog = self.catalog
    canvas.font.size = canvas.style.fontSize
    self.palette.catalog = self.catalog
    self.palette.style = canvas.style
    self.palette.zoom = 1.0
    self.palette.font.size = canvas.style.paletteFontSize
    self.palette.rebuildGroups()
    self.palette.mount(win, 0, 0, PaletteWidth, 100)
    canvas.mount(win, PaletteWidth, 0, 100, 100)
    self.bindCanvas(win, canvas)
    self.palette.bindCanvas(canvas)
    self.layoutShell()
    self.invalidateAll()

  def layout(self) -> None:
    self.layoutShell()
    self.invalidateAll()

  def onMenuCommand(self, cmdId: int) -> None:
    empty: str = ""
    match cmdId:
      case 1:
        self.boundFileNew()
        self.docPath = empty
      case 2:
        picked: str = pickOpenFile("Open Flow", ".flow.json")
        if picked != empty:
          doc: Path = new(picked)
          self.boundFileOpen(doc.readText())
          self.docPath = picked
      case 3:
        if self.docPath != empty:
          saveDoc: Path = new(self.docPath)
          saveDoc.writeText(self.boundFileSave())
      case 4:
        pickedAs: str = pickSaveFile("Save Flow As", ".flow.json", "untitled.flow.json")
        if pickedAs != empty:
          asDoc: Path = new(pickedAs)
          asDoc.writeText(self.boundFileSave())
          self.docPath = pickedAs
      case 100:
        self.win.close()
      case 201:
        self.runCanvasMenu(cmdId)
      case 202:
        self.runCanvasMenu(cmdId)
      case 203:
        self.runCanvasMenu(cmdId)
      case 204:
        self.runCanvasMenu(cmdId)
      case 205:
        self.runCanvasMenu(cmdId)
      case 206:
        self.runCanvasMenu(cmdId)
      case 207:
        self.runCanvasMenu(cmdId)
      case 208:
        self.runCanvasMenu(cmdId)
      case 301:
        self.runCanvasMenu(cmdId)
      case 401:
        self.runPlay()
      case 402:
        self.runPlaySelected()
      case 403:
        self.runStop()
      case _:
        pass

  def onFlowRun(self) -> None:
    pass

  def onFlowRunFromSelected(self) -> None:
    pass

  def onFlowStop(self) -> None:
    pass
