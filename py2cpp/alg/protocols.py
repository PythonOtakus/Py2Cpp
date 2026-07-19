"""``alg`` 域协议：可寻路图抽象（``Navigatable``）。"""
from ..builtins import *
from ..core.protocols import protocol
from ..util.protocols import DictKey


@protocol
class Navigatable[Node: DictKey]:
  """网格 / 邻接表等结构的统一寻路接口；节点类型 ``Node``。"""

  def vertex_count(self) -> int: ...

  def to_index(self, u: Node) -> int: ...

  def from_index(self, i: int) -> Node: ...

  def neighbors(self, u: Node) -> list[Node]: ...

  def move_cost(self, u: Node, v: Node) -> int: ...

  def heuristic(self, u: Node, goal: Node) -> int: ...
