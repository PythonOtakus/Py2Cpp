"""``alg`` 域协议：可寻路图抽象（``NavigatableType``）。"""
from ..builtins import *
from ..core.protocols import protocol
from ..util.protocols import DictKeyType


@protocol
class NavigatableType[Node: DictKeyType]:
  """网格 / 邻接表等结构的统一寻路接口；节点类型 ``Node``。"""

  def vertexCount(self) -> int: ...

  def toIndex(self, u: Node) -> int: ...

  def fromIndex(self, i: int) -> Node: ...

  def neighbors(self, u: Node) -> list[Node]: ...

  def moveCost(self, u: Node, v: Node) -> int: ...

  def heuristic(self, u: Node, goal: Node) -> int: ...
