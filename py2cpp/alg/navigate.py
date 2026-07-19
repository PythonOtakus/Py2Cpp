"""寻路：``astar`` / ``dijkstra``（仅依赖 ``Navigatable``）。"""
from ..builtins import *
from ..util.protocols import DictKey
from ..util.list import list
from .heap import Heap
from .protocols import Navigatable


_SEARCH_INF: int = 2_000_000_000


@dataclass(eq=True, order=True)
class _OpenEntry:
  f: int = 0
  tie: int = 0
  i: int = 0


def astar[Node: DictKey](nav: Navigatable[Node], start: Node, goal: Node) -> list[Node]:
  """A*；不可达或非法起终点 → 空 ``list``。"""
  return _search(nav, start, goal, True)


def dijkstra[Node: DictKey](nav: Navigatable[Node], start: Node, goal: Node) -> list[Node]:
  """Dijkstra（``heuristic`` 恒忽略，按 ``g`` 扩展）。"""
  return _search(nav, start, goal, False)


@immutable
def _search[Node: DictKey](
  nav: Navigatable[Node],
  start: Node,
  goal: Node,
  use_heuristic: bool,
) -> list[Node]:
  n: int = nav.vertex_count()
  if n == 0:
    none_path: list[Node] = []
    return none_path
  si: int = nav.to_index(start)
  gi: int = nav.to_index(goal)
  if si < 0 or si >= n or gi < 0 or gi >= n:
    none_path: list[Node] = []
    return none_path
  if si == gi:
    out: list[Node] = []
    out.append(start)
    return out

  g: list[int] = []
  parent: list[int] = []
  closed: list[bool] = []
  for i in range(n):
    g.append(_SEARCH_INF)
    parent.append(-1)
    closed.append(False)

  open_heap: Heap[_OpenEntry] = new()
  g[si] = 0
  h0: int = 0
  if use_heuristic:
    h0 = nav.heuristic(start, goal)
  open_heap.push(_OpenEntry(h0, 0, si))
  tie: int = 1

  while open_heap:
    entry: _OpenEntry = open_heap.pop()
    ui: int = entry.i
    if closed[ui]:
      continue
    want_f: int = g[ui]
    if use_heuristic:
      want_f += nav.heuristic(nav.from_index(ui), goal)
    if entry.f != want_f:
      continue
    if ui == gi:
      return _reconstruct(nav, parent, si, gi, goal)
    closed[ui] = True
    u: Node = nav.from_index(ui)
    for v in nav.neighbors(u):
      vi: int = nav.to_index(v)
      if vi < 0 or vi >= n:
        continue
      tentative: int = g[ui] + nav.move_cost(u, v)
      if tentative < g[vi]:
        parent[vi] = ui
        g[vi] = tentative
        f: int = tentative
        if use_heuristic:
          f = tentative + nav.heuristic(v, goal)
        open_heap.push(_OpenEntry(f, tie, vi))
        tie += 1

  empty: list[Node] = []
  return empty


@immutable
def _reconstruct[Node: DictKey](
  nav: Navigatable[Node],
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
    rev.append(nav.from_index(cur))
    cur = parent[cur]
  rev.append(nav.from_index(si))
  out: list[Node] = []
  for k in range(len(rev) - 1, -1, -1):
    out.append(rev[k])
  return out
