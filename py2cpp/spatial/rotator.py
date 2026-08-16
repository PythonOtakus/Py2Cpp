"""平面 ``Rotator`` 与 ``Quaternion``（对齐 tggame ``ComplexType`` / ``Quaternion``）。"""
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

  def _copyFrom(self, src: Self) -> None:
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(i, src._data.unsafeGet(i))

  @immutable
  def __len__(self) -> int:
    return Self._dim

  @immutable
  def __getitem__(self, index: int) -> float64:
    if index < 0 or index >= Self._dim:
      raise IndexError("rotator index out of range")
    return self._data.unsafeGet(index)

  def __setitem__(self, index: int, value: float64) -> None:
    if index < 0 or index >= Self._dim:
      raise IndexError("rotator index out of range")
    self._data.unsafeSet(index, value)

  @immutable
  def unsafeGet(self, index: int) -> float64:
    return self._data.unsafeGet(index)

  def unsafeSet(self, index: int, value: float64) -> None:
    self._data.unsafeSet(index, value)

  @staticproperty
  @immutable
  def zero() -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(i, 0.0)
    return out

  @staticproperty
  @immutable
  def identity() -> Self:
    return new()

  @property
  @immutable
  def sqrMag(self) -> float64:
    return self.dot(self)

  @property.setter
  def sqrMag(self, sqrMag: float64) -> None:
    self.mag = sqrt(sqrMag)

  @property
  @immutable
  def mag(self) -> float64:
    return sqrt(self.sqrMag)

  @property.setter
  def mag(self, mag: float64) -> None:
    self._copyFrom(self.withMag(mag))

  @property
  @immutable
  def norm(self) -> Self:
    return self.withMag(1.0)

  @immutable
  def dot(self, other: Self) -> float64:
    acc: float64 = 0.0
    for i in inlineRange(Self._dim):
      acc += self._data.unsafeGet(i) * other._data.unsafeGet(i)
    return acc

  @immutable
  def withMag(self, mag: float64) -> Self:
    rate: float64 = abs(self)
    z: float64 = 0.0
    if almost(rate, z):
      return new.zero
    return self * (mag / rate)

  def normalize(self) -> None:
    self._copyFrom(self.norm)

  @immutable
  def conjugate(self) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      v: float64 = self._data.unsafeGet(i)
      if i == 0:
        out._data.unsafeSet(i, v)
      else:
        out._data.unsafeSet(i, -v)
    return out

  @property
  @immutable
  def inv(self) -> Self:
    sq: float64 = self.sqrMag
    z: float64 = 0.0
    if almost(sq, z):
      return new.zero
    s: float64 = 1.0 / sq
    return self.conjugate() * s

  @immutable
  def lerp(self, other: Self, t: float64) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(
        i,
        lerp(self._data.unsafeGet(i), other._data.unsafeGet(i), t),
      )
    return out

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in inlineRange(Self._dim):
      if not almost(self._data.unsafeGet(i), other._data.unsafeGet(i)):
        return False
    return True

  @immutable
  def __bool__(self) -> bool:
    return self != new.zero

  @immutable
  def __pos__(self) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(i, self._data.unsafeGet(i))
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
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(i, self._data.unsafeGet(i) * other)
    return out

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  def __imatmul__(self, other: Self) -> Self:
    prod: Self = self @ other
    self._copyFrom(prod)
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
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(i, self._data.unsafeGet(i) * other)
    return self

  @overload
  def __imul__(self, other: Self) -> Self:
    prod: Self = self @ other
    self._copyFrom(prod)
    return self

  @overload
  def __itruediv__(self, other: float64) -> Self:
    s: float64 = 1.0 / other
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(i, self._data.unsafeGet(i) * s)
    return self

  @overload
  def __itruediv__(self, other: Self) -> Self:
    q: Self = self / other
    self._copyFrom(q)
    return self

  @immutable
  def __mod__(self, mag: float64) -> Self:
    return self.withMag(mag)

  def __imod__(self, mag: float64) -> Self:
    self._copyFrom(self.withMag(mag))
    return self

  @immutable
  def __pow__(self, exponent: float64) -> Self:
    return self.pow(exponent)

  def __ipow__(self, exponent: float64) -> Self:
    self._copyFrom(self ** exponent)
    return self


