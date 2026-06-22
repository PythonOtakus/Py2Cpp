"""平面 ``Rotator`` 与 ``Quaternion``（对齐 tggame ``Complex`` / ``Quaternion``）。"""
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
  radians,
  sin,
  sqrt,
)
from .vector import Vector2, Vector3


@copyable
@mixin
class RotatorMixin:
  """``Rotator`` / ``Quaternion`` 公共 API；``_data[0]`` 为实部 ``w``。"""

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
      raise IndexError("rotator index out of range")
    return self._data.unsafe_get(index)

  def __setitem__(self, index: int, value: float64) -> None:
    if index < 0 or index >= Self._dim:
      raise IndexError("rotator index out of range")
    self._data.unsafe_set(index, value)

  @immutable
  def unsafe_get(self, index: int) -> float64:
    return self._data.unsafe_get(index)

  def unsafe_set(self, index: int, value: float64) -> None:
    self._data.unsafe_set(index, value)

  @staticproperty
  @immutable
  def zero() -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      out._data.unsafe_set(i, 0.0)
    return out

  @staticproperty
  @immutable
  def identity() -> Self:
    return new()

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
  def with_mag(self, mag: float64) -> Self:
    rate: float64 = abs(self)
    z: float64 = 0.0
    if almost(rate, z):
      return new.zero
    return self * (mag / rate)

  def normalize(self) -> None:
    self._copy_from(self.norm)

  @immutable
  def conjugate(self) -> Self:
    out: Self = new()
    for i in inline_range(Self._dim):
      v: float64 = self._data.unsafe_get(i)
      if i == 0:
        out._data.unsafe_set(i, v)
      else:
        out._data.unsafe_set(i, -v)
    return out

  @property
  @immutable
  def inv(self) -> Self:
    sq: float64 = self.sqr_mag
    z: float64 = 0.0
    if almost(sq, z):
      return new.zero
    s: float64 = 1.0 / sq
    return self.conjugate() * s

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
  def __abs__(self) -> float64:
    return self.mag

  @immutable
  def __invert__(self) -> Self:
    return self.inv

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    return self @ other

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

  def __imatmul__(self, other: Self) -> Self:
    prod: Self = self @ other
    self._copy_from(prod)
    return self

  @overload
  @immutable
  def __truediv__(self, other: float64) -> Self:
    s: float64 = 1.0 / other
    return self * s

  @overload
  @immutable
  def __truediv__(self, other: Self) -> Self:
    return self @ other.inv

  @overload
  def __imul__(self, other: float64) -> Self:
    for i in inline_range(Self._dim):
      self._data.unsafe_set(i, self._data.unsafe_get(i) * other)
    return self

  @overload
  def __imul__(self, other: Self) -> Self:
    prod: Self = self @ other
    self._copy_from(prod)
    return self

  @overload
  def __itruediv__(self, other: float64) -> Self:
    s: float64 = 1.0 / other
    for i in inline_range(Self._dim):
      self._data.unsafe_set(i, self._data.unsafe_get(i) * s)
    return self

  @overload
  def __itruediv__(self, other: Self) -> Self:
    q: Self = self / other
    self._copy_from(q)
    return self

  @immutable
  def __mod__(self, mag: float64) -> Self:
    return self.with_mag(mag)

  def __imod__(self, mag: float64) -> Self:
    self._copy_from(self.with_mag(mag))
    return self

  @immutable
  def __pow__(self, exponent: float64) -> Self:
    return self.pow(exponent)

  def __ipow__(self, exponent: float64) -> Self:
    self._copy_from(self ** exponent)
    return self


