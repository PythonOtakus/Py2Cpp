"""空间矩形：``Rect``（对齐 tggame ``rect`` 轴对齐子集）。"""
from __future__ import annotations

from ..builtins import *
from ..math import almost
from .matrix import Matrix3
from .vector import Vector2


@copyable
class Rect:
  """2D 轴对齐矩形 ``(x, y, width, height)``。"""

  def __init__(
    self,
    x: float64 = 0.0,
    y: float64 = 0.0,
    width: float64 = 0.0,
    height: float64 = 0.0,
  ):
    self._x: float64 = x
    self._y: float64 = y
    self._width: float64 = width
    self._height: float64 = height

  def _copy_from(self, src: Self) -> None:
    self._x = src._x
    self._y = src._y
    self._width = src._width
    self._height = src._height

  @staticmethod
  @immutable
  def from_pos_size(pos: Vector2, size: Vector2) -> Self:
    return new(pos.x, pos.y, size.x, size.y)

  @staticmethod
  @immutable
  def from_min_max(pos_min: Vector2, pos_max: Vector2) -> Self:
    return new(pos_min.x, pos_min.y, pos_max.x - pos_min.x, pos_max.y - pos_min.y)

  @property
  @immutable
  def x(self) -> float64:
    return self._x

  @property.setter
  def x(self, value: float64) -> None:
    self._x = value

  @property
  @immutable
  def y(self) -> float64:
    return self._y

  @property.setter
  def y(self, value: float64) -> None:
    self._y = value

  @property
  @immutable
  def width(self) -> float64:
    return self._width

  @property.setter
  def width(self, value: float64) -> None:
    self._width = value

  @property
  @immutable
  def height(self) -> float64:
    return self._height

  @property.setter
  def height(self, value: float64) -> None:
    self._height = value

  @property
  @immutable
  def pos(self) -> Vector2:
    return new(self._x, self._y)

  @property.setter
  def pos(self, value: Vector2) -> None:
    self._x = value.x
    self._y = value.y

  @property
  @immutable
  def size(self) -> Vector2:
    return new(self._width, self._height)

  @property.setter
  def size(self, value: Vector2) -> None:
    self._width = value.x
    self._height = value.y

  @property
  @immutable
  def x_min(self) -> float64:
    if self._width < 0.0:
      return self._x + self._width
    return self._x

  @property
  @immutable
  def y_min(self) -> float64:
    if self._height < 0.0:
      return self._y + self._height
    return self._y

  @property
  @immutable
  def x_max(self) -> float64:
    if self._width < 0.0:
      return self._x
    return self._x + self._width

  @property
  @immutable
  def y_max(self) -> float64:
    if self._height < 0.0:
      return self._y
    return self._y + self._height

  @property
  @immutable
  def pos_min(self) -> Vector2:
    return new(self.x_min, self.y_min)

  @property
  @immutable
  def pos_max(self) -> Vector2:
    return new(self.x_max, self.y_max)

  @property
  @immutable
  def center(self) -> Vector2:
    return new(
      (self.x_min + self.x_max) * 0.5,
      (self.y_min + self.y_max) * 0.5,
    )

  @property.setter
  def center(self, value: Vector2) -> None:
    self.correct()
    self._x = value.x - self._width * 0.5
    self._y = value.y - self._height * 0.5

  @immutable
  def __bool__(self) -> bool:
    return self._width != 0.0 and self._height != 0.0

  @immutable
  def __eq__(self, other: Self) -> bool:
    return (
      almost(self._x, other._x)
      and almost(self._y, other._y)
      and almost(self._width, other._width)
      and almost(self._height, other._height)
    )

  def correct(self) -> None:
    if self._width < 0.0:
      self._x += self._width
      self._width = -self._width
    if self._height < 0.0:
      self._y += self._height
      self._height = -self._height

  @immutable
  def corrected(self) -> Self:
    out: Self = new(self._x, self._y, self._width, self._height)
    out.correct()
    return out

  def move(self, delta: Vector2) -> None:
    self._x += delta.x
    self._y += delta.y

  @immutable
  def moved(self, delta: Vector2) -> Self:
    return new(self._x + delta.x, self._y + delta.y, self._width, self._height)

  def expand(self, delta: Vector2) -> None:
    self._x -= delta.x
    self._y -= delta.y
    self._width += delta.x * 2.0
    self._height += delta.y * 2.0

  @immutable
  def expanded(self, delta: Vector2) -> Self:
    return new(
      self._x - delta.x,
      self._y - delta.y,
      self._width + delta.x * 2.0,
      self._height + delta.y * 2.0,
    )

  @immutable
  def contains(self, point: Vector2) -> bool:
    return (
      self.x_min <= point.x
      and point.x <= self.x_max
      and self.y_min <= point.y
      and point.y <= self.y_max
    )

  @immutable
  def __contains__(self, point: Vector2) -> bool:
    return self.contains(point)

  @immutable
  def overlaps(self, other: Self) -> bool:
    return not (
      self.x_max < other.x_min
      or other.x_max < self.x_min
      or self.y_max < other.y_min
      or other.y_max < self.y_min
    )

  @immutable
  def embraces(self, other: Self) -> bool:
    return (
      self.x_min <= other.x_min
      and other.x_max <= self.x_max
      and self.y_min <= other.y_min
      and other.y_max <= self.y_max
    )

  @immutable
  def intersect(self, other: Self) -> Self:
    if not self.overlaps(other):
      return new()
    x0: float64 = self.x_min
    if other.x_min > x0:
      x0 = other.x_min
    y0: float64 = self.y_min
    if other.y_min > y0:
      y0 = other.y_min
    x1: float64 = self.x_max
    if other.x_max < x1:
      x1 = other.x_max
    y1: float64 = self.y_max
    if other.y_max < y1:
      y1 = other.y_max
    return new(x0, y0, x1 - x0, y1 - y0)

  @immutable
  def union(self, other: Self) -> Self:
    a: Self = self.corrected()
    b: Self = other.corrected()
    if not a:
      return new(b._x, b._y, b._width, b._height)
    if not b:
      return new(a._x, a._y, a._width, a._height)
    x0: float64 = a.x_min
    if b.x_min < x0:
      x0 = b.x_min
    y0: float64 = a.y_min
    if b.y_min < y0:
      y0 = b.y_min
    x1: float64 = a.x_max
    if b.x_max > x1:
      x1 = b.x_max
    y1: float64 = a.y_max
    if b.y_max > y1:
      y1 = b.y_max
    return new(x0, y0, x1 - x0, y1 - y0)

  @immutable
  def __and__(self, other: Self) -> Self:
    return self.intersect(other)

  def __iand__(self, other: Self) -> Self:
    self._copy_from(self.intersect(other))
    return self

  @immutable
  def __or__(self, other: Self) -> Self:
    return self.union(other)

  def __ior__(self, other: Self) -> Self:
    self._copy_from(self.union(other))
    return self

  @immutable
  def apply_matrix(self, matrix: Matrix3) -> Self:
    """变换四角后取 AABB 外包。"""
    p0: Vector2 = new(self.x_min, self.y_min)
    p1: Vector2 = new(self.x_max, self.y_min)
    p2: Vector2 = new(self.x_min, self.y_max)
    p3: Vector2 = new(self.x_max, self.y_max)
    c0: Vector2 = matrix.apply_to_point(p0)
    c1: Vector2 = matrix.apply_to_point(p1)
    c2: Vector2 = matrix.apply_to_point(p2)
    c3: Vector2 = matrix.apply_to_point(p3)
    min_x: float64 = c0.x
    max_x: float64 = c0.x
    min_y: float64 = c0.y
    max_y: float64 = c0.y
    if c1.x < min_x:
      min_x = c1.x
    if c1.x > max_x:
      max_x = c1.x
    if c1.y < min_y:
      min_y = c1.y
    if c1.y > max_y:
      max_y = c1.y
    if c2.x < min_x:
      min_x = c2.x
    if c2.x > max_x:
      max_x = c2.x
    if c2.y < min_y:
      min_y = c2.y
    if c2.y > max_y:
      max_y = c2.y
    if c3.x < min_x:
      min_x = c3.x
    if c3.x > max_x:
      max_x = c3.x
    if c3.y < min_y:
      min_y = c3.y
    if c3.y > max_y:
      max_y = c3.y
    return new(min_x, min_y, max_x - min_x, max_y - min_y)

  @immutable
  def __repr__(self) -> str:
    return "Rect(%s,%s,%s,%s)" % (self._x, self._y, self._width, self._height)
