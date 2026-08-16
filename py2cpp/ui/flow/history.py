"""FlowGraph 撤销 / 重做（JSON 快照栈）。"""
from ...builtins import *
from .model import FlowGraph
from .serialize import graphFromJson, graphToJson


HistoryLimit: int = 32


@dataclass(eq=False, repr=False)
class FlowGraphHistory:
  _undo: list[str, 0] @optional = []
  _redo: list[str, 0] @optional = []
  limit: int = 32

  def clear(self) -> None:
    for i in range(len(self._undo) - 1, -1, -1):
      self._undo.pop(i)
    for i in range(len(self._redo) - 1, -1, -1):
      self._redo.pop(i)

  def _trimUndo(self) -> None:
    while len(self._undo) > self.limit:
      self._undo.pop(0)

  def push(self, graph: FlowGraph @ref) -> None:
    self._undo.append(graphToJson(graph))
    self._trimUndo()
    for i in range(len(self._redo) - 1, -1, -1):
      self._redo.pop(i)

  def canUndo(self) -> bool:
    if self._undo:
      return True
    return False

  def canRedo(self) -> bool:
    if self._redo:
      return True
    return False

  def undo(self, graph: FlowGraph @ref) -> bool:
    if not self.canUndo():
      return False
    self._redo.append(graphToJson(graph))
    idx: int = len(self._undo) - 1
    snap: str = self._undo.pop(idx)
    graphFromJson(graph, snap)
    return True

  def redo(self, graph: FlowGraph @ref) -> bool:
    if not self.canRedo():
      return False
    self._undo.append(graphToJson(graph))
    idx: int = len(self._redo) - 1
    snap: str = self._redo.pop(idx)
    graphFromJson(graph, snap)
    return True