class Rotator(RotatorMixin):
  """2D 旋转 ``(w, z)``（tggame ``comp`` / ``Complex``）。"""

  _dim: int @const = 2

  def __init__(self, w: float64 = 1.0, z: float64 = 0.0) -> None:
    self._data.unsafe_set(0, w)
    self._data.unsafe_set(1, z)

  @property
  @immutable
  def w(self) -> float64:
    return self._data.unsafe_get(0)

  @property.setter
  def w(self, value: float64) -> None:
    self._data.unsafe_set(0, value)

  @property
  @immutable
  def z(self) -> float64:
    return self._data.unsafe_get(1)

  @property.setter
  def z(self, value: float64) -> None:
    self._data.unsafe_set(1, value)

  @staticmethod
  @immutable
  def _from_vec(v: Vector2) -> Self:
    return new(v.x, v.y)

  @staticmethod
  @immutable
  def _to_vec(c: Self) -> Vector2:
    return new(c.w, c.z)

  @immutable
  def __matmul__(self, other: Self) -> Self:
    return new(
      self.w * other.w - self.z * other.z,
      self.w * other.z + self.z * other.w,
    )

  @staticmethod
  @immutable
  def from_angle(angle: float64) -> Self:
    rad: float64 = radians(angle)
    return new(cos(rad), sin(rad))

  @staticmethod
  @immutable
  def between(origin: Vector2, target: Vector2) -> Self:
    angle: float64 = origin.angle_to(target)
    if origin @ target < 0.0:
      angle = -angle
    return new.from_angle(angle)

  @staticmethod
  @immutable
  def look_at(forward: Vector2) -> Self:
    n: Vector2 = forward.norm
    return new(n.x, n.y)

  @immutable
  def to_angle(self) -> float64:
    return degrees(atan2(self.z, self.w))

  @overload
  @immutable
  def __mul__(self, other: float64) -> Self:
    return new(self.w * other, self.z * other)

  @overload
  @immutable
  def __mul__(self, other: Vector2) -> Vector2:
    v: Self = new._from_vec(other)
    r: Self = self @ v
    return Self._to_vec(r)

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  @overload
  @immutable
  def __rmul__(self, other: Vector2) -> Vector2:
    return self * other

  @immutable
  def angle_to(self, other: Self) -> float64:
    return degrees(acos(self.dot(other)))

  @immutable
  def pow(self, exponent: float64) -> Self:
    return new.from_angle(self.to_angle() * exponent)

  @immutable
  def slerp(self, other: Self, t: float64) -> Self:
    theta: float64 = radians(self.angle_to(other))
    sin_theta: float64 = sin(theta)
    z: float64 = 0.0
    if almost(sin_theta, z):
      return self
    w0: float64 = sin((1.0 - t) * theta) / sin_theta
    w1: float64 = sin(t * theta) / sin_theta
    return new(
      self.w * w0 + other.w * w1,
      self.z * w0 + other.z * w1,
    )


