"""编辑器壳：一体主窗（顶栏 + Hierarchy + Scene View + Inspector）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.ui.app import UIApp
from py2cpp.ui.window import UIWindow

from .hierarchy import HierarchyView
from .inspector import InspectorPanel
from .session import EditorSession
from .toolbar import ToolbarView
from .viewport import SceneViewport

MAIN_W: int = 1280
MAIN_H: int = 720
TOOLBAR_H: int = 36
HIER_W: int = 260
INSP_W: int = 320


@refcount
class EditorShell:
  """Unity 式单窗：Toolbar / Hierarchy / GL Scene View / Inspector。"""

  session: EditorSession = new()
  hierarchy: HierarchyView = new()
  inspector: InspectorPanel = new()
  toolbar: ToolbarView = new()
  viewport: SceneViewport = new()
  main_win: UIWindow = new()

  def __init__(self):
    self.session = new()
    self.hierarchy = new()
    self.inspector = new()
    self.toolbar = new()
    self.viewport = new()
    self.main_win = new()

  def sync_views(self) -> None:
    self.session.rebuild_hierarchy()
    self.hierarchy.refresh_from(self.session.rows, self.session.bus)
    self.inspector.bind_bus(self.session.bus)
    self.inspector.load_from_selection()
    self.toolbar.bind_bus(self.session.bus)
    self.viewport.bind_bus(self.session.bus)

  def on_hierarchy_select(self, name: str) -> None:
    self.inspector.bind_bus(self.session.bus)
    self.inspector.load_from_selection()
    if self.main_win.handle != 0:
      self.inspector.panel_sync_to_form()

  def _view_rect(self) -> (int, int, int, int):
    """中栏客户区 ``(x, y, w, h)``。"""
    cw, ch = self.main_win.client_size()
    if cw < 1:
      cw = MAIN_W
    if ch < 1:
      ch = MAIN_H
    x: int = HIER_W
    y: int = TOOLBAR_H
    w: int = cw - HIER_W - INSP_W
    h: int = ch - TOOLBAR_H
    if w < 1:
      w = 1
    if h < 1:
      h = 1
    return (x, y, w, h)

  def layout(self) -> None:
    if self.main_win.handle == 0:
      return
    cw, ch = self.main_win.client_size()
    if cw < 1 or ch < 1:
      return
    self.toolbar.set_bounds(0, 0, cw, TOOLBAR_H)
    body_h: int = ch - TOOLBAR_H
    if body_h < 1:
      body_h = 1
    self.hierarchy.set_bounds(0, TOOLBAR_H, HIER_W, body_h)
    vx, vy, vw, vh = self._view_rect()
    ox, oy = self.main_win.client_origin_screen()
    self.viewport.set_screen_bounds(ox + vx, oy + vy, vw, vh)
    self.toolbar.invalidate()
    self.hierarchy.invalidate()

  def open(self) -> bool:
    if not UIApp.is_available():
      return False
    self.sync_views()
    self.main_win.title = "Zeus Editor"
    self.main_win.style.form_origin_x = HIER_W + (MAIN_W - HIER_W - INSP_W) + 8
    self.main_win.style.form_origin_y = TOOLBAR_H
    self.main_win.style.edit_size = (200, 22)
    self.main_win.style.button_size = (200, 22)
    self.main_win.style.slider_size = (200, 22)
    self.main_win.show(MAIN_W, MAIN_H)
    self.toolbar.mount(self.main_win, 0, 0, MAIN_W, TOOLBAR_H)
    self.toolbar.bind_bus(self.session.bus)
    self.hierarchy.mount(self.main_win, 0, TOOLBAR_H, HIER_W, MAIN_H - TOOLBAR_H)
    self.hierarchy.selection_changed += self.on_hierarchy_select
    self.hierarchy.refresh_from(self.session.rows, self.session.bus)
    self.inspector.bind_bus(self.session.bus)
    self.inspector.load_from_selection()
    self.inspector.draw_panel(self.main_win)
    vw0: int = MAIN_W - HIER_W - INSP_W
    vh0: int = MAIN_H - TOOLBAR_H
    if not self.viewport.open(vw0, vh0):
      return False
    self.viewport.bind_bus(self.session.bus)
    self.layout()
    return True

  def close(self) -> None:
    self.viewport.close()
    if self.main_win.handle != 0:
      self.main_win.close()

  def run(self) -> int:
    if not self.open():
      return 1
    while True:
      code: int = UIApp.pump()
      if code == 0:
        break
      if code == 2:
        self.layout()
        self.viewport.render()
    self.close()
    return 0
