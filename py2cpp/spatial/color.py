"""空间颜色：``Color`` / ``ColorMatrix``（对齐 tggame ``color`` 数值色子集；分量约定 [0,1]）。"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import IndexError
from ..math import almost, clamp01, fabs, floor, lerp, pow, safe_sqrt


@copyable
class Color:
  """浮点 RGBA 颜色（分量钳制到 [0,1]；供材质、清屏、顶点色）。"""

  def __init__(
    self,
    r: float64 = 0.0,
    g: float64 = 0.0,
    b: float64 = 0.0,
    a: float64 = 1.0,
  ):
    self._data: float64[:4] = new()
    self._data.unsafe_set(0, clamp01(r))
    self._data.unsafe_set(1, clamp01(g))
    self._data.unsafe_set(2, clamp01(b))
    self._data.unsafe_set(3, clamp01(a))

  def _copy_from(self, src: Self) -> None:
    for i in inline_range(4):
      self._data.unsafe_set(i, src._data.unsafe_get(i))

  @property
  @immutable
  def r(self) -> float64:
    return self._data.unsafe_get(0)

  @property.setter
  def r(self, value: float64) -> None:
    self._data.unsafe_set(0, clamp01(value))

  @property
  @immutable
  def g(self) -> float64:
    return self._data.unsafe_get(1)

  @property.setter
  def g(self, value: float64) -> None:
    self._data.unsafe_set(1, clamp01(value))

  @property
  @immutable
  def b(self) -> float64:
    return self._data.unsafe_get(2)

  @property.setter
  def b(self, value: float64) -> None:
    self._data.unsafe_set(2, clamp01(value))

  @property
  @immutable
  def a(self) -> float64:
    return self._data.unsafe_get(3)

  @property.setter
  def a(self, value: float64) -> None:
    self._data.unsafe_set(3, clamp01(value))

  @staticproperty
  @immutable
  def clear() -> Self:
    return new(0.0, 0.0, 0.0, 0.0)

  @staticproperty
  @immutable
  def black() -> Self:
    return new(0.0, 0.0, 0.0, 1.0)

  @staticproperty
  @immutable
  def white() -> Self:
    return new(1.0, 1.0, 1.0, 1.0)

  @staticproperty
  @immutable
  def red() -> Self:
    return new(1.0, 0.0, 0.0, 1.0)

  @staticproperty
  @immutable
  def green() -> Self:
    return new(0.0, 1.0, 0.0, 1.0)

  @staticproperty
  @immutable
  def blue() -> Self:
    return new(0.0, 0.0, 1.0, 1.0)

  @immutable
  def __len__(self) -> int:
    return 4

  @immutable
  def __getitem__(self, index: int) -> float64:
    if index < 0 or index >= 4:
      raise IndexError("color index out of range")
    return self._data.unsafe_get(index)

  def __setitem__(self, index: int, value: float64) -> None:
    if index < 0 or index >= 4:
      raise IndexError("color index out of range")
    self._data.unsafe_set(index, clamp01(value))

  @immutable
  def __bool__(self) -> bool:
    return self.a > 0.0

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in inline_range(4):
      if not almost(self._data.unsafe_get(i), other._data.unsafe_get(i)):
        return False
    return True

  @immutable
  def __pos__(self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    out._copy_from(self)
    return out

  @immutable
  def __invert__(self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inline_range(4):
      out._data.unsafe_set(i, clamp01(1.0 - self._data.unsafe_get(i)))
    return out

  @immutable
  def __and__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inline_range(4):
      a: float64 = self._data.unsafe_get(i)
      b: float64 = other._data.unsafe_get(i)
      out._data.unsafe_set(i, a if a < b else b)
    return out

  def __iand__(self, other: Self) -> Self:
    self._copy_from(self & other)
    return self

  @immutable
  def __or__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inline_range(4):
      a: float64 = self._data.unsafe_get(i)
      b: float64 = other._data.unsafe_get(i)
      out._data.unsafe_set(i, a if a > b else b)
    return out

  def __ior__(self, other: Self) -> Self:
    self._copy_from(self | other)
    return self

  @immutable
  def __add__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inline_range(4):
      out._data.unsafe_set(
        i,
        clamp01(self._data.unsafe_get(i) + other._data.unsafe_get(i)),
      )
    return out

  def __iadd__(self, other: Self) -> Self:
    for i in inline_range(4):
      self._data.unsafe_set(
        i,
        clamp01(self._data.unsafe_get(i) + other._data.unsafe_get(i)),
      )
    return self

  @immutable
  def __sub__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inline_range(4):
      out._data.unsafe_set(
        i,
        clamp01(self._data.unsafe_get(i) - other._data.unsafe_get(i)),
      )
    return out

  def __isub__(self, other: Self) -> Self:
    for i in inline_range(4):
      self._data.unsafe_set(
        i,
        clamp01(self._data.unsafe_get(i) - other._data.unsafe_get(i)),
      )
    return self

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inline_range(4):
      out._data.unsafe_set(
        i,
        clamp01(self._data.unsafe_get(i) * other._data.unsafe_get(i)),
      )
    return out

  @overload
  @immutable
  def __mul__(self, other: float64) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inline_range(4):
      out._data.unsafe_set(i, clamp01(self._data.unsafe_get(i) * other))
    return out

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  @overload
  def __imul__(self, other: Self) -> Self:
    for i in inline_range(4):
      self._data.unsafe_set(
        i,
        clamp01(self._data.unsafe_get(i) * other._data.unsafe_get(i)),
      )
    return self

  @overload
  def __imul__(self, other: float64) -> Self:
    for i in inline_range(4):
      self._data.unsafe_set(i, clamp01(self._data.unsafe_get(i) * other))
    return self

  @immutable
  def __matmul__(self, other: Self) -> Self:
    return self * other

  def __imatmul__(self, other: Self) -> Self:
    self *= other
    return self

  @immutable
  def __truediv__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inline_range(4):
      out._data.unsafe_set(
        i,
        clamp01(self._data.unsafe_get(i) / other._data.unsafe_get(i)),
      )
    return out

  def __itruediv__(self, other: Self) -> Self:
    for i in inline_range(4):
      self._data.unsafe_set(
        i,
        clamp01(self._data.unsafe_get(i) / other._data.unsafe_get(i)),
      )
    return self

  @immutable
  def __pow__(self, exponent: float64) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inline_range(4):
      out._data.unsafe_set(i, clamp01(pow(self._data.unsafe_get(i), exponent)))
    return out

  def __ipow__(self, exponent: float64) -> Self:
    self._copy_from(self ** exponent)
    return self

  @immutable
  def with_alpha(self, alpha: float64) -> Self:
    return new(self.r, self.g, self.b, alpha)

  @immutable
  def lerp(self, other: Self, t: float64) -> Self:
    k: float64 = clamp01(t)
    return new(
      lerp(self.r, other.r, k),
      lerp(self.g, other.g, k),
      lerp(self.b, other.b, k),
      lerp(self.a, other.a, k),
    )

  @immutable
  def scaled(self, factor: float64) -> Self:
    return self * factor

  @immutable
  def to_argb(self) -> int:
    ai: int = int(self.a * 255.0 + 0.5)
    ri: int = int(self.r * 255.0 + 0.5)
    gi: int = int(self.g * 255.0 + 0.5)
    bi: int = int(self.b * 255.0 + 0.5)
    if ai < 0:
      ai = 0
    if ai > 255:
      ai = 255
    if ri < 0:
      ri = 0
    if ri > 255:
      ri = 255
    if gi < 0:
      gi = 0
    if gi > 255:
      gi = 255
    if bi < 0:
      bi = 0
    if bi > 255:
      bi = 255
    return (ai << 24) | (ri << 16) | (gi << 8) | bi

  @staticmethod
  @immutable
  def from_argb(argb: int) -> Self:
    ai: int = (argb >> 24) & 255
    ri: int = (argb >> 16) & 255
    gi: int = (argb >> 8) & 255
    bi: int = argb & 255
    return new(
      float64(ri) / 255.0,
      float64(gi) / 255.0,
      float64(bi) / 255.0,
      float64(ai) / 255.0,
    )

  @immutable
  def __repr__(self) -> str:
    return "Color(%s,%s,%s,%s)" % (self.r, self.g, self.b, self.a)


@copyable
class ColorMatrix:
  """5×5 颜色仿射矩阵（齐次 RGBA + 平移列）；``apply`` 作用于 ``Color``。"""

  _dim: int @const = 5

  def __init__(self, identity: bool = True):
    self._data: float64[:5, :5] = new()
    if identity:
      for i in inline_range(5):
        for j in inline_range(5):
          self._data.unsafe_set(i, j, 1.0 if i == j else 0.0)

  def _copy_from(self, src: Self) -> None:
    for i in inline_range(5):
      for j in inline_range(5):
        self._data.unsafe_set(i, j, src._data.unsafe_get(i, j))

  @staticproperty
  @immutable
  def identity() -> Self:
    return new(True)

  @staticproperty
  @immutable
  def zero() -> Self:
    return new(False)

  @immutable
  def __getitem__(self, index: (int, int)) -> float64:
    i: int = index[0]
    j: int = index[1]
    if i < 0 or i >= 5 or j < 0 or j >= 5:
      raise IndexError("color matrix index out of range")
    return self._data.unsafe_get(i, j)

  def __setitem__(self, index: (int, int), value: float64) -> None:
    i: int = index[0]
    j: int = index[1]
    if i < 0 or i >= 5 or j < 0 or j >= 5:
      raise IndexError("color matrix index out of range")
    self._data.unsafe_set(i, j, value)

  @immutable
  def unsafe_get(self, i: int, j: int) -> float64:
    return self._data.unsafe_get(i, j)

  def unsafe_set(self, i: int, j: int, value: float64) -> None:
    self._data.unsafe_set(i, j, value)

  @immutable
  def __bool__(self) -> bool:
    for i in inline_range(5):
      for j in inline_range(5):
        if not almost(self._data.unsafe_get(i, j), 0.0):
          return True
    return False

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in inline_range(5):
      for j in inline_range(5):
        if not almost(self._data.unsafe_get(i, j), other._data.unsafe_get(i, j)):
          return False
    return True

  @property
  @immutable
  def det(self) -> float64:
    tmp: float64[:5, :5] = new()
    for i in inline_range(5):
      for j in inline_range(5):
        tmp[i, j] = self.unsafe_get(i, j)
    sign: float64 = 1.0
    prod: float64 = 1.0
    for k in inline_range(5):
      piv_row: int = k
      piv_val: float64 = fabs(tmp[k, k])
      for r in inline_range(k + 1, 5):
        v: float64 = fabs(tmp[r, k])
        if v > piv_val:
          piv_val = v
          piv_row = r
      if piv_row != k:
        sign = -sign
        for c in inline_range(5):
          swap_val: float64 = tmp[k, c]
          tmp[k, c] = tmp[piv_row, c]
          tmp[piv_row, c] = swap_val
      pivot: float64 = tmp[k, k]
      prod *= pivot
      for r in inline_range(k + 1, 5):
        factor: float64 = tmp[r, k] / pivot
        tmp[r, k] = 0.0
        for c in inline_range(k + 1, 5):
          tmp[r, c] -= factor * tmp[k, c]
    return sign * prod

  @immutable
  def _inv_gauss(self) -> Self:
    tmp: float64[:5, :10] = new()
    for i in inline_range(5):
      for j in inline_range(5):
        tmp[i, j] = self.unsafe_get(i, j)
        tmp[i, j + 5] = 0.0
      tmp[i, i + 5] = 1.0
    for k in inline_range(5):
      piv_row: int = k
      piv_val: float64 = fabs(tmp[k, k])
      for r in inline_range(k + 1, 5):
        v: float64 = fabs(tmp[r, k])
        if v > piv_val:
          piv_val = v
          piv_row = r
      if piv_row != k:
        for c in inline_range(10):
          swap_val: float64 = tmp[k, c]
          tmp[k, c] = tmp[piv_row, c]
          tmp[piv_row, c] = swap_val
      pivot: float64 = tmp[k, k]
      for c in inline_range(10):
        tmp[k, c] /= pivot
      for r in inline_range(5):
        if r != k:
          factor: float64 = tmp[r, k]
          for c in inline_range(10):
            tmp[r, c] -= factor * tmp[k, c]
    result: Self = new(False)
    for i in inline_range(5):
      for j in inline_range(5):
        result.unsafe_set(i, j, tmp[i, j + 5])
    return result

  @property
  @immutable
  def inv(self) -> Self:
    return self._inv_gauss()

  @immutable
  def apply(self, color: Color) -> Color:
    """``out_i = sum_j M[i,j]*c_j + M[i,4]``（``c_4=1``），结果分量再钳制。"""
    out: float64[:4] = new()
    for i in inline_range(4):
      acc: float64 = self.unsafe_get(i, 4)
      for j in inline_range(4):
        acc += self.unsafe_get(i, j) * color[j]
      out[i] = acc
    return new(out[0], out[1], out[2], out[3])

  @immutable
  def dot(self, other: Self) -> float64:
    acc: float64 = 0.0
    for i in inline_range(5):
      for j in inline_range(5):
        acc += self.unsafe_get(i, j) * other.unsafe_get(i, j)
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
  def __pos__(self) -> Self:
    out: Self = new(False)
    out._copy_from(self)
    return out

  @immutable
  def __neg__(self) -> Self:
    out: Self = new(False)
    for i in inline_range(5):
      for j in inline_range(5):
        out.unsafe_set(i, j, -self.unsafe_get(i, j))
    return out

  @immutable
  def __add__(self, other: Self) -> Self:
    out: Self = new(False)
    for i in inline_range(5):
      for j in inline_range(5):
        out.unsafe_set(i, j, self.unsafe_get(i, j) + other.unsafe_get(i, j))
    return out

  def __iadd__(self, other: Self) -> Self:
    for i in inline_range(5):
      for j in inline_range(5):
        self.unsafe_set(i, j, self.unsafe_get(i, j) + other.unsafe_get(i, j))
    return self

  @immutable
  def __sub__(self, other: Self) -> Self:
    out: Self = new(False)
    for i in inline_range(5):
      for j in inline_range(5):
        out.unsafe_set(i, j, self.unsafe_get(i, j) - other.unsafe_get(i, j))
    return out

  def __isub__(self, other: Self) -> Self:
    for i in inline_range(5):
      for j in inline_range(5):
        self.unsafe_set(i, j, self.unsafe_get(i, j) - other.unsafe_get(i, j))
    return self

  @overload
  @immutable
  def __mul__(self, other: float64) -> Self:
    out: Self = new(False)
    for i in inline_range(5):
      for j in inline_range(5):
        out.unsafe_set(i, j, self.unsafe_get(i, j) * other)
    return out

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    return self @ other

  @overload
  @immutable
  def __rmul__(self, other: float64) -> Self:
    return self * other

  @overload
  def __imul__(self, other: float64) -> Self:
    for i in inline_range(5):
      for j in inline_range(5):
        self.unsafe_set(i, j, self.unsafe_get(i, j) * other)
    return self

  @overload
  def __imul__(self, other: Self) -> Self:
    m: Self = self @ other
    self._copy_from(m)
    return self

  @immutable
  def __matmul__(self, other: Self) -> Self:
    out: Self = new(False)
    for i in inline_range(5):
      for j in inline_range(5):
        acc: float64 = 0.0
        for k in inline_range(5):
          acc += self.unsafe_get(i, k) * other.unsafe_get(k, j)
        out.unsafe_set(i, j, acc)
    return out

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
    self *= s
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

  @staticmethod
  @immutable
  def grayscale() -> Self:
    """亮度灰度（ITU-R BT.601 近似）。"""
    m: Self = new(False)
    wr: float64 = 0.299
    wg: float64 = 0.587
    wb: float64 = 0.114
    for i in inline_range(3):
      m.unsafe_set(i, 0, wr)
      m.unsafe_set(i, 1, wg)
      m.unsafe_set(i, 2, wb)
      m.unsafe_set(i, 3, 0.0)
      m.unsafe_set(i, 4, 0.0)
    for i in inline_range(3, 5):
      for j in inline_range(5):
        m.unsafe_set(i, j, 1.0 if i == j else 0.0)
    return m
