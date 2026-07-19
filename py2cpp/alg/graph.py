"""邻接表与 ``Navigatable[int]`` 适配。"""
from ..builtins import *
from ..core.exceptions import IndexError, ValueError
from ..util.list import list
from ..util.mixins import ContainerMixin


@dataclass
class Edge:
  to: int
  w: int = 1


class AdjList(ContainerMixin):
  """有向邻接表；顶点 ``0 .. n-1``。"""

  def __init__(self, n: int = 0):
    if n < 0:
      raise ValueError("n must be non-negative")
    self._n: int = n
    adj: list[list[Edge]] = []
    self._adj: list[list[Edge]] = adj
    for i in range(n):
      row: list[Edge] = []
      self._adj.append(row)

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    self._n = other._n
    adj: list[list[Edge]] = []
    self._adj = adj
    for i in range(other._n):
      row: list[Edge] = []
      src: list[Edge] = other._adj[i]
      for j in range(len(src)):
        row.append(Edge(src[j].to, src[j].w))
      self._adj.append(row)

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    self._n = other._n
    self._adj = other._adj
    other._n = 0
    other._adj = []

  @immutable
  def vertex_count(self) -> int:
    return self._n

  def add_edge(self, u: int, v: int, w: int = 1) -> None:
    if u < 0 or u >= self._n or v < 0 or v >= self._n:
      raise IndexError("vertex out of range")
    self._adj[u].append(Edge(v, w))

  def add_undirected(self, u: int, v: int, w: int = 1) -> None:
    self.add_edge(u, v, w)
    self.add_edge(v, u, w)

  @immutable
  def neighbors(self, u: int) -> list[Edge]:
    if u < 0 or u >= self._n:
      raise IndexError("vertex out of range")
    return self._adj[u]


class GraphNav:
  """``AdjList`` → ``Navigatable[int]``；``h`` 为启发式查表（可传空 ``list``）。"""

  def __init__(self, graph: AdjList, h: list[int]):
    self._g: AdjList = graph
    heur: list[int] = []
    self._h: list[int] = heur
    for i in range(len(h)):
      self._h.append(h[i])

  @immutable
  def vertex_count(self) -> int:
    return self._g.vertex_count()

  @immutable
  def to_index(self, u: int) -> int:
    return u

  @immutable
  def from_index(self, i: int) -> int:
    return i

  @immutable
  def neighbors(self, u: int) -> list[int]:
    edges: list[Edge] = self._g.neighbors(u)
    out: list[int] = []
    for e in edges:
      out.append(e.to)
    return out

  @immutable
  def move_cost(self, u: int, v: int) -> int:
    edges: list[Edge] = self._g.neighbors(u)
    for e in edges:
      if e.to == v:
        return e.w
    return 1_000_000_000

  @immutable
  def heuristic(self, u: int, goal: int) -> int:
    if u < 0 or u >= len(self._h):
      return 0
    return self._h[u]
