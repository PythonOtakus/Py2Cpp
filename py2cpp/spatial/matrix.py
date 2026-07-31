"""游戏数学：``Matrix3``（2D 仿射）、``Matrix4``（3D TRS）。"""
from __future__ import annotations

from ..builtins import *
from ..math import cos, degrees, fabs, almost, floor, lerp, radians, sin, safe_sqrt
from .rotator import Quaternion, Rotator
from .vector import Vector2, Vector3


@copyable
@mixin
class MatrixMixin[Vec, Rot]:
  """``Matrix3`` / ``Matrix4`` 公共矩阵 API（``Vec``/``Rot`` 由宿主绑定；经 ``__getitem__`` / ``__setitem__`` 访问元素）。"""

  _dim: int @const = 0
  _vec_dim: int @const = 0
  _data: float64[:Self._dim, :Self._dim]

  def __init__(self, identity: bool = True) -> None:
    if identity:
      for i in inline_range(Self._dim):
        for j in inline_range(Self._dim):
          self[i, j] = 1.0 if i == j else 0.0

  @immutable
  def __getitem__(self, index: (int, int)) -> float64:
    return self._data.unsafe_get(index[0], index[1])

  def __setitem__(self, index: (int, int), value: float64) -> None:
    self._data.unsafe_set(index[0], index[1], value)

  @immutable
  def unsafe_get(self, row: int, col: int) -> float64:
    return self._data.unsafe_get(row, col)

  def unsafe_set(self, row: int, col: int, value: float64) -> None:
    self._data.unsafe_set(row, col, value)

  @immutable
  def is_affine(self) -> bool:
    z: float64 = 0.0
    one: float64 = 1.0
    for j in inline_range(Self._dim - 1):
      if not almost(self.unsafe_get(Self._dim - 1, j), z):
        return False
    if not almost(self.unsafe_get(Self._dim - 1, Self._dim - 1), one):
      return False
    return True

  @immutable
  def _inv_gauss(self) -> Self:
    tmp: float64[:Self._dim, :Self._dim * 2] = new()
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        tmp[i, j] = self[i, j]
        tmp[i, j + Self._dim] = 0.0
      tmp[i, i + Self._dim] = 1.0
    for k in inline_range(Self._dim):
      piv_row: int = k
      piv_val: float64 = fabs(tmp[k, k])
      for r in inline_range(k + 1, Self._dim):
        v: float64 = fabs(tmp[r, k])
        if v > piv_val:
          piv_val = v
          piv_row = r
      if piv_row != k:
        for c in inline_range(Self._dim * 2):
          swap_val: float64 = tmp[k, c]
          tmp[k, c] = tmp[piv_row, c]
          tmp[piv_row, c] = swap_val
      pivot: float64 = tmp[k, k]
      for c in inline_range(Self._dim * 2):
        tmp[k, c] /= pivot
      for r in inline_range(Self._dim):
        if r != k:
          factor: float64 = tmp[r, k]
          for c in inline_range(Self._dim * 2):
            tmp[r, c] -= factor * tmp[k, c]
    result: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        result[i, j] = tmp[i, j + Self._dim]
    return result

  @immutable
  def inv_affine(self) -> Self:
    hom: int = Self._dim - 1
    lin: Self = new(False)
    for i in inline_range(Self._dim - 1):
      for j in inline_range(Self._dim - 1):
        lin[i, j] = self[i, j]
    lin[hom, hom] = 1.0
    lin_inv: Self = lin._inv_gauss()
    result: Self = lin_inv
    for i in inline_range(Self._dim - 1):
      acc: float64 = 0.0
      for j in inline_range(Self._dim - 1):
        acc += lin_inv[i, j] * self[j, hom]
      result[i, hom] = -acc
    return result

  def _copy_from(self, other: Self) -> None:
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        self[i, j] = other[i, j]

  @staticproperty
  @immutable
  def zero() -> Self:
    m: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        m[i, j] = 0.0
    return m

  @staticproperty
  @immutable
  def identity() -> Self:
    return new()

  @property
  @immutable
  def det(self) -> float64:
    tmp: float64[:Self._dim, :Self._dim] = new()
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        tmp[i, j] = self[i, j]
    sign: float64 = 1.0
    prod: float64 = 1.0
    for k in inline_range(Self._dim):
      piv_row: int = k
      piv_val: float64 = fabs(tmp[k, k])
      for r in inline_range(k + 1, Self._dim):
        v: float64 = fabs(tmp[r, k])
        if v > piv_val:
          piv_val = v
          piv_row = r
      if piv_row != k:
        sign = -sign
        for c in inline_range(Self._dim):
          swap_val: float64 = tmp[k, c]
          tmp[k, c] = tmp[piv_row, c]
          tmp[piv_row, c] = swap_val
      pivot: float64 = tmp[k, k]
      prod *= pivot
      for r in inline_range(k + 1, Self._dim):
        factor: float64 = tmp[r, k] / pivot
        tmp[r, k] = 0.0
        for c in inline_range(k + 1, Self._dim):
          tmp[r, c] -= factor * tmp[k, c]
    return sign * prod

  @property
  @immutable
  def inv(self) -> Self:
    if self.is_affine():
      return self.inv_affine()
    return self._inv_gauss()

  @immutable
  def transpose(self) -> Self:
    result: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        result[i, j] = self[j, i]
    return result

  @property
  @immutable
  def T(self) -> Self:
    return self.transpose()

  @immutable
  def dot(self, other: Self) -> float64:
    acc: float64 = 0.0
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        acc += self[i, j] * other[i, j]
    return acc

  @immutable
  def _fro_norm(self) -> float64:
    return safe_sqrt(self.dot(self))

  @immutable
  def _exp_taylor(self, terms: int) -> Self:
    result: Self = new.identity
    term: Self = new.identity
    k: float64 = 1.0
    for _ in range(terms):
      term @= self
      term /= k
      result += term
      k += 1.0
    return result

  @immutable
  def _log_taylor(self, terms: int) -> Self:
    idm: Self = new.identity
    x: Self = self - idm
    result: Self = new.zero
    power: Self = x
    k: int = 1
    for _ in range(terms):
      inv_k: float64 = 1.0 / k
      if k % 2 == 1:
        result += power * inv_k
      else:
        result -= power * inv_k
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
    half: float64 = 0.5
    for _ in inline_range(16):
      inv_m: Self = m.inv
      avg: Self = m + self @ inv_m
      next_m: Self = avg * half
      if next_m @ next_m == self:
        return next_m
      m = next_m
    return m

  @immutable
  def exp(self) -> Self:
    thresh: float64 = 0.5
    taylor_terms: int = 12
    max_scale: int = 32
    a: Self = self
    s: int = 0
    for _ in range(max_scale):
      if a._fro_norm() <= thresh:
        break
      a *= 0.5
      s += 1
    e: Self = a._exp_taylor(taylor_terms)
    for _ in range(s):
      e @= e
    return e

  @immutable
  def log(self) -> Self:
    thresh: float64 = 0.25
    taylor_terms: int = 12
    max_scale: int = 32
    a: Self = self
    s: int = 0
    idm: Self = new.identity
    for _ in range(max_scale):
      diff: Self = a - idm
      if diff._fro_norm() <= thresh:
        break
      a = a.sqrt()
      s += 1
    log_a: Self = a._log_taylor(taylor_terms)
    scale: float64 = 1.0
    for _ in range(s):
      scale += scale
    return log_a * scale

  @immutable
  def lerp(self, other: Self, t: float64) -> Self:
    result: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        result[i, j] = lerp(self[i, j], other[i, j], t)
    return result

  @immutable
  def xlerp(self, other: Self, t: float64) -> Self:
    return (other @ self.inv) ** t @ self

  @immutable
  def around(self, other: Self) -> Self:
    return other @ self @ other.inv

  @immutable
  def __pos__(self) -> Self:
    result: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        result[i, j] = self[i, j]
    return result

  @immutable
  def __neg__(self) -> Self:
    result: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        result[i, j] = -self[i, j]
    return result

  @immutable
  def __add__(self, other: Self) -> Self:
    result: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        result[i, j] = self[i, j] + other[i, j]
    return result

  def __iadd__(self, other: Self) -> Self:
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        self[i, j] += other[i, j]
    return self

  @immutable
  def __sub__(self, other: Self) -> Self:
    result: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        result[i, j] = self[i, j] - other[i, j]
    return result

  def __isub__(self, other: Self) -> Self:
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        self[i, j] -= other[i, j]
    return self

  @overload
  @immutable
  def __mul__(self, other: float64) -> Self:
    result: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        result[i, j] = self[i, j] * other
    return result

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    return self @ other

  @overload
  @immutable
  def __mul__(self, other: Vec) -> Vec:
    return self.apply_to_point(other)

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  @overload
  def __imul__(self, other: float64) -> Self:
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        self[i, j] *= other
    return self

  @overload
  def __imul__(self, other: Self) -> Self:
    m: Self = self @ other
    self._copy_from(m)
    return self

  @immutable
  def __matmul__(self, other: Self) -> Self:
    result: Self = new(False)
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        s: float64 = 0.0
        for k in inline_range(Self._dim):
          s += self.unsafe_get(i, k) * other.unsafe_get(k, j)
        result.unsafe_set(i, j, s)
    return result

  def __imatmul__(self, other: Self) -> Self:
    m: Self = self @ other
    self._copy_from(m)
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
  def __itruediv__(self, other: float64) -> Self:
    s: float64 = 1.0 / other
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        self[i, j] *= s
    return self

  @overload
  def __itruediv__(self, other: Self) -> Self:
    m: Self = self @ other.inv
    self._copy_from(m)
    return self

  @immutable
  def __invert__(self) -> Self:
    return self.inv

  @immutable
  def __abs__(self) -> float64:
    return self.det

  @immutable
  def __pow__(self, exponent: float64) -> Self:
    if almost(exponent, 0.0):
      return new.identity
    if almost(exponent, 1.0):
      return self
    if almost(exponent, -1.0):
      return self.inv
    if almost(exponent, 0.5):
      return self.sqrt()
    n: float64 = floor(exponent)
    if almost(exponent, n):
      return self.ipow(int(n))
    return (self.log() * exponent).exp()

  def __ipow__(self, exponent: float64) -> Self:
    m: Self = self ** exponent
    self._copy_from(m)
    return self

  @immutable
  def __bool__(self) -> bool:
    return self != new.zero

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in inline_range(Self._dim):
      for j in inline_range(Self._dim):
        if not almost(self[i, j], other[i, j]):
          return False
    return True

  @property.setter
  def rotation(self, value: Rot) -> None:
    self._copy_from(Self.transform(self.position, value, self.scale))

  @staticmethod
  @immutable
  def _look_at_impl(position: Vec, target: Vec, scale: Vec) -> Self:
    rot: Rot = new.look_at(target - position)
    return new.transform(position, rot, scale)

  @immutable
  def get_axis(self, i: int) -> Vec:
    out: Vec = new()
    for j in inline_range(Self._vec_dim):
      out.unsafe_set(j, self.unsafe_get(j, i))
    return out

  def set_axis(self, i: int, axis: Vec) -> None:
    for j in inline_range(Self._vec_dim):
      self.unsafe_set(j, i, axis.unsafe_get(j))

  @property
  @immutable
  def x_axis(self) -> Vec:
    return self.get_axis(0)

  @property.setter
  def x_axis(self, value: Vec) -> None:
    self.set_axis(0, value)

  @property
  @immutable
  def y_axis(self) -> Vec:
    return self.get_axis(1)

  @property.setter
  def y_axis(self, value: Vec) -> None:
    self.set_axis(1, value)

  @property
  @immutable
  def position(self) -> Vec:
    return self.get_axis(Self._dim - 1)

  @property.setter
  def position(self, value: Vec) -> None:
    self.set_axis(Self._dim - 1, value)

  @property
  @immutable
  def scale(self) -> Vec:
    out: Vec = new()
    for col in inline_range(Self._vec_dim):
      out.unsafe_set(col, abs(self.get_axis(col)))
    return out

  @property.setter
  def scale(self, value: Vec) -> None:
    m: Self = new()
    for col in inline_range(Self._dim - 1):
      mag: float64 = value.unsafe_get(col)
      ax: Vec = self.get_axis(col).with_mag(mag)
      for j in inline_range(Self._vec_dim):
        m.unsafe_set(j, col, ax.unsafe_get(j))
    pos_col: int = Self._dim - 1
    pos: Vec = self.position
    for j in inline_range(Self._vec_dim):
      m.unsafe_set(j, pos_col, pos.unsafe_get(j))
    m.unsafe_set(Self._dim - 1, Self._dim - 1, 1.0)
    self._copy_from(m)

  @immutable
  def apply_to_vector(self, other: Vec) -> Vec:
    out: Vec = new()
    for i in inline_range(Self._dim - 1):
      s: float64 = 0.0
      for j in inline_range(Self._vec_dim):
        s += self.unsafe_get(i, j) * other.unsafe_get(j)
      out.unsafe_set(i, s)
    return out

  @immutable
  def apply_to_point(self, other: Vec) -> Vec:
    out: Vec = new()
    pos_col: int = Self._dim - 1
    hom_row: int = Self._dim - 1
    for i in inline_range(Self._dim - 1):
      s: float64 = self.unsafe_get(i, pos_col)
      for j in inline_range(Self._vec_dim):
        s += self.unsafe_get(i, j) * other.unsafe_get(j)
      w: float64 = self.unsafe_get(hom_row, pos_col)
      for j2 in inline_range(Self._vec_dim):
        w += self.unsafe_get(hom_row, j2) * other.unsafe_get(j2)
      out.unsafe_set(i, s / w)
    return out

  @staticmethod
  @immutable
  def from_axes_origin(*axis: Vec[:Self._dim - 1], origin: Vec = new.zero) -> Self:
    m: Self = new()
    for col in inline_range(Self._dim - 1):
      ax: Vec = axis[col]
      for j in inline_range(Self._vec_dim):
        m[j, col] = ax[j]
    pos_col: int = Self._dim - 1
    for j in inline_range(Self._vec_dim):
      m[j, pos_col] = origin[j]
    m[Self._dim - 1, Self._dim - 1] = 1.0
    return m

  @staticmethod
  @immutable
  def from_position(position: Vec) -> Self:
    m: Self = new()
    pos_col: int = Self._dim - 1
    for j in inline_range(Self._vec_dim):
      m[j, pos_col] = position[j]
    m[Self._dim - 1, Self._dim - 1] = 1.0
    return m

  @staticmethod
  @immutable
  def from_scale(scale: Vec) -> Self:
    m: Self = new()
    for j in inline_range(Self._vec_dim):
      m[j, j] = scale[j]
    m[Self._dim - 1, Self._dim - 1] = 1.0
    return m

  @staticmethod
  @immutable
  def transform(
    position: Vec = new.zero,
    rotation: Rot = new.identity,
    scale: Vec = new.one,
  ) -> Self:
    m: Self = new()
    for col in inline_range(Self._vec_dim):
      basis: Vec = [Vec.right, Vec.down, Vec.forward][col]
      ax: Vec = rotation * (basis * scale.unsafe_get(col))
      for j in inline_range(Self._vec_dim):
        m.unsafe_set(j, col, ax.unsafe_get(j))
    pos_col: int = Self._dim - 1
    for j in inline_range(Self._vec_dim):
      m.unsafe_set(j, pos_col, position.unsafe_get(j))
    m.unsafe_set(Self._dim - 1, Self._dim - 1, 1.0)
    return m


