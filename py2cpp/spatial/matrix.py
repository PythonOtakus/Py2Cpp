"""游戏数学：``Matrix3``（2D 仿射）、``Matrix4``（3D TRS）。"""
from __future__ import annotations

from ..builtins import *
from ..numeric.protocols import RealType
from ..math import cos, degrees, fabs, almost, floor, lerp, radians, sin, safeSqrt
from .rotator import Quaternion, Rotator
from .vector import Vector2, Vector3


@copyable
@mixin
class MatrixMixin[Scalar: RealType, Vec, Rot]:
  """``Matrix3`` / ``Matrix4`` 公共矩阵 API（``Vec``/``Rot`` 由宿主绑定；经 ``__getitem__`` / ``__setitem__`` 访问元素）。"""

  _dim: int @const = 0
  _vecDim: int @const = 0
  _data: Scalar[:Self._dim, :Self._dim]

  def __init__(self, identity: bool = True) -> None:
    if identity:
      for i in inlineRange(Self._dim):
        for j in inlineRange(Self._dim):
          self[i, j] = 1.0 if i == j else 0.0

  @immutable
  def __getitem__(self, index: (int, int)) -> Scalar:
    return self._data.unsafeGet(index[0], index[1])

  def __setitem__(self, index: (int, int), value: Scalar) -> None:
    self._data.unsafeSet(index[0], index[1], value)

  @immutable
  def unsafeGet(self, row: int, col: int) -> Scalar:
    return self._data.unsafeGet(row, col)

  def unsafeSet(self, row: int, col: int, value: Scalar) -> None:
    self._data.unsafeSet(row, col, value)

  @immutable
  def isAffine(self) -> bool:
    z: Scalar = 0.0
    one: Scalar = 1.0
    for j in inlineRange(Self._dim - 1):
      if not almost(self.unsafeGet(Self._dim - 1, j), z):
        return False
    if not almost(self.unsafeGet(Self._dim - 1, Self._dim - 1), one):
      return False
    return True

  @immutable
  def _invGauss(self) -> Self:
    tmp: Scalar[:Self._dim, :Self._dim * 2] = new()
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        tmp[i, j] = self[i, j]
        tmp[i, j + Self._dim] = 0.0
      tmp[i, i + Self._dim] = 1.0
    for k in inlineRange(Self._dim):
      pivRow: int = k
      pivVal: Scalar = fabs(tmp[k, k])
      for r in inlineRange(k + 1, Self._dim):
        v: Scalar = fabs(tmp[r, k])
        if v > pivVal:
          pivVal = v
          pivRow = r
      if pivRow != k:
        for c in inlineRange(Self._dim * 2):
          swapVal: Scalar = tmp[k, c]
          tmp[k, c] = tmp[pivRow, c]
          tmp[pivRow, c] = swapVal
      pivot: Scalar = tmp[k, k]
      for c in inlineRange(Self._dim * 2):
        tmp[k, c] /= pivot
      for r in inlineRange(Self._dim):
        if r != k:
          factor: Scalar = tmp[r, k]
          for c in inlineRange(Self._dim * 2):
            tmp[r, c] -= factor * tmp[k, c]
    result: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        result[i, j] = tmp[i, j + Self._dim]
    return result

  @immutable
  def invAffine(self) -> Self:
    hom: int = Self._dim - 1
    lin: Self = new(False)
    for i in inlineRange(Self._dim - 1):
      for j in inlineRange(Self._dim - 1):
        lin[i, j] = self[i, j]
    lin[hom, hom] = 1.0
    linInv: Self = lin._invGauss()
    result: Self = linInv
    for i in inlineRange(Self._dim - 1):
      acc: Scalar = 0.0
      for j in inlineRange(Self._dim - 1):
        acc += linInv[i, j] * self[j, hom]
      result[i, hom] = -acc
    return result

  def _copyFrom(self, other: Self) -> None:
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        self[i, j] = other[i, j]

  @staticproperty
  @immutable
  def zero() -> Self:
    m: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        m[i, j] = 0.0
    return m

  @staticproperty
  @immutable
  def identity() -> Self:
    return new()

  @property
  @immutable
  def det(self) -> Scalar:
    tmp: Scalar[:Self._dim, :Self._dim] = new()
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        tmp[i, j] = self[i, j]
    sign: Scalar = 1.0
    prod: Scalar = 1.0
    for k in inlineRange(Self._dim):
      pivRow: int = k
      pivVal: Scalar = fabs(tmp[k, k])
      for r in inlineRange(k + 1, Self._dim):
        v: Scalar = fabs(tmp[r, k])
        if v > pivVal:
          pivVal = v
          pivRow = r
      if pivRow != k:
        sign = -sign
        for c in inlineRange(Self._dim):
          swapVal: Scalar = tmp[k, c]
          tmp[k, c] = tmp[pivRow, c]
          tmp[pivRow, c] = swapVal
      pivot: Scalar = tmp[k, k]
      prod *= pivot
      for r in inlineRange(k + 1, Self._dim):
        factor: Scalar = tmp[r, k] / pivot
        tmp[r, k] = 0.0
        for c in inlineRange(k + 1, Self._dim):
          tmp[r, c] -= factor * tmp[k, c]
    return sign * prod

  @property
  @immutable
  def inv(self) -> Self:
    if self.isAffine():
      return self.invAffine()
    return self._invGauss()

  @immutable
  def transpose(self) -> Self:
    result: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        result[i, j] = self[j, i]
    return result

  @property
  @immutable
  def T(self) -> Self:
    return self.transpose()

  @immutable
  def dot(self, other: Self) -> Scalar:
    acc: Scalar = 0.0
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        acc += self[i, j] * other[i, j]
    return acc

  @immutable
  def _froNorm(self) -> Scalar:
    return safeSqrt(self.dot(self))

  @immutable
  def _expTaylor(self, terms: int) -> Self:
    result: Self = new.identity
    term: Self = new.identity
    k: Scalar = 1.0
    for _ in range(terms):
      term @= self
      term /= k
      result += term
      k += 1.0
    return result

  @immutable
  def _logTaylor(self, terms: int) -> Self:
    idm: Self = new.identity
    x: Self = self - idm
    result: Self = new.zero
    power: Self = x
    k: int = 1
    for _ in range(terms):
      invK: Scalar = 1.0 / k
      if k % 2 == 1:
        result += power * invK
      else:
        result -= power * invK
      power @= x
      k += 1
    return result

  @immutable
  def ipow(self, exponent: int) -> Self:
    if exponent == 0:
      return new.identity
    if exponent == 1:
      return self
    if exponent < 0:
      inv: Self = self.inv
      return inv.ipow(-exponent)
    half: int = exponent // 2
    p: Self = self.ipow(half)
    if exponent - half - half == 0:
      return p @ p
    return p @ p @ self

  @immutable
  def sqrt(self) -> Self:
    m: Self = new.identity
    half: Scalar = 0.5
    for _ in inlineRange(16):
      invM: Self = m.inv
      avg: Self = m + self @ invM
      nextM: Self = avg * half
      if nextM @ nextM == self:
        return nextM
      m = nextM
    return m

  @immutable
  def exp(self) -> Self:
    thresh: Scalar = 0.5
    taylorTerms: int = 12
    maxScale: int = 32
    a: Self = self
    s: int = 0
    for _ in range(maxScale):
      if a._froNorm() <= thresh:
        break
      a *= 0.5
      s += 1
    e: Self = a._expTaylor(taylorTerms)
    for _ in range(s):
      e @= e
    return e

  @immutable
  def log(self) -> Self:
    thresh: Scalar = 0.25
    taylorTerms: int = 12
    maxScale: int = 32
    a: Self = self
    s: int = 0
    idm: Self = new.identity
    for _ in range(maxScale):
      diff: Self = a - idm
      if diff._froNorm() <= thresh:
        break
      a = a.sqrt()
      s += 1
    logA: Self = a._logTaylor(taylorTerms)
    scale: Scalar = 1.0
    for _ in range(s):
      scale += scale
    return logA * scale

  @immutable
  def lerp(self, other: Self, t: Scalar) -> Self:
    result: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        result[i, j] = lerp(self[i, j], other[i, j], t)
    return result

  @immutable
  def xlerp(self, other: Self, t: Scalar) -> Self:
    return (other @ self.inv) ** t @ self

  @immutable
  def around(self, other: Self) -> Self:
    return other @ self @ other.inv

  @immutable
  def __pos__(self) -> Self:
    result: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        result[i, j] = self[i, j]
    return result

  @immutable
  def __neg__(self) -> Self:
    result: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        result[i, j] = -self[i, j]
    return result

  @immutable
  def __add__(self, other: Self) -> Self:
    result: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        result[i, j] = self[i, j] + other[i, j]
    return result

  def __iadd__(self, other: Self) -> Self:
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        self[i, j] += other[i, j]
    return self

  @immutable
  def __sub__(self, other: Self) -> Self:
    result: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        result[i, j] = self[i, j] - other[i, j]
    return result

  def __isub__(self, other: Self) -> Self:
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        self[i, j] -= other[i, j]
    return self

  @overload
  @immutable
  def __mul__(self, other: Scalar) -> Self:
    result: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        result[i, j] = self[i, j] * other
    return result

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    return self @ other

  @overload
  @immutable
  def __mul__(self, other: Vec) -> Vec:
    return self.applyToPoint(other)

  @overload
  @immutable
  def __rmul__(self, other: Scalar) -> Self:
    return self * other

  @overload
  def __imul__(self, other: Scalar) -> Self:
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        self[i, j] *= other
    return self

  @overload
  def __imul__(self, other: Self) -> Self:
    m: Self = self @ other
    self._copyFrom(m)
    return self

  @immutable
  def __matmul__(self, other: Self) -> Self:
    result: Self = new(False)
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        s: Scalar = 0.0
        for k in inlineRange(Self._dim):
          s += self.unsafeGet(i, k) * other.unsafeGet(k, j)
        result.unsafeSet(i, j, s)
    return result

  def __imatmul__(self, other: Self) -> Self:
    m: Self = self @ other
    self._copyFrom(m)
    return self

  @overload
  @immutable
  def __truediv__(self, other: Scalar) -> Self:
    s: Scalar = 1.0 / other
    return self * s

  @overload
  @immutable
  def __truediv__(self, other: Self) -> Self:
    return self @ other.inv

  @overload
  def __itruediv__(self, other: Scalar) -> Self:
    s: Scalar = 1.0 / other
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        self[i, j] *= s
    return self

  @overload
  def __itruediv__(self, other: Self) -> Self:
    m: Self = self @ other.inv
    self._copyFrom(m)
    return self

  @immutable
  def __invert__(self) -> Self:
    return self.inv

  @immutable
  def __abs__(self) -> Scalar:
    return self.det

  @immutable
  def __pow__(self, exponent: Scalar) -> Self:
    if almost(exponent, 0.0):
      return new.identity
    if almost(exponent, 1.0):
      return self
    if almost(exponent, -1.0):
      return self.inv
    if almost(exponent, 0.5):
      return self.sqrt()
    n: Scalar = floor(exponent)
    if almost(exponent, n):
      return self.ipow(int(n))
    return (self.log() * exponent).exp()

  def __ipow__(self, exponent: Scalar) -> Self:
    m: Self = self ** exponent
    self._copyFrom(m)
    return self

  @immutable
  def __bool__(self) -> bool:
    return self != Self.zero

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in inlineRange(Self._dim):
      for j in inlineRange(Self._dim):
        if not almost(self[i, j], other[i, j]):
          return False
    return True

  @property.setter
  def rotation(self, value: Rot) -> None:
    self._copyFrom(Self.transform(self.position, value, self.scale))

  @staticmethod
  @immutable
  def _lookAtImpl(position: Vec, target: Vec, scale: Vec) -> Self:
    rot: Rot = new.lookAt(target - position)
    return new.transform(position, rot, scale)

  @immutable
  def getAxis(self, i: int) -> Vec:
    out: Vec = new()
    for j in inlineRange(Self._vecDim):
      out.unsafeSet(j, self.unsafeGet(j, i))
    return out

  def setAxis(self, i: int, axis: Vec) -> None:
    for j in inlineRange(Self._vecDim):
      self.unsafeSet(j, i, axis.unsafeGet(j))

  @property
  @immutable
  def xAxis(self) -> Vec:
    return self.getAxis(0)

  @property.setter
  def xAxis(self, value: Vec) -> None:
    self.setAxis(0, value)

  @property
  @immutable
  def yAxis(self) -> Vec:
    return self.getAxis(1)

  @property.setter
  def yAxis(self, value: Vec) -> None:
    self.setAxis(1, value)

  @property
  @immutable
  def position(self) -> Vec:
    return self.getAxis(Self._dim - 1)

  @property.setter
  def position(self, value: Vec) -> None:
    self.setAxis(Self._dim - 1, value)

  @property
  @immutable
  def scale(self) -> Vec:
    out: Vec = new()
    for col in inlineRange(Self._vecDim):
      out.unsafeSet(col, abs(self.getAxis(col)))
    return out

  @property.setter
  def scale(self, value: Vec) -> None:
    m: Self = new()
    for col in inlineRange(Self._dim - 1):
      mag: Scalar = value.unsafeGet(col)
      ax: Vec = self.getAxis(col).withMag(mag)
      for j in inlineRange(Self._vecDim):
        m.unsafeSet(j, col, ax.unsafeGet(j))
    posCol: int = Self._dim - 1
    pos: Vec = self.position
    for j in inlineRange(Self._vecDim):
      m.unsafeSet(j, posCol, pos.unsafeGet(j))
    m.unsafeSet(Self._dim - 1, Self._dim - 1, 1.0)
    self._copyFrom(m)

  @immutable
  def applyToVector(self, other: Vec) -> Vec:
    out: Vec = new()
    for i in inlineRange(Self._dim - 1):
      s: Scalar = 0.0
      for j in inlineRange(Self._vecDim):
        s += self.unsafeGet(i, j) * other.unsafeGet(j)
      out.unsafeSet(i, s)
    return out

  @immutable
  def applyToPoint(self, other: Vec) -> Vec:
    out: Vec = new()
    posCol: int = Self._dim - 1
    homRow: int = Self._dim - 1
    for i in inlineRange(Self._dim - 1):
      s: Scalar = self.unsafeGet(i, posCol)
      for j in inlineRange(Self._vecDim):
        s += self.unsafeGet(i, j) * other.unsafeGet(j)
      w: Scalar = self.unsafeGet(homRow, posCol)
      for j2 in inlineRange(Self._vecDim):
        w += self.unsafeGet(homRow, j2) * other.unsafeGet(j2)
      out.unsafeSet(i, s / w)
    return out

  @staticmethod
  @immutable
  def fromAxesOrigin(*axis: Vec[:Self._dim - 1], origin: Vec = new()) -> Self:
    m: Self = new()
    for col in inlineRange(Self._dim - 1):
      ax: Vec = axis[col]
      for j in inlineRange(Self._vecDim):
        m[j, col] = ax[j]
    posCol: int = Self._dim - 1
    for j in inlineRange(Self._vecDim):
      m[j, posCol] = origin[j]
    m[Self._dim - 1, Self._dim - 1] = 1.0
    return m

  @staticmethod
  @immutable
  def fromPosition(position: Vec) -> Self:
    m: Self = new()
    posCol: int = Self._dim - 1
    for j in inlineRange(Self._vecDim):
      m[j, posCol] = position[j]
    m[Self._dim - 1, Self._dim - 1] = 1.0
    return m

  @staticmethod
  @immutable
  def fromScale(scale: Vec) -> Self:
    m: Self = new()
    for j in inlineRange(Self._vecDim):
      m[j, j] = scale[j]
    m[Self._dim - 1, Self._dim - 1] = 1.0
    return m

  @staticmethod
  @immutable
  def transform(
    position: Vec,
    rotation: Rot,
    scale: Vec,
  ) -> Self:
    m: Self = new()
    for col in inlineRange(Self._vecDim):
      basis: Vec = [Vec.right, Vec.down, Vec.forward][col]
      ax: Vec = rotation * (basis * scale.unsafeGet(col))
      for j in inlineRange(Self._vecDim):
        m.unsafeSet(j, col, ax.unsafeGet(j))
    posCol: int = Self._dim - 1
    for j in inlineRange(Self._vecDim):
      m.unsafeSet(j, posCol, position.unsafeGet(j))
    m.unsafeSet(Self._dim - 1, Self._dim - 1, 1.0)
    return m


