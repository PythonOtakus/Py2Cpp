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

  def _copyFrom(self, src: Self) -> None:
    self._x = src._x
    self._y = src._y
    self._width = src._width
    self._height = src._height

  @staticmethod
  @immutable
  def fromPosSize(pos: Vector2, size: Vector2) -> Self:
    return new(pos.x, pos.y, size.x, size.y)

  @staticmethod
  @immutable
  def fromMinMax(posMin: Vector2, posMax: Vector2) -> Self:
    return new(posMin.x, posMin.y, posMax.x - posMin.x, posMax.y - posMin.y)

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
  def xMin(self) -> float64:
    if self._width < 0.0:
      return self._x + self._width
    return self._x

  @property
  @immutable
  def yMin(self) -> float64:
    if self._height < 0.0:
      return self._y + self._height
    return self._y

  @property
  @immutable
  def xMax(self) -> float64:
    if self._width < 0.0:
      return self._x
    return self._x + self._width

  @property
  @immutable
  def yMax(self) -> float64:
    if self._height < 0.0:
      return self._y
    return self._y + self._height

  @property
  @immutable
  def posMin(self) -> Vector2:
    return new(self.xMin, self.yMin)

  @property
  @immutable
  def posMax(self) -> Vector2:
    return new(self.xMax, self.yMax)

  @property
  @immutable
  def center(self) -> Vector2:
    return new(
      (self.xMin + self.xMax) * 0.5,
      (self.yMin + self.yMax) * 0.5,
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
      self.xMin <= point.x
      and point.x <= self.xMax
      and self.yMin <= point.y
      and point.y <= self.yMax
    )

  @immutable
  def __contains__(self, point: Vector2) -> bool:
    return self.contains(point)

  @immutable
  def overlaps(self, other: Self) -> bool:
    return not (
      self.xMax < other.xMin
      or other.xMax < self.xMin
      or self.yMax < other.yMin
      or other.yMax < self.yMin
    )

  @immutable
  def embraces(self, other: Self) -> bool:
    return (
      self.xMin <= other.xMin
      and other.xMax <= self.xMax
      and self.yMin <= other.yMin
      and other.yMax <= self.yMax
    )

  @immutable
  def intersect(self, other: Self) -> Self:
    if not self.overlaps(other):
      return new()
    x0: float64 = self.xMin
    if other.xMin > x0:
      x0 = other.xMin
    y0: float64 = self.yMin
    if other.yMin > y0:
      y0 = other.yMin
    x1: float64 = self.xMax
    if other.xMax < x1:
      x1 = other.xMax
    y1: float64 = self.yMax
    if other.yMax < y1:
      y1 = other.yMax
    return new(x0, y0, x1 - x0, y1 - y0)

  @immutable
  def union(self, other: Self) -> Self:
    a: Self = self.corrected()
    b: Self = other.corrected()
    if not a:
      return new(b._x, b._y, b._width, b._height)
    if not b:
      return new(a._x, a._y, a._width, a._height)
    x0: float64 = a.xMin
    if b.xMin < x0:
      x0 = b.xMin
    y0: float64 = a.yMin
    if b.yMin < y0:
      y0 = b.yMin
    x1: float64 = a.xMax
    if b.xMax > x1:
      x1 = b.xMax
    y1: float64 = a.yMax
    if b.yMax > y1:
      y1 = b.yMax
    return new(x0, y0, x1 - x0, y1 - y0)

  @immutable
  def __and__(self, other: Self) -> Self:
    return self.intersect(other)

  def __iand__(self, other: Self) -> Self:
    self._copyFrom(self.intersect(other))
    return self

  @immutable
  def __or__(self, other: Self) -> Self:
    return self.union(other)

  def __ior__(self, other: Self) -> Self:
    self._copyFrom(self.union(other))
    return self

  @immutable
  def applyMatrix(self, matrix: Matrix3) -> Self:
    """变换四角后取 AABB 外包。"""
    p0: Vector2 = new(self.xMin, self.yMin)
    p1: Vector2 = new(self.xMax, self.yMin)
    p2: Vector2 = new(self.xMin, self.yMax)
    p3: Vector2 = new(self.xMax, self.yMax)
    c0: Vector2 = matrix.applyToPoint(p0)
    c1: Vector2 = matrix.applyToPoint(p1)
    c2: Vector2 = matrix.applyToPoint(p2)
    c3: Vector2 = matrix.applyToPoint(p3)
    minX: float64 = c0.x
    maxX: float64 = c0.x
    minY: float64 = c0.y
    maxY: float64 = c0.y
    if c1.x < minX:
      minX = c1.x
    if c1.x > maxX:
      maxX = c1.x
    if c1.y < minY:
      minY = c1.y
    if c1.y > maxY:
      maxY = c1.y
    if c2.x < minX:
      minX = c2.x
    if c2.x > maxX:
      maxX = c2.x
    if c2.y < minY:
      minY = c2.y
    if c2.y > maxY:
      maxY = c2.y
    if c3.x < minX:
      minX = c3.x
    if c3.x > maxX:
      maxX = c3.x
    if c3.y < minY:
      minY = c3.y
    if c3.y > maxY:
      maxY = c3.y
    return new(minX, minY, maxX - minX, maxY - minY)

  @immutable
  def __repr__(self) -> str:
    return "Rect(%s,%s,%s,%s)" % (self._x, self._y, self._width, self._height)