class Matrix3(MatrixMixin[Vector2, Rotator]):
  """3×3 矩阵（2D 仿射变换，列主序对齐 tggame ``mat3``）。"""

  _dim: int @const = 3
  _vec_dim: int @const = 2

  @property
  @immutable
  def rotation(self) -> Rotator:
    r: Rotator = new(self[0, 0], self[1, 0])
    return r.norm

  @property
  @immutable
  def angle(self) -> float64:
    return self.rotation.to_angle()

  @property.setter
  def angle(self, value: float64) -> None:
    self._copy_from(Self.transform(self.position, Rotator.from_angle(value), self.scale))

  @staticmethod
  @immutable
  def from_rotation(rotation: Rotator) -> Self:
    m: Self = new()
    m[0, 0] = rotation.w
    m[1, 0] = rotation.z
    m[0, 1] = -rotation.z
    m[1, 1] = rotation.w
    m[2, 2] = 1.0
    return m

  @staticmethod
  @immutable
  def from_angle(angle: float64) -> Self:
    return new.from_rotation(Rotator.from_angle(angle))

  @staticmethod
  @immutable
  def look_at(
    position: Vector2 = new.zero,
    target: Vector2 = new.right,
    scale: Vector2 = new.one,
  ) -> Self:
    return new._look_at_impl(position, target, scale)


