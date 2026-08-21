"""编辑器会话：选中同步、Hierarchy 行表。"""
from __future__ import annotations

from py2cpp import *

from ..command import CommandBus, CommandResult, ZeusCommandUnion
from ..scene import GameObject


@copyable
@dataclass
class HierarchyRow:
  name: str = ""
  depth: int = 0


@refcount
class EditorSession:
  """命令总线包装；维护 Hierarchy 扁平行与选中。"""

  bus: CommandBus
  rows: list[HierarchyRow, 0]

  def __init__(self):
    self.bus = new()
    self.rows = []

  def rebuild_hierarchy(self) -> None:
    for i in range(len(self.rows) - 1, -1, -1):
      self.rows.pop(i)
    names: list[str] = []
    depths: list[int] = []
    self.bus.world.root.append_hierarchy_names(names, depths, 0)
    for i in range(len(names)):
      row: HierarchyRow = new()
      row.name = names[i]
      row.depth = depths[i]
      self.rows.append(row)

  def dispatch(self, cmd: ZeusCommandUnion) -> CommandResult:
    r: CommandResult = self.bus.dispatch(cmd)
    match cmd:
      case new.ObjectCreate(_, _):
        self.rebuild_hierarchy()
      case new.ObjectDelete(_):
        self.rebuild_hierarchy()
      case new.ObjectRename(_, _):
        self.rebuild_hierarchy()
      case new.SceneLoad(_):
        self.rebuild_hierarchy()
      case new.SceneFromJson(_):
        self.rebuild_hierarchy()
      case _:
        pass
    return r

  def select_index(self, index: int) -> CommandResult:
    if index < 0 or index >= len(self.rows):
      r: CommandResult = new()
      r.ok = False
      r.message = "bad index"
      return r
    return self.dispatch(ZeusCommandUnion.EditorSelect(self.rows[index].name))
