"""空间颜色：``Color`` / ``ColorMatrix``（对齐 tggame ``color`` 数值色子集；分量约定 [0,1]）。"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import IndexError
from ..numeric.protocols import RealType
from ..math import almost, clamp01, fabs, floor, lerp, pow, safeSqrt


@copyable
class Color[Scalar: RealType = float]:
  """浮点 RGBA 颜色（分量钳制到 [0,1]；供材质、清屏、顶点色）。"""

  def __init__(
    self,
    r: Scalar = 0.0,
    g: Scalar = 0.0,
    b: Scalar = 0.0,
    a: Scalar = 1.0,
  ):
    self._data: Scalar[:4] = new()
    self._data.unsafeSet(0, clamp01(r))
    self._data.unsafeSet(1, clamp01(g))
    self._data.unsafeSet(2, clamp01(b))
    self._data.unsafeSet(3, clamp01(a))

  def _copyFrom(self, src: Self) -> None:
    for i in inlineRange(4):
      self._data.unsafeSet(i, src._data.unsafeGet(i))

  @property
  @immutable
  def r(self) -> Scalar:
    return self._data.unsafeGet(0)

  @property.setter
  def r(self, value: Scalar) -> None:
    self._data.unsafeSet(0, clamp01(value))

  @property
  @immutable
  def g(self) -> Scalar:
    return self._data.unsafeGet(1)

  @property.setter
  def g(self, value: Scalar) -> None:
    self._data.unsafeSet(1, clamp01(value))

  @property
  @immutable
  def b(self) -> Scalar:
    return self._data.unsafeGet(2)

  @property.setter
  def b(self, value: Scalar) -> None:
    self._data.unsafeSet(2, clamp01(value))

  @property
  @immutable
  def a(self) -> Scalar:
    return self._data.unsafeGet(3)

  @property.setter
  def a(self, value: Scalar) -> None:
    self._data.unsafeSet(3, clamp01(value))

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
  def __getitem__(self, index: int) -> Scalar:
    if index < 0 or index >= 4:
      raise IndexError("color index out of range")
    return self._data.unsafeGet(index)

  def __setitem__(self, index: int, value: Scalar) -> None:
    if index < 0 or index >= 4:
      raise IndexError("color index out of range")
    self._data.unsafeSet(index, clamp01(value))

  @immutable
  def __bool__(self) -> bool:
    return self.a > 0.0

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in inlineRange(4):
      if not almost(self._data.unsafeGet(i), other._data.unsafeGet(i)):
        return False
    return True

  @immutable
  def __pos__(self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    out._copyFrom(self)
    return out

  @immutable
  def __invert__(self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inlineRange(4):
      out._data.unsafeSet(i, clamp01(1.0 - self._data.unsafeGet(i)))
    return out

  @immutable
  def __and__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inlineRange(4):
      a: Scalar = self._data.unsafeGet(i)
      b: Scalar = other._data.unsafeGet(i)
      out._data.unsafeSet(i, a if a < b else b)
    return out

  def __iand__(self, other: Self) -> Self:
    self._copyFrom(self & other)
    return self

  @immutable
  def __or__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inlineRange(4):
      a: Scalar = self._data.unsafeGet(i)
      b: Scalar = other._data.unsafeGet(i)
      out._data.unsafeSet(i, a if a > b else b)
    return out

  def __ior__(self, other: Self) -> Self:
    self._copyFrom(self | other)
    return self

  @immutable
  def __add__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inlineRange(4):
      out._data.unsafeSet(
        i,
        clamp01(self._data.unsafeGet(i) + other._data.unsafeGet(i)),
      )
    return out

  def __iadd__(self, other: Self) -> Self:
    for i in inlineRange(4):
      self._data.unsafeSet(
        i,
        clamp01(self._data.unsafeGet(i) + other._data.unsafeGet(i)),
      )
    return self

  @immutable
  def __sub__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inlineRange(4):
      out._data.unsafeSet(
        i,
        clamp01(self._data.unsafeGet(i) - other._data.unsafeGet(i)),
      )
    return out

  def __isub__(self, other: Self) -> Self:
    for i in inlineRange(4):
      self._data.unsafeSet(
        i,
        clamp01(self._data.unsafeGet(i) - other._data.unsafeGet(i)),
      )
    return self

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inlineRange(4):
      out._data.unsafeSet(
        i,
        clamp01(self._data.unsafeGet(i) * other._data.unsafeGet(i)),
      )
    return out

  @overload
  @immutable
  def __mul__(self, other: Scalar) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inlineRange(4):
      out._data.unsafeSet(i, clamp01(self._data.unsafeGet(i) * other))
    return out

  @overload
  @immutable
  def __rmul__(self, other: Scalar) -> Self:
    return self * other

  @overload
  def __imul__(self, other: Self) -> Self:
    for i in inlineRange(4):
      self._data.unsafeSet(
        i,
        clamp01(self._data.unsafeGet(i) * other._data.unsafeGet(i)),
      )
    return self

  @overload
  def __imul__(self, other: Scalar) -> Self:
    for i in inlineRange(4):
      self._data.unsafeSet(i, clamp01(self._data.unsafeGet(i) * other))
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
    for i in inlineRange(4):
      out._data.unsafeSet(
        i,
        clamp01(self._data.unsafeGet(i) / other._data.unsafeGet(i)),
      )
    return out

  def __itruediv__(self, other: Self) -> Self:
    for i in inlineRange(4):
      self._data.unsafeSet(
        i,
        clamp01(self._data.unsafeGet(i) / other._data.unsafeGet(i)),
      )
    return self

  @immutable
  def __pow__(self, exponent: Scalar) -> Self:
    out: Self = new(0.0, 0.0, 0.0, 0.0)
    for i in inlineRange(4):
      out._data.unsafeSet(i, clamp01(pow(self._data.unsafeGet(i), exponent)))
    return out

  def __ipow__(self, exponent: Scalar) -> Self:
    self._copyFrom(self ** exponent)
    return self

  @immutable
  def withAlpha(self, alpha: Scalar) -> Self:
    return new(self.r, self.g, self.b, alpha)

  @immutable
  def lerp(self, other: Self, t: Scalar) -> Self:
    k: Scalar = clamp01(t)
    return new(
      lerp(self.r, other.r, k),
      lerp(self.g, other.g, k),
      lerp(self.b, other.b, k),
      lerp(self.a, other.a, k),
    )

  @immutable
  def scaled(self, factor: Scalar) -> Self:
    return self * factor

  @immutable
  def toArgb(self) -> int:
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
  def fromArgb(argb: int) -> Self:
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
class ColorMatrix[Scalar: RealType = float]:
  """5×5 颜色仿射矩阵（齐次 RGBA + 平移列）；``apply`` 作用于 ``Color``。"""

  _dim: int @const = 5

  def __init__(self, identity: bool = True):
    self._data: Scalar[:5, :5] = new()
    if identity:
      for i in inlineRange(5):
        for j in inlineRange(5):
          self._data.unsafeSet(i, j, 1.0 if i == j else 0.0)

  def _copyFrom(self, src: Self) -> None:
    for i in inlineRange(5):
      for j in inlineRange(5):
        self._data.unsafeSet(i, j, src._data.unsafeGet(i, j))

  @staticproperty
  @immutable
  def identity() -> Self:
    return new(True)

  @staticproperty
  @immutable
  def zero() -> Self:
    return new(False)

  @immutable
  def __getitem__(self, index: (int, int)) -> Scalar:
    i: int = index[0]
    j: int = index[1]
    if i < 0 or i >= 5 or j < 0 or j >= 5:
      raise IndexError("color matrix index out of range")
    return self._data.unsafeGet(i, j)

  def __setitem__(self, index: (int, int), value: Scalar) -> None:
    i: int = index[0]
    j: int = index[1]
    if i < 0 or i >= 5 or j < 0 or j >= 5:
      raise IndexError("color matrix index out of range")
    self._data.unsafeSet(i, j, value)

  @immutable
  def unsafeGet(self, i: int, j: int) -> Scalar:
    return self._data.unsafeGet(i, j)

  def unsafeSet(self, i: int, j: int, value: Scalar) -> None:
    self._data.unsafeSet(i, j, value)

  @immutable
  def __bool__(self) -> bool:
    for i in inlineRange(5):
      for j in inlineRange(5):
        if not almost(self._data.unsafeGet(i, j), 0.0):
          return True
    return False

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in inlineRange(5):
      for j in inlineRange(5):
        if not almost(self._data.unsafeGet(i, j), other._data.unsafeGet(i, j)):
          return False
    return True

  @property
  @immutable
  def det(self) -> Scalar:
    tmp: Scalar[:5, :5] = new()
    for i in inlineRange(5):
      for j in inlineRange(5):
        tmp[i, j] = self.unsafeGet(i, j)
    sign: Scalar = 1.0
    prod: Scalar = 1.0
    for k in inlineRange(5):
      pivRow: int = k
      pivVal: Scalar = fabs(tmp[k, k])
      for r in inlineRange(k + 1, 5):
        v: Scalar = fabs(tmp[r, k])
        if v > pivVal:
          pivVal = v
          pivRow = r
      if pivRow != k:
        sign = -sign
        for c in inlineRange(5):
          swapVal: Scalar = tmp[k, c]
          tmp[k, c] = tmp[pivRow, c]
          tmp[pivRow, c] = swapVal
      pivot: Scalar = tmp[k, k]
      prod *= pivot
      for r in inlineRange(k + 1, 5):
        factor: Scalar = tmp[r, k] / pivot
        tmp[r, k] = 0.0
        for c in inlineRange(k + 1, 5):
          tmp[r, c] -= factor * tmp[k, c]
    return sign * prod

  @immutable
  def _invGauss(self) -> Self:
    tmp: Scalar[:5, :10] = new()
    for i in inlineRange(5):
      for j in inlineRange(5):
        tmp[i, j] = self.unsafeGet(i, j)
        tmp[i, j + 5] = 0.0
      tmp[i, i + 5] = 1.0
    for k in inlineRange(5):
      pivRow: int = k
      pivVal: Scalar = fabs(tmp[k, k])
      for r in inlineRange(k + 1, 5):
        v: Scalar = fabs(tmp[r, k])
        if v > pivVal:
          pivVal = v
          pivRow = r
      if pivRow != k:
        for c in inlineRange(10):
          swapVal: Scalar = tmp[k, c]
          tmp[k, c] = tmp[pivRow, c]
          tmp[pivRow, c] = swapVal
      pivot: Scalar = tmp[k, k]
      for c in inlineRange(10):
        tmp[k, c] /= pivot
      for r in inlineRange(5):
        if r != k:
          factor: Scalar = tmp[r, k]
          for c in inlineRange(10):
            tmp[r, c] -= factor * tmp[k, c]
    result: Self = new(False)
    for i in inlineRange(5):
      for j in inlineRange(5):
        result.unsafeSet(i, j, tmp[i, j + 5])
    return result

  @property
  @immutable
  def inv(self) -> Self:
    return self._invGauss()

  @immutable
  def apply(self, color: Color[Scalar]) -> Color[Scalar]:
    """``outI = sum_j M[i,j]*c_j + M[i,4]``（``c_4=1``），结果分量再钳制。"""
    out: Scalar[:4] = new()
    for i in inlineRange(4):
      acc: Scalar = self.unsafeGet(i, 4)
      for j in inlineRange(4):
        acc += self.unsafeGet(i, j) * color[j]
      out[i] = acc
    return new(out[0], out[1], out[2], out[3])

  @immutable
  def dot(self, other: Self) -> Scalar:
    acc: Scalar = 0.0
    for i in inlineRange(5):
      for j in inlineRange(5):
        acc += self.unsafeGet(i, j) * other.unsafeGet(i, j)
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
  def __pos__(self) -> Self:
    out: Self = new(False)
    out._copyFrom(self)
    return out

  @immutable
  def __neg__(self) -> Self:
    out: Self = new(False)
    for i in inlineRange(5):
      for j in inlineRange(5):
        out.unsafeSet(i, j, -self.unsafeGet(i, j))
    return out

  @immutable
  def __add__(self, other: Self) -> Self:
    out: Self = new(False)
    for i in inlineRange(5):
      for j in inlineRange(5):
        out.unsafeSet(i, j, self.unsafeGet(i, j) + other.unsafeGet(i, j))
    return out

  def __iadd__(self, other: Self) -> Self:
    for i in inlineRange(5):
      for j in inlineRange(5):
        self.unsafeSet(i, j, self.unsafeGet(i, j) + other.unsafeGet(i, j))
    return self

  @immutable
  def __sub__(self, other: Self) -> Self:
    out: Self = new(False)
    for i in inlineRange(5):
      for j in inlineRange(5):
        out.unsafeSet(i, j, self.unsafeGet(i, j) - other.unsafeGet(i, j))
    return out

  def __isub__(self, other: Self) -> Self:
    for i in inlineRange(5):
      for j in inlineRange(5):
        self.unsafeSet(i, j, self.unsafeGet(i, j) - other.unsafeGet(i, j))
    return self

  @overload
  @immutable
  def __mul__(self, other: Scalar) -> Self:
    out: Self = new(False)
    for i in inlineRange(5):
      for j in inlineRange(5):
        out.unsafeSet(i, j, self.unsafeGet(i, j) * other)
    return out

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    return self @ other

  @overload
  @immutable
  def __rmul__(self, other: Scalar) -> Self:
    return self * other

  @overload
  def __imul__(self, other: Scalar) -> Self:
    for i in inlineRange(5):
      for j in inlineRange(5):
        self.unsafeSet(i, j, self.unsafeGet(i, j) * other)
    return self

  @overload
  def __imul__(self, other: Self) -> Self:
    m: Self = self @ other
    self._copyFrom(m)
    return self

  @immutable
  def __matmul__(self, other: Self) -> Self:
    out: Self = new(False)
    for i in inlineRange(5):
      for j in inlineRange(5):
        acc: Scalar = 0.0
        for k in inlineRange(5):
          acc += self.unsafeGet(i, k) * other.unsafeGet(k, j)
        out.unsafeSet(i, j, acc)
    return out

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
    self *= s
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

  @staticmethod
  @immutable
  def grayscale() -> Self:
    """亮度灰度（ITU-R BT.601 近似）。"""
    m: Self = new(False)
    wr: Scalar = 0.299
    wg: Scalar = 0.587
    wb: Scalar = 0.114
    for i in inlineRange(3):
      m.unsafeSet(i, 0, wr)
      m.unsafeSet(i, 1, wg)
      m.unsafeSet(i, 2, wb)
      m.unsafeSet(i, 3, 0.0)
      m.unsafeSet(i, 4, 0.0)
    for i in inlineRange(3, 5):
      for j in inlineRange(5):
        m.unsafeSet(i, j, 1.0 if i == j else 0.0)
    return m