class Rotator(RotatorMixin):
  """2D 旋转 ``(w, z)``（tggame ``comp`` / ``ComplexType``）。"""

  _dim: int @const = 2

  def __init__(self, w: float64 = 1.0, z: float64 = 0.0) -> None:
    self._data.unsafeSet(0, w)
    self._data.unsafeSet(1, z)

  @property
  @immutable
  def w(self) -> float64:
    return self._data.unsafeGet(0)

  @property.setter
  def w(self, value: float64) -> None:
    self._data.unsafeSet(0, value)

  @property
  @immutable
  def z(self) -> float64:
    return self._data.unsafeGet(1)

  @property.setter
  def z(self, value: float64) -> None:
    self._data.unsafeSet(1, value)

  @staticmethod
  @immutable
  def _fromVec(v: Vector2) -> Self:
    return new(v.x, v.y)

  @staticmethod
  @immutable
  def _toVec(c: Self) -> Vector2:
    return new(c.w, c.z)

  @immutable
  def __matmul__(self, other: Self) -> Self:
    return new(
      self.w * other.w - self.z * other.z,
      self.w * other.z + self.z * other.w,
    )

  @staticmethod
  @immutable
  def fromAngle(angle: float64) -> Self:
    rad: float64 = radians(angle)
    return new(cos(rad), sin(rad))

  @staticmethod
  @immutable
  def between(origin: Vector2, target: Vector2) -> Self:
    angle: float64 = origin.angleTo(target)
    if origin @ target < 0.0:
      angle = -angle
    return new.fromAngle(angle)

  @staticmethod
  @immutable
  def lookAt(forward: Vector2) -> Self:
    n: Vector2 = forward.norm
    return new(n.x, n.y)

  @immutable
  def toAngle(self) -> float64:
    return degrees(atan2(self.z, self.w))

  @overload
  @immutable
  def __mul__(self, other: float64) -> Self:
    return new(self.w * other, self.z * other)

  @overload
  @immutable
  def __mul__(self, other: Vector2) -> Vector2:
    v: Self = new._fromVec(other)
    r: Self = self @ v
    return Self._toVec(r)

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  @overload
  @immutable
  def __rmul__(self, other: Vector2) -> Vector2:
    return self * other

  @immutable
  def angleTo(self, other: Self) -> float64:
    return degrees(acos(self.dot(other)))

  @immutable
  def pow(self, exponent: float64) -> Self:
    return new.fromAngle(self.toAngle() * exponent)

  @immutable
  def slerp(self, other: Self, t: float64) -> Self:
    theta: float64 = radians(self.angleTo(other))
    sinTheta: float64 = sin(theta)
    z: float64 = 0.0
    if almost(sinTheta, z):
      return self
    w0: float64 = sin((1.0 - t) * theta) / sinTheta
    w1: float64 = sin(t * theta) / sinTheta
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
    self._data.unsafeSet(0, w)
    self._data.unsafeSet(1, x)
    self._data.unsafeSet(2, y)
    self._data.unsafeSet(3, z)

  @property
  @immutable
  def w(self) -> float64:
    return self._data.unsafeGet(0)

  @property.setter
  def w(self, value: float64) -> None:
    self._data.unsafeSet(0, value)

  @property
  @immutable
  def x(self) -> float64:
    return self._data.unsafeGet(1)

  @property.setter
  def x(self, value: float64) -> None:
    self._data.unsafeSet(1, value)

  @property
  @immutable
  def y(self) -> float64:
    return self._data.unsafeGet(2)

  @property.setter
  def y(self, value: float64) -> None:
    self._data.unsafeSet(2, value)

  @property
  @immutable
  def z(self) -> float64:
    return self._data.unsafeGet(3)

  @property.setter
  def z(self, value: float64) -> None:
    self._data.unsafeSet(3, value)

  @staticmethod
  @immutable
  def _fromVec(v: Vector3) -> Self:
    return new(0.0, v.x, v.y, v.z)

  @staticmethod
  @immutable
  def _toVec(q: Self) -> Vector3:
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
  def fromAxisAngle(axis: Vector3, angle: float64) -> Self:
    half: float64 = radians(angle * 0.5)
    w: float64 = cos(half)
    v: Vector3 = axis % sin(half)
    return new(w, v.x, v.y, v.z)

  @staticmethod
  @immutable
  def fromEulerAngles(euler: Vector3) -> Self:
    ex: float64 = radians(euler.x * 0.5)
    ey: float64 = radians(euler.y * 0.5)
    ez: float64 = radians(euler.z * 0.5)
    cosX: float64 = cos(ex)
    sinX: float64 = sin(ex)
    cosY: float64 = cos(ey)
    sinY: float64 = sin(ey)
    cosZ: float64 = cos(ez)
    sinZ: float64 = sin(ez)
    return new(
      cosX * cosY * cosZ + sinX * sinY * sinZ,
      sinX * cosY * cosZ - cosX * sinY * sinZ,
      cosX * sinY * cosZ + sinX * cosY * sinZ,
      cosX * cosY * sinZ - sinX * sinY * cosZ,
    )

  @staticmethod
  @immutable
  def between(origin: Vector3, target: Vector3) -> Self:
    axis: Vector3 = origin @ target
    return new.fromAxisAngle(axis, origin.angleTo(target))

  @staticmethod
  @immutable
  def lookAt(forward: Vector3) -> Self:
    zAxis: Vector3 = new.forward
    return new.between(zAxis, forward)

  @overload
  @immutable
  def __mul__(self, other: float64) -> Self:
    return new(self.w * other, self.x * other, self.y * other, self.z * other)

  @overload
  @immutable
  def __mul__(self, other: Vector3) -> Vector3:
    return other.applyQuat(self.w, self.x, self.y, self.z)

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  @overload
  @immutable
  def __rmul__(self, other: Vector3) -> Vector3:
    return self * other

  @immutable
  def angleTo(self, other: Self) -> float64:
    dot: float64 = self.dot(other)
    return degrees(acos(dot * dot * 2.0 - 1.0))

  @immutable
  def toEulerAngles(self) -> Vector3:
    sinX: float64 = 2.0 * (self.w * self.x + self.y * self.z)
    cosX: float64 = 1.0 - 2.0 * (self.x * self.x + self.y * self.y)
    sinY: float64 = 2.0 * (self.w * self.y - self.x * self.z)
    sinZ: float64 = 2.0 * (self.w * self.z + self.x * self.y)
    cosZ: float64 = 1.0 - 2.0 * (self.y * self.y + self.z * self.z)
    return new(degrees(atan2(sinX, cosX)), degrees(asin(sinY)), degrees(atan2(sinZ, cosZ)))

  @immutable
  def toAxisAngle(self) -> (Vector3, float64):
    one: float64 = 1.0
    zeroAngle: float64 = 0.0
    if almost(self.w, one):
      axis: Vector3 = new.right
      return (axis, zeroAngle)
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
    return new.fromAxisAngle(axis, angle * exponent)

  @immutable
  def slerp(self, other: Self, t: float64) -> Self:
    theta: float64 = acos(self.dot(other))
    sinTheta: float64 = sin(theta)
    z: float64 = 0.0
    if almost(sinTheta, z):
      return self
    w0: float64 = sin((1.0 - t) * theta) / sinTheta
    w1: float64 = sin(t * theta) / sinTheta
    return new(
      self.w * w0 + other.w * w1,
      self.x * w0 + other.x * w1,
      self.y * w0 + other.y * w1,
      self.z * w0 + other.z * w1,
    )