class Matrix3[Scalar: RealType = float](
  MatrixMixin[Scalar, Vector2[Scalar], Rotator[Scalar]],
):
  """3×3 矩阵（2D 仿射变换，列主序对齐 tggame ``mat3``）。"""

  _dim: int @const = 3
  _vecDim: int @const = 2

  @property
  @immutable
  def rotation(self) -> Rotator[Scalar]:
    r: Rotator[Scalar] = new(self[0, 0], self[1, 0])
    return r.norm

  @property
  @immutable
  def angle(self) -> Scalar:
    return self.rotation.toAngle()

  @property.setter
  def angle(self, value: Scalar) -> None:
    self._copyFrom(Self.transform(self.position, Rotator[Scalar].fromAngle(value), self.scale))

  @staticmethod
  @immutable
  def fromRotation(rotation: Rotator[Scalar]) -> Self:
    m: Self = new()
    m[0, 0] = rotation.w
    m[1, 0] = rotation.z
    m[0, 1] = -rotation.z
    m[1, 1] = rotation.w
    m[2, 2] = 1.0
    return m

  @staticmethod
  @immutable
  def fromAngle(angle: Scalar) -> Self:
    return new.fromRotation(Rotator[Scalar].fromAngle(angle))

  @staticmethod
  @immutable
  def lookAt(
    position: Vector2[Scalar] = new(),
    target: Vector2[Scalar] = new(1.0, 0.0),
    scale: Vector2[Scalar] = new(1.0, 1.0),
  ) -> Self:
    return new._lookAtImpl(position, target, scale)


