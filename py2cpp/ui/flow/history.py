"""FlowGraph 撤销 / 重做（JSON 快照栈）。"""
from ...builtins import *
from .model import FlowGraph
from .serialize import graph_from_json, graph_to_json


HISTORY_LIMIT: int = 32


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

  def _trim_undo(self) -> None:
    while len(self._undo) > self.limit:
      self._undo.pop(0)

  def push(self, graph: FlowGraph @ref) -> None:
    self._undo.append(graph_to_json(graph))
    self._trim_undo()
    for i in range(len(self._redo) - 1, -1, -1):
      self._redo.pop(i)

  def can_undo(self) -> bool:
    if self._undo:
      return True
    return False

  def can_redo(self) -> bool:
    if self._redo:
      return True
    return False

  def undo(self, graph: FlowGraph @ref) -> bool:
    if not self.can_undo():
      return False
    self._redo.append(graph_to_json(graph))
    idx: int = len(self._undo) - 1
    snap: str = self._undo.pop(idx)
    graph_from_json(graph, snap)
    return True

  def redo(self, graph: FlowGraph @ref) -> bool:
    if not self.can_redo():
      return False
    self._undo.append(graph_to_json(graph))
    idx: int = len(self._redo) - 1
    snap: str = self._redo.pop(idx)
    graph_from_json(graph, snap)
    return True
