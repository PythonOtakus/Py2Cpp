"""编辑器壳：Hierarchy 画布 + Inspector Panel（双窗最小布局）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.ui.app import UIApp
from py2cpp.ui.window import UIWindow

from .hierarchy import HierarchyView
from .inspector import InspectorPanel
from .session import EditorSession

HIER_W: int = 280
HIER_H: int = 480


@refcount
class EditorShell:
  """无 UI 嵌 GL；Hierarchy 左窗自绘，Inspector 右窗 Panel。"""

  session: EditorSession = new()
  hierarchy: HierarchyView = new()
  inspector: InspectorPanel = new()
  hier_win: UIWindow = new()
  insp_win: UIWindow = new()

  def __init__(self):
    self.session = new()
    self.hierarchy = new()
    self.inspector = new()
    self.hier_win = new()
    self.insp_win = new()

  def sync_views(self) -> None:
    self.session.rebuild_hierarchy()
    self.hierarchy.refresh_from(self.session.rows, self.session.bus)
    self.inspector.bind_bus(self.session.bus)
    self.inspector.load_from_selection()

  def on_hierarchy_select(self, name: str) -> None:
    self.inspector.bind_bus(self.session.bus)
    self.inspector.load_from_selection()
    if self.insp_win.handle != 0:
      self.inspector.draw_panel(self.insp_win)

  def open(self) -> bool:
    if not UIApp.is_available():
      return False
    self.sync_views()
    self.hier_win.title = "Zeus Hierarchy"
    self.hier_win.show(HIER_W, HIER_H)
    self.hierarchy.mount(self.hier_win, 0, 0, -1, -1)
    self.hierarchy.selection_changed += self.on_hierarchy_select
    self.hierarchy.refresh_from(self.session.rows, self.session.bus)
    self.insp_win.title = "Zeus Inspector"
    self.insp_win.show(360, 420)
    self.inspector.bind_bus(self.session.bus)
    self.inspector.load_from_selection()
    self.inspector.draw_panel(self.insp_win)
    return True

  def close(self) -> None:
    if self.hier_win.handle != 0:
      self.hier_win.close()
    if self.insp_win.handle != 0:
      self.insp_win.close()

  def run(self) -> int:
    if not self.open():
      return 1
    code: int = UIApp.run()
    self.close()
    return code