class Matrix4[Scalar: RealType = float](
  MatrixMixin[Scalar, Vector3[Scalar], Quaternion[Scalar]],
):
  """4×4 矩阵（3D TRS 变换，列主序对齐 tggame ``mat4``）。"""

  _dim: int @const = 4
  _vecDim: int @const = 3

  @property
  @immutable
  def zAxis(self) -> Vector3[Scalar]:
    return self.getAxis(2)

  @property.setter
  def zAxis(self, value: Vector3[Scalar]) -> None:
    self.setAxis(2, value)

  @property
  @immutable
  def rotation(self) -> Quaternion[Scalar]:
    sc: Vector3[Scalar] = self.scale
    rx: Scalar = self[0, 0] / sc.x
    ry: Scalar = self[1, 1] / sc.y
    rz: Scalar = self[2, 2] / sc.z
    return new(
      safeSqrt(1.0 + rx + ry + rz) * 0.5,
      safeSqrt(1.0 + rx - ry - rz) * 0.5,
      safeSqrt(1.0 - rx + ry - rz) * 0.5,
      safeSqrt(1.0 - rx - ry + rz) * 0.5,
    )

  @property
  @immutable
  def eulerAngles(self) -> Vector3[Scalar]:
    return self.rotation.toEulerAngles()

  @property.setter
  def eulerAngles(self, value: Vector3[Scalar]) -> None:
    self._copyFrom(Self.transform(self.position, Quaternion[Scalar].fromEulerAngles(value), self.scale))

  @staticmethod
  @immutable
  def fromAngleX(angle: Scalar) -> Self:
    radA: Scalar = radians(angle)
    cosA: Scalar = cos(radA)
    sinA: Scalar = sin(radA)
    m: Self = new()
    m[1, 1] = cosA
    m[1, 2] = -sinA
    m[2, 1] = sinA
    m[2, 2] = cosA
    return m

  @staticmethod
  @immutable
  def fromAngleY(angle: Scalar) -> Self:
    radA: Scalar = radians(angle)
    cosA: Scalar = cos(radA)
    sinA: Scalar = sin(radA)
    m: Self = new()
    m[0, 0] = cosA
    m[0, 2] = sinA
    m[2, 0] = -sinA
    m[2, 2] = cosA
    return m

  @staticmethod
  @immutable
  def fromAngleZ(angle: Scalar) -> Self:
    radA: Scalar = radians(angle)
    cosA: Scalar = cos(radA)
    sinA: Scalar = sin(radA)
    m: Self = new()
    m[0, 0] = cosA
    m[0, 1] = -sinA
    m[1, 0] = sinA
    m[1, 1] = cosA
    return m

  @staticmethod
  @immutable
  def fromRotation(rotation: Quaternion[Scalar]) -> Self:
    xAxis: Vector3[Scalar] = rotation * Vector3[Scalar].right
    yAxis: Vector3[Scalar] = rotation * Vector3[Scalar].down
    zAxis: Vector3[Scalar] = rotation * Vector3[Scalar].forward
    return new.fromAxesOrigin(xAxis, yAxis, zAxis)

  @staticmethod
  @immutable
  def fromAxisAngle(axis: Vector3[Scalar], angle: Scalar) -> Self:
    return new.fromRotation(Quaternion[Scalar].fromAxisAngle(axis, angle))

  @staticmethod
  @immutable
  def fromEulerAngles(eulerAngles: Vector3[Scalar]) -> Self:
    return new.fromRotation(Quaternion[Scalar].fromEulerAngles(eulerAngles))

  @staticmethod
  @immutable
  def lookAt(
    position: Vector3[Scalar] = new(),
    target: Vector3[Scalar] = new(0.0, 0.0, 1.0),
    scale: Vector3[Scalar] = new(1.0, 1.0, 1.0),
  ) -> Self:
    return new._lookAtImpl(position, target, scale)