class Quaternion(RotatorMixin):
  """3D 旋转四元数 ``(w, x, y, z)``。"""

  _dim: int @const = 4

  def __init__(
    self,
    w: float64 = 1.0,
    x: float64 = 0.0,
    y: float64 = 0.0,
    z: float64 = 0.0,
  ) -> None:
    self._data.unsafe_set(0, w)
    self._data.unsafe_set(1, x)
    self._data.unsafe_set(2, y)
    self._data.unsafe_set(3, z)

  @property
  @immutable
  def w(self) -> float64:
    return self._data.unsafe_get(0)

  @property.setter
  def w(self, value: float64) -> None:
    self._data.unsafe_set(0, value)

  @property
  @immutable
  def x(self) -> float64:
    return self._data.unsafe_get(1)

  @property.setter
  def x(self, value: float64) -> None:
    self._data.unsafe_set(1, value)

  @property
  @immutable
  def y(self) -> float64:
    return self._data.unsafe_get(2)

  @property.setter
  def y(self, value: float64) -> None:
    self._data.unsafe_set(2, value)

  @property
  @immutable
  def z(self) -> float64:
    return self._data.unsafe_get(3)

  @property.setter
  def z(self, value: float64) -> None:
    self._data.unsafe_set(3, value)

  @staticmethod
  @immutable
  def _from_vec(v: Vector3) -> Self:
    return new(0.0, v.x, v.y, v.z)

  @staticmethod
  @immutable
  def _to_vec(q: Self) -> Vector3:
    return new(q.x, q.y, q.z)

  @immutable
  def __matmul__(self, other: Self) -> Self:
    return new(
      self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z,
      self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y,
      self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x,
      self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w,
    )

  @staticmethod
  @immutable
  def from_axis_angle(axis: Vector3, angle: float64) -> Self:
    half: float64 = radians(angle * 0.5)
    w: float64 = cos(half)
    v: Vector3 = axis % sin(half)
    return new(w, v.x, v.y, v.z)

  @staticmethod
  @immutable
  def from_euler_angles(euler: Vector3) -> Self:
    ex: float64 = radians(euler.x * 0.5)
    ey: float64 = radians(euler.y * 0.5)
    ez: float64 = radians(euler.z * 0.5)
    cos_x: float64 = cos(ex)
    sin_x: float64 = sin(ex)
    cos_y: float64 = cos(ey)
    sin_y: float64 = sin(ey)
    cos_z: float64 = cos(ez)
    sin_z: float64 = sin(ez)
    return new(
      cos_x * cos_y * cos_z + sin_x * sin_y * sin_z,
      sin_x * cos_y * cos_z - cos_x * sin_y * sin_z,
      cos_x * sin_y * cos_z + sin_x * cos_y * sin_z,
      cos_x * cos_y * sin_z - sin_x * sin_y * cos_z,
    )

  @staticmethod
  @immutable
  def between(origin: Vector3, target: Vector3) -> Self:
    axis: Vector3 = origin @ target
    return new.from_axis_angle(axis, origin.angle_to(target))

  @staticmethod
  @immutable
  def look_at(forward: Vector3) -> Self:
    z_axis: Vector3 = new.forward
    return new.between(z_axis, forward)

  @overload
  @immutable
  def __mul__(self, other: float64) -> Self:
    return new(self.w * other, self.x * other, self.y * other, self.z * other)

  @overload
  @immutable
  def __mul__(self, other: Vector3) -> Vector3:
    return other.apply_quat(self.w, self.x, self.y, self.z)

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  @overload
  @immutable
  def __rmul__(self, other: Vector3) -> Vector3:
    return self * other

  @immutable
  def angle_to(self, other: Self) -> float64:
    dot: float64 = self.dot(other)
    return degrees(acos(dot * dot * 2.0 - 1.0))

  @immutable
  def to_euler_angles(self) -> Vector3:
    sin_x: float64 = 2.0 * (self.w * self.x + self.y * self.z)
    cos_x: float64 = 1.0 - 2.0 * (self.x * self.x + self.y * self.y)
    sin_y: float64 = 2.0 * (self.w * self.y - self.x * self.z)
    sin_z: float64 = 2.0 * (self.w * self.z + self.x * self.y)
    cos_z: float64 = 1.0 - 2.0 * (self.y * self.y + self.z * self.z)
    return new(degrees(atan2(sin_x, cos_x)), degrees(asin(sin_y)), degrees(atan2(sin_z, cos_z)))

  @immutable
  def to_axis_angle(self) -> (Vector3, float64):
    one: float64 = 1.0
    zero_angle: float64 = 0.0
    if almost(self.w, one):
      axis: Vector3 = new.right
      return (axis, zero_angle)
    rad: float64 = acos(self.w)
    angle: float64 = degrees(rad * 2.0)
    axis: Vector3 = new(self.x, self.y, self.z)
    axis = axis.norm
    if angle > 180.0:
      neg: Vector3 = new(-axis.x, -axis.y, -axis.z)
      alt: float64 = 360.0 - angle
      return (neg, alt)
    return (axis, angle)

  @immutable
  def pow(self, exponent: float64) -> Self:
    one: float64 = 1.0
    if almost(self.w, one):
      return new.identity
    rad: float64 = acos(self.w)
    angle: float64 = degrees(rad * 2.0)
    axis: Vector3 = new(self.x, self.y, self.z)
    axis = axis.norm
    if angle > 180.0:
      axis = -axis
      angle = 360.0 - angle
    return new.from_axis_angle(axis, angle * exponent)

  @immutable
  def slerp(self, other: Self, t: float64) -> Self:
    theta: float64 = acos(self.dot(other))
    sin_theta: float64 = sin(theta)
    z: float64 = 0.0
    if almost(sin_theta, z):
      return self
    w0: float64 = sin((1.0 - t) * theta) / sin_theta
    w1: float64 = sin(t * theta) / sin_theta
    return new(
      self.w * w0 + other.w * w1,
      self.x * w0 + other.x * w1,
      self.y * w0 + other.y * w1,
      self.z * w0 + other.z * w1,
    )
