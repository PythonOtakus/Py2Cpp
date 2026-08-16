"""复数 ``complex[T: RealType]``（CPython 3.13 ``complex`` 核心语义）。"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import TypeError, ValueError
from .protocols import RealType
from ..math import hypot
from ..math.complex import exp, log


@copyable
class complex[Scalar: RealType = float]:
  """``complex`` / ``complex128``；实部/虚部均为 ``T``。"""

  @staticmethod
  @immutable
  def isInf(z: Self) -> bool:
    return float.isInf(z.real) or float.isInf(z.imag)

  @staticmethod
  @immutable
  def isNaN(z: Self) -> bool:
    return float.isNaN(z.real) or float.isNaN(z.imag)

  @staticmethod
  @immutable
  def isFinite(z: Self) -> bool:
    return float.isFinite(z.real) and float.isFinite(z.imag)

  def __init__(self, real: Scalar = 0, imag: Scalar = 0):
    self._real: Scalar = real
    self._imag: Scalar = imag

  def __copy__(self, other: Self):
    self._real = other._real
    self._imag = other._imag

  @property
  def real(self) -> Scalar:
    return self._real

  @property
  def imag(self) -> Scalar:
    return self._imag

  @staticproperty
  @immutable
  def Infj() -> Self:
    im: float = float.Inf
    return new(0.0, im)

  @staticproperty
  @immutable
  def NaNj() -> Self:
    im: float = float.NaN
    return new(0.0, im)

  @immutable
  def conjugate(self) -> Self:
    return new(self._real, -self._imag)

  @immutable
  def __complex__(self) -> Self:
    return new(self._real, self._imag)

  @immutable
  def __abs__(self) -> Scalar:
    xr: float64 = self._real
    xi: float64 = self._imag
    h: float64 = hypot(xr, xi)
    mag: Scalar = h
    return mag

  @immutable
  def __float__(self) -> float:
    z: Scalar = 0
    if self._imag != z:
      raise TypeError("can't convert complex to float")
    r: float = self._real
    return r

  @immutable
  def __int__(self) -> int:
    z: Scalar = 0
    if self._imag != z:
      raise TypeError("can't convert complex to int")
    n: int = self._real
    return n

  @immutable
  def __eq__(self, other: Self) -> bool:
    return self._real == other._real and self._imag == other._imag

  @immutable
  def __bool__(self) -> bool:
    z: Scalar = 0
    return self._real != z or self._imag != z

  @immutable
  def __pos__(self) -> Self:
    return new(self._real, self._imag)

  @immutable
  def __neg__(self) -> Self:
    return new(-self._real, -self._imag)

  @overload
  @immutable
  def __add__(self, other: Scalar) -> Self:
    z: Scalar = 0
    return new(self._real + other, self._imag + z)

  @overload
  @immutable
  def __add__(self, other: Self) -> Self:
    return new(self._real + other._real, self._imag + other._imag)

  @overload
  @immutable
  def __radd__(self, other: Scalar) -> Self:
    z: Scalar = 0
    return new(other + self._real, z + self._imag)

  @overload
  @immutable
  def __sub__(self, other: Scalar) -> Self:
    z: Scalar = 0
    return new(self._real - other, self._imag - z)

  @overload
  @immutable
  def __sub__(self, other: Self) -> Self:
    return new(self._real - other._real, self._imag - other._imag)

  @overload
  @immutable
  def __rsub__(self, other: Scalar) -> Self:
    z: Scalar = 0
    return new(other - self._real, z - self._imag)

  @overload
  @immutable
  def __mul__(self, other: Scalar) -> Self:
    ar: Scalar = self._real
    ai: Scalar = self._imag
    return new(ar * other, ai * other)

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    ar: Scalar = self._real
    ai: Scalar = self._imag
    br: Scalar = other._real
    bi: Scalar = other._imag
    return new(ar * br - ai * bi, ar * bi + ai * br)

  @overload
  @immutable
  def __rmul__(self, other: Scalar) -> Self:
    return self * other

  @overload
  @immutable
  def __truediv__(self, other: Scalar) -> Self:
    z: Scalar = 0
    if other == z:
      raise ValueError("complex division by zero")
    return new(self._real / other, self._imag / other)

  @overload
  @immutable
  def __truediv__(self, other: Self) -> Self:
    br: Scalar = other._real
    bi: Scalar = other._imag
    denom: Scalar = br * br + bi * bi
    z: Scalar = 0
    if denom == z:
      raise ValueError("complex division by zero")
    ar: Scalar = self._real
    ai: Scalar = self._imag
    return new((ar * br + ai * bi) / denom, (ai * br - ar * bi) / denom)

  @overload
  @immutable
  def __rtruediv__(self, other: Scalar) -> Self:
    br: Scalar = self._real
    bi: Scalar = self._imag
    denom: Scalar = br * br + bi * bi
    z: Scalar = 0
    if denom == z:
      raise ValueError("complex division by zero")
    return new(other * br / denom, -other * bi / denom)

  @overload
  @immutable
  def __pow__(self, exponent: int) -> Self:
    if exponent == 0:
      return new(1, 0)
    if exponent < 0:
      one: Self = new(1, 0)
      return one / (self ** -exponent)
    out: Self = new(1, 0)
    base: Self = new(self._real, self._imag)
    e: int = exponent
    while e > 0:
      if e & 1:
        out *= base
      base *= base
      e //= 2
    return out

  @overload
  @immutable
  def __pow__(self, exponent: Scalar) -> Self:
    w: Self = log(self)
    sr: Scalar = w._real * exponent
    si: Scalar = w._imag * exponent
    return exp(Self(sr, si))

  @overload
  @immutable
  def __pow__(self, exponent: Self) -> Self:
    w: Self = log(self)
    prod: Self = w * exponent
    return exp(prod)

  @overload
  @immutable
  def __rpow__(self, other: Scalar) -> Self:
    z: Scalar = 0
    base: Self = new(other, z)
    return base ** self


type complex128 = complex[float64]
