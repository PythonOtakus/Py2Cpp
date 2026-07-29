"""二维网格与 ``Navigatable[Cell]`` 适配（tilemap / A*）。"""
from ..builtins import *
from ..core.exceptions import IndexError, ValueError
from ..util.list import list
from ..util.mixins import ContainerMixin


@enum
class GridConnectivity:
  """四向 / 八向邻接（影响 ``GridNav.neighbors`` 与启发式）。"""

  Four = 0
  Eight = ...


@copyable
@dataclass(eq=True)
class Cell:
  """网格坐标：``x`` 列、``y`` 行（0-based）。"""

  x: int = 0
  y: int = 0

  @immutable
  def __hash__(self) -> int:
    return self.x ^ (self.y << 16)


class Grid2D(ContainerMixin):
  """``width`` × ``height`` 整数格；``0`` 墙，``>= 1`` 进入边权；``int[:,:]`` 存储。"""

  def __init__(self, width: int = 0, height: int = 0, fill: int = 0):
    if width < 0 or height < 0:
      raise ValueError("width and height must be non-negative")
    self._width: int = width
    self._height: int = height
    self._cells: int[:,:] = new(height, width)
    self.fill(fill)

  def __copy__(self, other: Self):
    self._ensure_active()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._width = other._width
    self._height = other._height
    self._cells = new(other._height, other._width)
    for y in range(other._height):
      for x in range(other._width):
        self._cells[y, x] = other._cells[y, x]

  def __move__(self, other: Self):
    self._ensure_active()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._width = other._width
    self._height = other._height
    self._cells = other._cells
    other._width = 0
    other._height = 0
    other._cells = new(0, 0)

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new(self._width, self._height, 0)
    out.__copy__(self)
    return out

  @immutable
  def get_width(self) -> int:
    return self._width

  @immutable
  def get_height(self) -> int:
    return self._height

  @immutable
  def in_bounds(self, x: int, y: int) -> bool:
    return 0 <= x < self._width and 0 <= y < self._height

  @immutable
  @immutable
  def get(self, x: int, y: int) -> int:
    if not self.in_bounds(x, y):
      raise IndexError("cell out of bounds")
    return self._cells[y, x]

  def set(self, x: int, y: int, value: int) -> None:
    if not self.in_bounds(x, y):
      raise IndexError("cell out of bounds")
    self._cells[y, x] = value

  @immutable
  def walkable(self, x: int, y: int) -> bool:
    if not self.in_bounds(x, y):
      return False
    return self.get(x, y) > 0

  def fill(self, value: int) -> None:
    h: int = self._height
    w: int = self._width
    for y in range(h):
      for x in range(w):
        self._cells[y, x] = value


class GridNav:
  """``Grid2D`` → ``Navigatable[Cell]``。"""

  def __init__(self, grid: Grid2D, connectivity: GridConnectivity):
    self._grid: Grid2D = grid
    self._conn: GridConnectivity = connectivity

  @immutable
  def vertex_count(self) -> int:
    return self._grid.get_width() * self._grid.get_height()

  @immutable
  def to_index(self, u: Cell) -> int:
    return u.y * self._grid.get_width() + u.x

  @immutable
  def from_index(self, i: int) -> Cell:
    w: int = self._grid.get_width()
    if w == 0:
      return new(0, 0)
    y: int = i // w
    x: int = i - y * w
    return new(x, y)

  @immutable
  def neighbors(self, u: Cell) -> list[Cell]:
    out: list[Cell] = []
    if not self._grid.walkable(u.x, u.y):
      return out
    dirs: list[Cell] = Self._dirs(self._conn)
    for d in dirs:
      nx: int = u.x + d.x
      ny: int = u.y + d.y
      if self._grid.walkable(nx, ny):
        out.append(Cell(nx, ny))
    return out

  @immutable
  def move_cost(self, u: Cell, v: Cell) -> int:
    c: int = self._grid.get(v.x, v.y)
    if self._conn == GridConnectivity.Eight and u.x != v.x and u.y != v.y:
      return c * 14 // 10
    return c

  @immutable
  def heuristic(self, u: Cell, goal: Cell) -> int:
    dx: int = u.x - goal.x
    if dx < 0:
      dx = -dx
    dy: int = u.y - goal.y
    if dy < 0:
      dy = -dy
    if self._conn == GridConnectivity.Four:
      return dx + dy
    mn: int = dx
    if dy < mn:
      mn = dy
    return 10 * (dx + dy) + 4 * mn

  @immutable
  @staticmethod
  def _dirs(conn: GridConnectivity) -> list[Cell]:
    four: list[Cell] = [
      Cell(0, -1),
      Cell(1, 0),
      Cell(0, 1),
      Cell(-1, 0),
    ]
    if conn == GridConnectivity.Four:
      return four
    eight: list[Cell] = []
    eight.extend(four)
    eight.append(Cell(-1, -1))
    eight.append(Cell(1, -1))
    eight.append(Cell(1, 1))
    eight.append(Cell(-1, 1))
    return eight
