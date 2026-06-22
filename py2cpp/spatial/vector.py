"""游戏数学：``Vector2`` / ``Vector3`` / ``Vector4``（对齐 tggame ``linalg``）。"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import IndexError
from ..math import (
  acos,
  asin,
  atan2,
  cos,
  degrees,
  almost,
  lerp,
  pow,
  radians,
  sin,
  sqrt,
)


@copyable
@mixin
class VectorMixin:
  """``Vector2`` / ``Vector3`` / ``Vector4`` 公共 API（分量存于 ``_data`` 栈数组）。"""

  _dim: int @const = 0
  _data: float64[:Self._dim]

  def _copy_from(self, src: Self) -> None:
    for i in inline_range(Self._dim):
      self._data.unsafe_set(i, src._data.unsafe_get(i))

  @immutable
  def __len__(self) -> int:
    return Self._dim

  @immutable
  def __getitem__(self, index: int) -> float64:
    if index < 0 or index >= Self._dim:
      raise IndexError("vector index out of range")
    return self._data.unsafe_get(index)

  def __setitem__(self, index: int, value: float64) -> None:
    if index < 0 or index >= Self._dim:
      raise IndexError("vector index out of range")
    self._data.unsafe_set(index, value)

  @immutable
  def unsafe_get(self, index: int) -> float64:
    return self._data.unsafe_get(index)

  def unsafe_set(self, index: int, value: float64) -> None:
    self._data.unsafe_set(index, value)

  @staticproperty
  @immutable
  def zero() -> Self:
    return new()

  @staticproperty
  @immutable
  def one() -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(i, 1.0)
    return out

  @property
  @immutable
  def sqr_mag(self) -> float64:
    return self.dot(self)

  @property.setter
  def sqr_mag(self, sqr_mag: float64) -> None:
    self.mag = sqrt(sqr_mag)

  @property
  @immutable
  def mag(self) -> float64:
    return sqrt(self.sqr_mag)

  @property.setter
  def mag(self, mag: float64) -> None:
    self._copy_from(self.with_mag(mag))

  @property
  @immutable
  def norm(self) -> Self:
    return self.with_mag(1.0)

  @immutable
  def dot(self, other: Self) -> float64:
    acc: float64 = 0.0
    for i in inline_range(Self._dim):
      acc += self._data.unsafe_get(i) * other._data.unsafe_get(i)
    return acc

  @immutable
  def scaled(self, other: Self) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(
        i,
        self._data.unsafe_get(i) * other._data.unsafe_get(i),
      )
    return out

  def scale(self, other: Self) -> None:
    for i in inline_range(Self._dim):
      self._data.unsafe_set(
        i,
        self._data.unsafe_get(i) * other._data.unsafe_get(i),
      )

  @immutable
  def inv_scaled(self, other: Self) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(
        i,
        self._data.unsafe_get(i) / other._data.unsafe_get(i),
      )
    return out

  def inv_scale(self, other: Self) -> None:
    for i in inline_range(Self._dim):
      self._data.unsafe_set(
        i,
        self._data.unsafe_get(i) / other._data.unsafe_get(i),
      )

  @immutable
  def pow_scaled(self, exponent: float64) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(i, pow(self._data.unsafe_get(i), exponent))
    return out

  def pow_scale(self, exponent: float64) -> None:
    for i in inline_range(Self._dim):
      self._data.unsafe_set(i, pow(self._data.unsafe_get(i), exponent))

  @property
  @immutable
  def inv(self) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(i, 1.0 / self._data.unsafe_get(i))
    return out

  @immutable
  def with_mag(self, mag: float64) -> Self:
    rate: float64 = abs(self)
    z: float64 = 0.0
    if almost(rate, z):
      return new.zero
    return self * (mag / rate)

  def normalize(self) -> None:
    self._copy_from(self.norm)

  @immutable
  def clamped(self, min_mag: float64, max_mag: float64) -> Self:
    sq: float64 = self.sqr_mag
    if sq < min_mag * min_mag:
      return self.with_mag(min_mag)
    if sq > max_mag * max_mag:
      return self.with_mag(max_mag)
    return self

  def clamp(self, min_mag: float64, max_mag: float64) -> None:
    self._copy_from(self.clamped(min_mag, max_mag))

  @immutable
  def sqr_dist_to(self, other: Self) -> float64:
    d: Self = self - other
    return d.dot(d)

  @immutable
  def dist_to(self, other: Self) -> float64:
    return sqrt(self.sqr_dist_to(other))

  @immutable
  def moved_towards(self, target: Self, delta: float64) -> Self:
    dist: float64 = self.dist_to(target)
    z: float64 = 0.0
    if almost(dist, z):
      return self
    return self.lerp(target, delta / dist)

  def move_towards(self, target: Self, delta: float64) -> None:
    self._copy_from(self.moved_towards(target, delta))

  @immutable
  def angle_to(self, other: Self) -> float64:
    denom: float64 = sqrt(self.sqr_mag * other.sqr_mag)
    return degrees(acos(self.dot(other) / denom))

  @immutable
  def rotated_towards(self, target: Self, delta: float64) -> Self:
    ang: float64 = self.angle_to(target)
    z: float64 = 0.0
    if almost(ang, z):
      return self
    return self.slerp(target, delta / ang)

  def rotate_towards(self, target: Self, delta: float64) -> None:
    self._copy_from(self.rotated_towards(target, delta))

  @immutable
  def project(self, other: Self) -> Self:
    rate: float64 = other.sqr_mag
    z: float64 = 0.0
    if almost(rate, z):
      return new.zero
    s: float64 = self.dot(other) / rate
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(i, other._data.unsafe_get(i) * s)
    return out

  @immutable
  def reflect(self, other: Self) -> Self:
    p: Self = self.project(other)
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(
        i,
        self._data.unsafe_get(i) - 2.0 * p._data.unsafe_get(i),
      )
    return out

  @immutable
  def lerp(self, other: Self, t: float64) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(
        i,
        lerp(self._data.unsafe_get(i), other._data.unsafe_get(i), t),
      )
    return out

  @immutable
  def slerp(self, other: Self, t: float64) -> Self:
    theta: float64 = radians(self.angle_to(other))
    sin_theta: float64 = sin(theta)
    z: float64 = 0.0
    if almost(sin_theta, z):
      return self
    w0: float64 = sin((1.0 - t) * theta) / sin_theta
    w1: float64 = sin(t * theta) / sin_theta
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(
        i,
        self._data.unsafe_get(i) * w0 + other._data.unsafe_get(i) * w1,
      )
    return out

  @immutable
  def xlerp(self, other: Self, t: float64) -> Self:
    return self.scaled(other.inv_scaled(self).pow_scaled(t))

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in inline_range(Self._dim):
      if not almost(self._data.unsafe_get(i), other._data.unsafe_get(i)):
        return False
    return True

  @immutable
  def __bool__(self) -> bool:
    return self != new.zero

  @immutable
  def __pos__(self) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(i, self._data.unsafe_get(i))
    return out

  @immutable
  def __neg__(self) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(i, -self._data.unsafe_get(i))
    return out

  @immutable
  def __add__(self, other: Self) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(
        i,
        self._data.unsafe_get(i) + other._data.unsafe_get(i),
      )
    return out

  def __iadd__(self, other: Self) -> Self:
    for i in inline_range(Self._dim):
      self._data.unsafe_set(
        i,
        self._data.unsafe_get(i) + other._data.unsafe_get(i),
      )
    return self

  @immutable
  def __sub__(self, other: Self) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(
        i,
        self._data.unsafe_get(i) - other._data.unsafe_get(i),
      )
    return out

  def __isub__(self, other: Self) -> Self:
    for i in inline_range(Self._dim):
      self._data.unsafe_set(
        i,
        self._data.unsafe_get(i) - other._data.unsafe_get(i),
      )
    return self

  @overload
  @immutable
  def __mul__(self, other: Self) -> float64:
    return self.dot(other)

  @overload
  @immutable
  def __mul__(self, other: float64) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(i, self._data.unsafe_get(i) * other)
    return out

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  def __imul__(self, other: float64) -> Self:
    for i in inline_range(Self._dim):
      self._data.unsafe_set(i, self._data.unsafe_get(i) * other)
    return self

  @immutable
  def __invert__(self) -> Self:
    return self.inv

  @immutable
  def __truediv__(self, other: float64) -> Self:
    s: float64 = 1.0 / other
    return self * s

  def __itruediv__(self, other: float64) -> Self:
    s: float64 = 1.0 / other
    for i in inline_range(Self._dim):
      self._data.unsafe_set(i, self._data.unsafe_get(i) * s)
    return self

  @immutable
  def __abs__(self) -> float64:
    return self.mag

  @immutable
  def __mod__(self, mag: float64) -> Self:
    return self.with_mag(mag)

  def __imod__(self, mag: float64) -> Self:
    self._copy_from(self.with_mag(mag))
    return self

  @immutable
  def __xor__(self, other: Self) -> float64:
    return self.dist_to(other)


class Vector2(VectorMixin):
  """二维向量 ``(x, y)``。"""

  _dim: int @const = 2

  def __init__(self, x: float64 = 0.0, y: float64 = 0.0) -> None:
    self._data.unsafe_set(0, x)
    self._data.unsafe_set(1, y)

  @property
  @immutable
  def x(self) -> float64:
    return self._data.unsafe_get(0)

  @property.setter
  def x(self, value: float64) -> None:
    self._data.unsafe_set(0, value)

  @property
  @immutable
  def y(self) -> float64:
    return self._data.unsafe_get(1)

  @property.setter
  def y(self, value: float64) -> None:
    self._data.unsafe_set(1, value)

  @staticproperty
  @immutable
  def right() -> Self:
    return new(1.0, 0.0)

  @staticproperty
  @immutable
  def down() -> Self:
    return new(0.0, 1.0)

  @staticmethod
  @immutable
  def from_polar(r: float64, phi: float64) -> Self:
    rad_phi: float64 = radians(phi)
    u: Self = new(cos(rad_phi), sin(rad_phi))
    return u * r

  @immutable
  def cross(self, other: Self) -> float64:
    return self.x * other.y - self.y * other.x

  @immutable
  def rotated(self, angle: float64) -> Self:
    rad_a: float64 = radians(angle)
    cos_a: float64 = cos(rad_a)
    sin_a: float64 = sin(rad_a)
    rx: float64 = self.x * cos_a - self.y * sin_a
    ry: float64 = self.x * sin_a + self.y * cos_a
    return new(rx, ry)

  def rotate(self, angle: float64) -> None:
    self._copy_from(self.rotated(angle))

  @immutable
  def rotated90(self) -> Self:
    return new(-self.y, self.x)

  def rotate90(self) -> None:
    self._copy_from(self.rotated90())

  @immutable
  def rotated_around(self, center: Self, angle: float64) -> Self:
    return (self - center).rotated(angle) + center

  def rotate_around(self, center: Self, angle: float64) -> None:
    self._copy_from(self.rotated_around(center, angle))

  @immutable
  def flipped(self, flip_x: bool = False, flip_y: bool = False) -> Self:
    return new(-self.x if flip_x else self.x, -self.y if flip_y else self.y)

  def flip(self, flip_x: bool = False, flip_y: bool = False) -> None:
    self._copy_from(self.flipped(flip_x, flip_y))

  @immutable
  def to_polar(self) -> Self:
    return new(abs(self), degrees(atan2(self.y, self.x)))

  @immutable
  def __matmul__(self, other: Self) -> float64:
    return self.cross(other)


class Vector3(VectorMixin):
  """三维向量 ``(x, y, z)``。"""

  _dim: int @const = 3

  def __init__(self, x: float64 = 0.0, y: float64 = 0.0, z: float64 = 0.0) -> None:
    self._data.unsafe_set(0, x)
    self._data.unsafe_set(1, y)
    self._data.unsafe_set(2, z)

  @property
  @immutable
  def x(self) -> float64:
    return self._data.unsafe_get(0)

  @property.setter
  def x(self, value: float64) -> None:
    self._data.unsafe_set(0, value)

  @property
  @immutable
  def y(self) -> float64:
    return self._data.unsafe_get(1)

  @property.setter
  def y(self, value: float64) -> None:
    self._data.unsafe_set(1, value)

  @property
  @immutable
  def z(self) -> float64:
    return self._data.unsafe_get(2)

  @property.setter
  def z(self, value: float64) -> None:
    self._data.unsafe_set(2, value)

  @staticproperty
  @immutable
  def right() -> Self:
    return new(1.0, 0.0, 0.0)

  @staticproperty
  @immutable
  def down() -> Self:
    return new(0.0, 1.0, 0.0)

  @staticproperty
  @immutable
  def forward() -> Self:
    return new(0.0, 0.0, 1.0)

  @staticmethod
  @immutable
  def from_spherical(r: float64, phi: float64, theta: float64) -> Self:
    rad_phi: float64 = radians(phi)
    rad_theta: float64 = radians(theta)
    sin_theta: float64 = sin(rad_theta)
    cos_theta: float64 = cos(rad_theta)
    cos_phi: float64 = cos(rad_phi)
    sin_phi: float64 = sin(rad_phi)
    p: float64 = sin_theta * r
    return new(p * cos_phi, p * sin_phi, cos_theta * r)

  @immutable
  def cross(self, other: Self) -> Self:
    return new(
      self.y * other.z - self.z * other.y,
      self.z * other.x - self.x * other.z,
      self.x * other.y - self.y * other.x,
    )

  @immutable
  def rotated_x(self, angle: float64) -> Self:
    rad_a: float64 = radians(angle)
    cos_a: float64 = cos(rad_a)
    sin_a: float64 = sin(rad_a)
    ry: float64 = self.y * cos_a - self.z * sin_a
    rz: float64 = self.y * sin_a + self.z * cos_a
    return new(self.x, ry, rz)

  def rotate_x(self, angle: float64) -> None:
    self._copy_from(self.rotated_x(angle))

  @immutable
  def rotated_y(self, angle: float64) -> Self:
    rad_a: float64 = radians(angle)
    cos_a: float64 = cos(rad_a)
    sin_a: float64 = sin(rad_a)
    rx: float64 = self.x * cos_a + self.z * sin_a
    rz: float64 = -self.x * sin_a + self.z * cos_a
    return new(rx, self.y, rz)

  def rotate_y(self, angle: float64) -> None:
    self._copy_from(self.rotated_y(angle))

  @immutable
  def rotated_z(self, angle: float64) -> Self:
    rad_a: float64 = radians(angle)
    cos_a: float64 = cos(rad_a)
    sin_a: float64 = sin(rad_a)
    rx: float64 = self.x * cos_a - self.y * sin_a
    ry: float64 = self.x * sin_a + self.y * cos_a
    return new(rx, ry, self.z)

  def rotate_z(self, angle: float64) -> None:
    self._copy_from(self.rotated_z(angle))

  @immutable
  def apply_quat(self, w: float64, qx: float64, qy: float64, qz: float64) -> Self:
    qv: Self = new(qx, qy, qz)
    t: Self = qv @ self
    t *= 2.0
    return self + t * w + (qv @ t)

  @immutable
  def rotated(self, axis: Self, angle: float64) -> Self:
    half: float64 = radians(angle * 0.5)
    w: float64 = cos(half)
    s: float64 = sin(half)
    n: Self = axis.norm
    return self.apply_quat(w, n.x * s, n.y * s, n.z * s)

  def rotate(self, axis: Self, angle: float64) -> None:
    self._copy_from(self.rotated(axis, angle))

  @immutable
  def rotated_around(self, center: Self, axis: Self, angle: float64) -> Self:
    return (self - center).rotated(axis, angle) + center

  def rotate_around(self, center: Self, axis: Self, angle: float64) -> None:
    self._copy_from(self.rotated_around(center, axis, angle))

  @immutable
  def rotated_euler_angles(self, euler_angles: Self) -> Self:
    ex: float64 = radians(euler_angles.x * 0.5)
    ey: float64 = radians(euler_angles.y * 0.5)
    ez: float64 = radians(euler_angles.z * 0.5)
    cos_x: float64 = cos(ex)
    sin_x: float64 = sin(ex)
    cos_y: float64 = cos(ey)
    sin_y: float64 = sin(ey)
    cos_z: float64 = cos(ez)
    sin_z: float64 = sin(ez)
    w: float64 = cos_x * cos_y * cos_z + sin_x * sin_y * sin_z
    qx: float64 = sin_x * cos_y * cos_z - cos_x * sin_y * sin_z
    qy: float64 = cos_x * sin_y * cos_z + sin_x * cos_y * sin_z
    qz: float64 = cos_x * cos_y * sin_z - sin_x * sin_y * cos_z
    return self.apply_quat(w, qx, qy, qz)

  def rotate_euler_angles(self, euler_angles: Self) -> None:
    self._copy_from(self.rotated_euler_angles(euler_angles))

  @immutable
  def flipped(
    self,
    flip_x: bool = False,
    flip_y: bool = False,
    flip_z: bool = False,
  ) -> Self:
    return new(
      -self.x if flip_x else self.x,
      -self.y if flip_y else self.y,
      -self.z if flip_z else self.z,
    )

  def flip(
    self,
    flip_x: bool = False,
    flip_y: bool = False,
    flip_z: bool = False,
  ) -> None:
    self._copy_from(self.flipped(flip_x, flip_y, flip_z))

  @immutable
  def to_spherical(self) -> Self:
    len_v: float64 = abs(self)
    return new(len_v, degrees(atan2(self.y, self.x)), degrees(acos(self.z / len_v)))

  @immutable
  def to_vector2(self) -> Vector2:
    return new(self.x, self.y)

  @immutable
  def __matmul__(self, other: Self) -> Self:
    return self.cross(other)

  def __imatmul__(self, other: Self) -> Self:
    self._copy_from(self.cross(other))
    return self


class Vector4(VectorMixin):
  """四维向量 ``(x, y, z, w)``。"""

  _dim: int @const = 4

  def __init__(
    self,
    x: float64 = 0.0,
    y: float64 = 0.0,
    z: float64 = 0.0,
    w: float64 = 0.0,
  ) -> None:
    self._data.unsafe_set(0, x)
    self._data.unsafe_set(1, y)
    self._data.unsafe_set(2, z)
    self._data.unsafe_set(3, w)

  @property
  @immutable
  def x(self) -> float64:
    return self._data.unsafe_get(0)

  @property.setter
  def x(self, value: float64) -> None:
    self._data.unsafe_set(0, value)

  @property
  @immutable
  def y(self) -> float64:
    return self._data.unsafe_get(1)

  @property.setter
  def y(self, value: float64) -> None:
    self._data.unsafe_set(1, value)

  @property
  @immutable
  def z(self) -> float64:
    return self._data.unsafe_get(2)

  @property.setter
  def z(self, value: float64) -> None:
    self._data.unsafe_set(2, value)

  @property
  @immutable
  def w(self) -> float64:
    return self._data.unsafe_get(3)

  @property.setter
  def w(self, value: float64) -> None:
    self._data.unsafe_set(3, value)

  @immutable
  def flipped(
    self,
    flip_x: bool = False,
    flip_y: bool = False,
    flip_z: bool = False,
    flip_w: bool = False,
  ) -> Self:
    return new(
      -self.x if flip_x else self.x,
      -self.y if flip_y else self.y,
      -self.z if flip_z else self.z,
      -self.w if flip_w else self.w,
    )

  def flip(
    self,
    flip_x: bool = False,
    flip_y: bool = False,
    flip_z: bool = False,
    flip_w: bool = False,
  ) -> None:
    self._copy_from(self.flipped(flip_x, flip_y, flip_z, flip_w))
