"""寻路：``astar`` / ``dijkstra``（仅依赖 ``NavigatableType``）。"""
from ..builtins import *
from ..util.protocols import DictKeyType
from ..util.list import list
from .heap import Heap
from .protocols import NavigatableType


_SearchInf: int = 2_000_000_000


@dataclass(eq=True, order=True)
class _OpenEntry:
  f: int = 0
  tie: int = 0
  i: int = 0


def astar[Node: DictKeyType](nav: NavigatableType[Node], start: Node, goal: Node) -> list[Node]:
  """A*；不可达或非法起终点 → 空 ``list``。"""
  return _search(nav, start, goal, True)


def dijkstra[Node: DictKeyType](nav: NavigatableType[Node], start: Node, goal: Node) -> list[Node]:
  """Dijkstra（``heuristic`` 恒忽略，按 ``g`` 扩展）。"""
  return _search(nav, start, goal, False)


@immutable
def _search[Node: DictKeyType](
  nav: NavigatableType[Node],
  start: Node,
  goal: Node,
  useHeuristic: bool,
) -> list[Node]:
  n: int = nav.vertexCount()
  if n == 0:
    nonePath: list[Node] = []
    return nonePath
  si: int = nav.toIndex(start)
  gi: int = nav.toIndex(goal)
  if si < 0 or si >= n or gi < 0 or gi >= n:
    nonePath: list[Node] = []
    return nonePath
  if si == gi:
    out: list[Node] = []
    out.append(start)
    return out

  g: list[int] = []
  parent: list[int] = []
  closed: list[bool] = []
  for i in range(n):
    g.append(_SearchInf)
    parent.append(-1)
    closed.append(False)

  openHeap: Heap[_OpenEntry] = new()
  g[si] = 0
  h0: int = 0
  if useHeuristic:
    h0 = nav.heuristic(start, goal)
  openHeap.push(_OpenEntry(h0, 0, si))
  tie: int = 1

  while openHeap:
    entry: _OpenEntry = openHeap.pop()
    ui: int = entry.i
    if closed[ui]:
      continue
    wantF: int = g[ui]
    if useHeuristic:
      wantF += nav.heuristic(nav.fromIndex(ui), goal)
    if entry.f != wantF:
      continue
    if ui == gi:
      return _reconstruct(nav, parent, si, gi, goal)
    closed[ui] = True
    u: Node = nav.fromIndex(ui)
    for v in nav.neighbors(u):
      vi: int = nav.toIndex(v)
      if vi < 0 or vi >= n:
        continue
      tentative: int = g[ui] + nav.moveCost(u, v)
      if tentative < g[vi]:
        parent[vi] = ui
        g[vi] = tentative
        f: int = tentative
        if useHeuristic:
          f = tentative + nav.heuristic(v, goal)
        openHeap.push(_OpenEntry(f, tie, vi))
        tie += 1

  empty: list[Node] = []
  return empty


@immutable
def _reconstruct[Node: DictKeyType](
  nav: NavigatableType[Node],
  parent: list[int],
  si: int,
  gi: int,
  goal: Node,
) -> list[Node]:
  rev: list[Node] = []
  cur: int = gi
  while cur != si:
    if cur < 0 or cur >= len(parent) or parent[cur] < 0:
      empty: list[Node] = []
      return empty
    rev.append(nav.fromIndex(cur))
    cur = parent[cur]
  rev.append(nav.fromIndex(si))
  out: list[Node] = []
  for k in range(len(rev) - 1, -1, -1):
    out.append(rev[k])
  return out
