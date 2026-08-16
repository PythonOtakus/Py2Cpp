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

  def _copyFrom(self, src: Self) -> None:
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(i, src._data.unsafeGet(i))

  @immutable
  def __len__(self) -> int:
    return Self._dim

  @immutable
  def __getitem__(self, index: int) -> float64:
    if index < 0 or index >= Self._dim:
      raise IndexError("vector index out of range")
    return self._data.unsafeGet(index)

  def __setitem__(self, index: int, value: float64) -> None:
    if index < 0 or index >= Self._dim:
      raise IndexError("vector index out of range")
    self._data.unsafeSet(index, value)

  @immutable
  def unsafeGet(self, index: int) -> float64:
    return self._data.unsafeGet(index)

  def unsafeSet(self, index: int, value: float64) -> None:
    self._data.unsafeSet(index, value)

  @staticproperty
  @immutable
  def zero() -> Self:
    return new()

  @staticproperty
  @immutable
  def one() -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(i, 1.0)
    return out

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
  def scaled(self, other: Self) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(
        i,
        self._data.unsafeGet(i) * other._data.unsafeGet(i),
      )
    return out

  def scale(self, other: Self) -> None:
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(
        i,
        self._data.unsafeGet(i) * other._data.unsafeGet(i),
      )

  @immutable
  def invScaled(self, other: Self) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(
        i,
        self._data.unsafeGet(i) / other._data.unsafeGet(i),
      )
    return out

  def invScale(self, other: Self) -> None:
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(
        i,
        self._data.unsafeGet(i) / other._data.unsafeGet(i),
      )

  @immutable
  def powScaled(self, exponent: float64) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(i, pow(self._data.unsafeGet(i), exponent))
    return out

  def powScale(self, exponent: float64) -> None:
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(i, pow(self._data.unsafeGet(i), exponent))

  @property
  @immutable
  def inv(self) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(i, 1.0 / self._data.unsafeGet(i))
    return out

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
  def clamped(self, minMag: float64, maxMag: float64) -> Self:
    sq: float64 = self.sqrMag
    if sq < minMag * minMag:
      return self.withMag(minMag)
    if sq > maxMag * maxMag:
      return self.withMag(maxMag)
    return self

  def clamp(self, minMag: float64, maxMag: float64) -> None:
    self._copyFrom(self.clamped(minMag, maxMag))

  @immutable
  def sqrDistTo(self, other: Self) -> float64:
    d: Self = self - other
    return d.dot(d)

  @immutable
  def distTo(self, other: Self) -> float64:
    return sqrt(self.sqrDistTo(other))

  @immutable
  def movedTowards(self, target: Self, delta: float64) -> Self:
    dist: float64 = self.distTo(target)
    z: float64 = 0.0
    if almost(dist, z):
      return self
    return self.lerp(target, delta / dist)

  def moveTowards(self, target: Self, delta: float64) -> None:
    self._copyFrom(self.movedTowards(target, delta))

  @immutable
  def angleTo(self, other: Self) -> float64:
    denom: float64 = sqrt(self.sqrMag * other.sqrMag)
    return degrees(acos(self.dot(other) / denom))

  @immutable
  def rotatedTowards(self, target: Self, delta: float64) -> Self:
    ang: float64 = self.angleTo(target)
    z: float64 = 0.0
    if almost(ang, z):
      return self
    return self.slerp(target, delta / ang)

  def rotateTowards(self, target: Self, delta: float64) -> None:
    self._copyFrom(self.rotatedTowards(target, delta))

  @immutable
  def project(self, other: Self) -> Self:
    rate: float64 = other.sqrMag
    z: float64 = 0.0
    if almost(rate, z):
      return new.zero
    s: float64 = self.dot(other) / rate
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(i, other._data.unsafeGet(i) * s)
    return out

  @immutable
  def reflect(self, other: Self) -> Self:
    p: Self = self.project(other)
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(
        i,
        self._data.unsafeGet(i) - 2.0 * p._data.unsafeGet(i),
      )
    return out

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
  def slerp(self, other: Self, t: float64) -> Self:
    theta: float64 = radians(self.angleTo(other))
    sinTheta: float64 = sin(theta)
    z: float64 = 0.0
    if almost(sinTheta, z):
      return self
    w0: float64 = sin((1.0 - t) * theta) / sinTheta
    w1: float64 = sin(t * theta) / sinTheta
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(
        i,
        self._data.unsafeGet(i) * w0 + other._data.unsafeGet(i) * w1,
      )
    return out

  @immutable
  def xlerp(self, other: Self, t: float64) -> Self:
    return self.scaled(other.invScaled(self).powScaled(t))

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
  def __neg__(self) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(i, -self._data.unsafeGet(i))
    return out

  @immutable
  def __add__(self, other: Self) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(
        i,
        self._data.unsafeGet(i) + other._data.unsafeGet(i),
      )
    return out

  def __iadd__(self, other: Self) -> Self:
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(
        i,
        self._data.unsafeGet(i) + other._data.unsafeGet(i),
      )
    return self

  @immutable
  def __sub__(self, other: Self) -> Self:
    out: Self = new()
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(
        i,
        self._data.unsafeGet(i) - other._data.unsafeGet(i),
      )
    return out

  def __isub__(self, other: Self) -> Self:
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(
        i,
        self._data.unsafeGet(i) - other._data.unsafeGet(i),
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
    for i in inlineRange(Self._dim):
      out._data.unsafeSet(i, self._data.unsafeGet(i) * other)
    return out

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  def __imul__(self, other: float64) -> Self:
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(i, self._data.unsafeGet(i) * other)
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
    for i in inlineRange(Self._dim):
      self._data.unsafeSet(i, self._data.unsafeGet(i) * s)
    return self

  @immutable
  def __abs__(self) -> float64:
    return self.mag

  @immutable
  def __mod__(self, mag: float64) -> Self:
    return self.withMag(mag)

  def __imod__(self, mag: float64) -> Self:
    self._copyFrom(self.withMag(mag))
    return self

  @immutable
  def __xor__(self, other: Self) -> float64:
    return self.distTo(other)


class Vector2(VectorMixin):
  """二维向量 ``(x, y)``。"""

  _dim: int @const = 2

  def __init__(self, x: float64 = 0.0, y: float64 = 0.0) -> None:
    self._data.unsafeSet(0, x)
    self._data.unsafeSet(1, y)

  @property
  @immutable
  def x(self) -> float64:
    return self._data.unsafeGet(0)

  @property.setter
  def x(self, value: float64) -> None:
    self._data.unsafeSet(0, value)

  @property
  @immutable
  def y(self) -> float64:
    return self._data.unsafeGet(1)

  @property.setter
  def y(self, value: float64) -> None:
    self._data.unsafeSet(1, value)

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
  def fromPolar(r: float64, phi: float64) -> Self:
    radPhi: float64 = radians(phi)
    u: Self = new(cos(radPhi), sin(radPhi))
    return u * r

  @immutable
  def cross(self, other: Self) -> float64:
    return self.x * other.y - self.y * other.x

  @immutable
  def rotated(self, angle: float64) -> Self:
    radA: float64 = radians(angle)
    cosA: float64 = cos(radA)
    sinA: float64 = sin(radA)
    rx: float64 = self.x * cosA - self.y * sinA
    ry: float64 = self.x * sinA + self.y * cosA
    return new(rx, ry)

  def rotate(self, angle: float64) -> None:
    self._copyFrom(self.rotated(angle))

  @immutable
  def rotated90(self) -> Self:
    return new(-self.y, self.x)

  def rotate90(self) -> None:
    self._copyFrom(self.rotated90())

  @immutable
  def rotatedAround(self, center: Self, angle: float64) -> Self:
    return (self - center).rotated(angle) + center

  def rotateAround(self, center: Self, angle: float64) -> None:
    self._copyFrom(self.rotatedAround(center, angle))

  @immutable
  def flipped(self, flipX: bool = False, flipY: bool = False) -> Self:
    return new(-self.x if flipX else self.x, -self.y if flipY else self.y)

  def flip(self, flipX: bool = False, flipY: bool = False) -> None:
    self._copyFrom(self.flipped(flipX, flipY))

  @immutable
  def toPolar(self) -> Self:
    return new(abs(self), degrees(atan2(self.y, self.x)))

  @immutable
  def __matmul__(self, other: Self) -> float64:
    return self.cross(other)


class Vector3(VectorMixin):
  """三维向量 ``(x, y, z)``。"""

  _dim: int @const = 3

  def __init__(self, x: float64 = 0.0, y: float64 = 0.0, z: float64 = 0.0) -> None:
    self._data.unsafeSet(0, x)
    self._data.unsafeSet(1, y)
    self._data.unsafeSet(2, z)

  @property
  @immutable
  def x(self) -> float64:
    return self._data.unsafeGet(0)

  @property.setter
  def x(self, value: float64) -> None:
    self._data.unsafeSet(0, value)

  @property
  @immutable
  def y(self) -> float64:
    return self._data.unsafeGet(1)

  @property.setter
  def y(self, value: float64) -> None:
    self._data.unsafeSet(1, value)

  @property
  @immutable
  def z(self) -> float64:
    return self._data.unsafeGet(2)

  @property.setter
  def z(self, value: float64) -> None:
    self._data.unsafeSet(2, value)

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
  def fromSpherical(r: float64, phi: float64, theta: float64) -> Self:
    radPhi: float64 = radians(phi)
    radTheta: float64 = radians(theta)
    sinTheta: float64 = sin(radTheta)
    cosTheta: float64 = cos(radTheta)
    cosPhi: float64 = cos(radPhi)
    sinPhi: float64 = sin(radPhi)
    p: float64 = sinTheta * r
    return new(p * cosPhi, p * sinPhi, cosTheta * r)

  @immutable
  def cross(self, other: Self) -> Self:
    return new(
      self.y * other.z - self.z * other.y,
      self.z * other.x - self.x * other.z,
      self.x * other.y - self.y * other.x,
    )

  @immutable
  def rotatedX(self, angle: float64) -> Self:
    radA: float64 = radians(angle)
    cosA: float64 = cos(radA)
    sinA: float64 = sin(radA)
    ry: float64 = self.y * cosA - self.z * sinA
    rz: float64 = self.y * sinA + self.z * cosA
    return new(self.x, ry, rz)

  def rotateX(self, angle: float64) -> None:
    self._copyFrom(self.rotatedX(angle))

  @immutable
  def rotatedY(self, angle: float64) -> Self:
    radA: float64 = radians(angle)
    cosA: float64 = cos(radA)
    sinA: float64 = sin(radA)
    rx: float64 = self.x * cosA + self.z * sinA
    rz: float64 = -self.x * sinA + self.z * cosA
    return new(rx, self.y, rz)

  def rotateY(self, angle: float64) -> None:
    self._copyFrom(self.rotatedY(angle))

  @immutable
  def rotatedZ(self, angle: float64) -> Self:
    radA: float64 = radians(angle)
    cosA: float64 = cos(radA)
    sinA: float64 = sin(radA)
    rx: float64 = self.x * cosA - self.y * sinA
    ry: float64 = self.x * sinA + self.y * cosA
    return new(rx, ry, self.z)

  def rotateZ(self, angle: float64) -> None:
    self._copyFrom(self.rotatedZ(angle))

  @immutable
  def applyQuat(self, w: float64, qx: float64, qy: float64, qz: float64) -> Self:
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
    return self.applyQuat(w, n.x * s, n.y * s, n.z * s)

  def rotate(self, axis: Self, angle: float64) -> None:
    self._copyFrom(self.rotated(axis, angle))

  @immutable
  def rotatedAround(self, center: Self, axis: Self, angle: float64) -> Self:
    return (self - center).rotated(axis, angle) + center

  def rotateAround(self, center: Self, axis: Self, angle: float64) -> None:
    self._copyFrom(self.rotatedAround(center, axis, angle))

  @immutable
  def rotatedEulerAngles(self, eulerAngles: Self) -> Self:
    ex: float64 = radians(eulerAngles.x * 0.5)
    ey: float64 = radians(eulerAngles.y * 0.5)
    ez: float64 = radians(eulerAngles.z * 0.5)
    cosX: float64 = cos(ex)
    sinX: float64 = sin(ex)
    cosY: float64 = cos(ey)
    sinY: float64 = sin(ey)
    cosZ: float64 = cos(ez)
    sinZ: float64 = sin(ez)
    w: float64 = cosX * cosY * cosZ + sinX * sinY * sinZ
    qx: float64 = sinX * cosY * cosZ - cosX * sinY * sinZ
    qy: float64 = cosX * sinY * cosZ + sinX * cosY * sinZ
    qz: float64 = cosX * cosY * sinZ - sinX * sinY * cosZ
    return self.applyQuat(w, qx, qy, qz)

  def rotateEulerAngles(self, eulerAngles: Self) -> None:
    self._copyFrom(self.rotatedEulerAngles(eulerAngles))

  @immutable
  def flipped(
    self,
    flipX: bool = False,
    flipY: bool = False,
    flipZ: bool = False,
  ) -> Self:
    return new(
      -self.x if flipX else self.x,
      -self.y if flipY else self.y,
      -self.z if flipZ else self.z,
    )

  def flip(
    self,
    flipX: bool = False,
    flipY: bool = False,
    flipZ: bool = False,
  ) -> None:
    self._copyFrom(self.flipped(flipX, flipY, flipZ))

  @immutable
  def toSpherical(self) -> Self:
    lenV: float64 = abs(self)
    return new(lenV, degrees(atan2(self.y, self.x)), degrees(acos(self.z / lenV)))

  @immutable
  def toVector2(self) -> Vector2:
    return new(self.x, self.y)

  @immutable
  def __matmul__(self, other: Self) -> Self:
    return self.cross(other)

  def __imatmul__(self, other: Self) -> Self:
    self._copyFrom(self.cross(other))
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
    self._data.unsafeSet(0, x)
    self._data.unsafeSet(1, y)
    self._data.unsafeSet(2, z)
    self._data.unsafeSet(3, w)

  @property
  @immutable
  def x(self) -> float64:
    return self._data.unsafeGet(0)

  @property.setter
  def x(self, value: float64) -> None:
    self._data.unsafeSet(0, value)

  @property
  @immutable
  def y(self) -> float64:
    return self._data.unsafeGet(1)

  @property.setter
  def y(self, value: float64) -> None:
    self._data.unsafeSet(1, value)

  @property
  @immutable
  def z(self) -> float64:
    return self._data.unsafeGet(2)

  @property.setter
  def z(self, value: float64) -> None:
    self._data.unsafeSet(2, value)

  @property
  @immutable
  def w(self) -> float64:
    return self._data.unsafeGet(3)

  @property.setter
  def w(self, value: float64) -> None:
    self._data.unsafeSet(3, value)

  @immutable
  def flipped(
    self,
    flipX: bool = False,
    flipY: bool = False,
    flipZ: bool = False,
    flipW: bool = False,
  ) -> Self:
    return new(
      -self.x if flipX else self.x,
      -self.y if flipY else self.y,
      -self.z if flipZ else self.z,
      -self.w if flipW else self.w,
    )

  def flip(
    self,
    flipX: bool = False,
    flipY: bool = False,
    flipZ: bool = False,
    flipW: bool = False,
  ) -> None:
    self._copyFrom(self.flipped(flipX, flipY, flipZ, flipW))