class Matrix4(MatrixMixin[Vector3, Quaternion]):
  """4×4 矩阵（3D TRS 变换，列主序对齐 tggame ``mat4``）。"""

  _dim: int @const = 4
  _vec_dim: int @const = 3

  @property
  @immutable
  def z_axis(self) -> Vector3:
    return self.get_axis(2)

  @property.setter
  def z_axis(self, value: Vector3) -> None:
    self.set_axis(2, value)

  @property
  @immutable
  def rotation(self) -> Quaternion:
    sc: Vector3 = self.scale
    rx: float64 = self[0, 0] / sc.x
    ry: float64 = self[1, 1] / sc.y
    rz: float64 = self[2, 2] / sc.z
    return new(
      safe_sqrt(1.0 + rx + ry + rz) * 0.5,
      safe_sqrt(1.0 + rx - ry - rz) * 0.5,
      safe_sqrt(1.0 - rx + ry - rz) * 0.5,
      safe_sqrt(1.0 - rx - ry + rz) * 0.5,
    )

  @property
  @immutable
  def euler_angles(self) -> Vector3:
    return self.rotation.to_euler_angles()

  @property.setter
  def euler_angles(self, value: Vector3) -> None:
    self._copy_from(Self.transform(self.position, Quaternion.from_euler_angles(value), self.scale))

  @staticmethod
  @immutable
  def from_angle_x(angle: float64) -> Self:
    rad_a: float64 = radians(angle)
    cos_a: float64 = cos(rad_a)
    sin_a: float64 = sin(rad_a)
    m: Self = new()
    m[1, 1] = cos_a
    m[1, 2] = -sin_a
    m[2, 1] = sin_a
    m[2, 2] = cos_a
    return m

  @staticmethod
  @immutable
  def from_angle_y(angle: float64) -> Self:
    rad_a: float64 = radians(angle)
    cos_a: float64 = cos(rad_a)
    sin_a: float64 = sin(rad_a)
    m: Self = new()
    m[0, 0] = cos_a
    m[0, 2] = sin_a
    m[2, 0] = -sin_a
    m[2, 2] = cos_a
    return m

  @staticmethod
  @immutable
  def from_angle_z(angle: float64) -> Self:
    rad_a: float64 = radians(angle)
    cos_a: float64 = cos(rad_a)
    sin_a: float64 = sin(rad_a)
    m: Self = new()
    m[0, 0] = cos_a
    m[0, 1] = -sin_a
    m[1, 0] = sin_a
    m[1, 1] = cos_a
    return m

  @staticmethod
  @immutable
  def from_rotation(rotation: Quaternion) -> Self:
    x_axis: Vector3 = rotation * Vector3.right
    y_axis: Vector3 = rotation * Vector3.down
    z_axis: Vector3 = rotation * Vector3.forward
    return new.from_axes_origin(x_axis, y_axis, z_axis)

  @staticmethod
  @immutable
  def from_axis_angle(axis: Vector3, angle: float64) -> Self:
    return new.from_rotation(Quaternion.from_axis_angle(axis, angle))

  @staticmethod
  @immutable
  def from_euler_angles(euler_angles: Vector3) -> Self:
    return new.from_rotation(Quaternion.from_euler_angles(euler_angles))

  @staticmethod
  @immutable
  def look_at(
    position: Vector3 = new.zero,
    target: Vector3 = new.forward,
    scale: Vector3 = new.one,
  ) -> Self:
    return new._look_at_impl(position, target, scale)
