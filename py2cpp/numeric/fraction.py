"""有理数 ``Fraction[T: IntegralType]``（对齐 CPython 3.13 ``fractions.Fraction`` 核心语义）。

``T`` 为 ``int`` 或 ``long``；字符串解析、``float`` / ``Decimal`` 构造重载（浮点经 ``float.asIntegerRatio``）。
"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import OverflowError, TypeError, ValueError, ZeroDivisionError
from .decimal import Decimal
from .protocols import IntegralType
from .ratio import floatAsIntegerRatio
from .long import long


@copyable
class Fraction[Scalar: IntegralType]:
  """约分存储的有理数；分母恒正，符号在分子。"""

  _HashModulus: int64 @const = 2305843009213693951
  _HashInf: int @const = 314159

  _num: Scalar
  _den: Scalar

  @overload
  def __init__(self, text: str):
    parsed: (Scalar, Scalar) = Self._parseStr(text)
    self._num = parsed[0]
    self._den = parsed[1]
    self._normalizeInplace()

  @overload
  def __init__(self, f: float64):
    ratio: (long, long) = floatAsIntegerRatio(f)
    self._num = Self._toT(ratio[0])
    self._den = Self._toT(ratio[1])

  @overload
  def __init__(self, dec: Decimal):
    if dec.isNan() or dec.isInfinite():
      raise OverflowError("cannot convert NaN or Infinity to Fraction")
    r: (long, long) = dec.asIntegerRatio()
    self._num = Self._toT(r[0])
    self._den = Self._toT(r[1])

  @staticmethod
  @immutable
  def _tZero() -> Scalar:
    z: int = 0
    out: Scalar = z
    return out

  @staticmethod
  @immutable
  def _tOne() -> Scalar:
    o: int = 1
    out: Scalar = o
    return out

  @staticmethod
  @immutable
  def _abs(v: Scalar) -> Scalar:
    zero: Scalar = Self._tZero()
    if v < zero:
      return -v
    return v

  @overload
  def __init__(self, numerator: Self, denominator: Self):
    n: Scalar = numerator._num * denominator._den
    d: Scalar = denominator._num * numerator._den
    self._num = n
    self._den = d
    self._normalizeInplace()

  @overload
  def __init__(self, numerator: Scalar, denominator: Scalar):
    self._num = numerator
    self._den = denominator
    self._normalizeInplace()

  @overload
  def __init__(self, numerator: Scalar):
    one: Scalar = Self._tOne()
    self._num = numerator
    self._den = one
    self._normalizeInplace()

  @overload
  def __init__(self):
    self._num = Self._tZero()
    self._den = Self._tOne()
    self._normalizeInplace()

  def __copy__(self, other: Self):
    self._num = other._num
    self._den = other._den

  @staticmethod
  @immutable
  def _toT(v: long) -> Scalar:
    if not v:
      z: int = 0
      out: Scalar = z
      return out
    return int(str(v))

  @staticmethod
  @immutable
  def _gcd(a: Scalar, b: Scalar) -> Scalar:
    x: Scalar = Self._abs(a)
    y: Scalar = Self._abs(b)
    zero: Scalar = Self._tZero()
    while y != zero:
      t: Scalar = y
      y = x % y
      x = t
    return x

  @staticmethod
  @immutable
  def _floordiv(a: Scalar, b: Scalar) -> Scalar:
    return a // b

  def _normalizeInplace(self) -> None:
    zero: Scalar = Self._tZero()
    if self._den == zero:
      raise ZeroDivisionError("Fraction(" + str(self._num) + ", 0)")
    g: Scalar = Self._gcd(self._num, self._den)
    if self._den < zero:
      g = -g
    self._num = Self._floordiv(self._num, g)
    self._den = Self._floordiv(self._den, g)

  @staticmethod
  @immutable
  def _parseDigits(s: str) -> str:
    out: str = ""
    for i in range(len(s)):
      c: int = s[i]
      if c != ord("_"):
        out += chr(c)
    return out

  @staticmethod
  @immutable
  def _parseIntPart(s: str) -> long:
    if not s:
      return long("0")
    return long(s)

  @staticmethod
  @immutable
  def _parseStr(text: str) -> (Scalar, Scalar):
    t: str = text.strip()
    if not t:
      raise ValueError("Invalid literal for Fraction: " + repr(text))
    signNeg: bool = False
    start: int = 0
    c0: int = t[0]
    if c0 == ord("-"):
      signNeg = True
      start = 1
    elif c0 == ord("+"):
      start = 1
    body: str = t[start:]
    if not body:
      raise ValueError("Invalid literal for Fraction: " + repr(text))
    slash: int = body.find("/")
    if slash >= 0:
      left: str = Self._parseDigits(body[:slash].strip())
      right: str = Self._parseDigits(body[slash + 1 :].strip())
      if not right:
        raise ValueError("Invalid literal for Fraction: " + repr(text))
      numV: long = Self._parseIntPart(left)
      denV: long = Self._parseIntPart(right)
      if signNeg:
        numV = -numV
      return (Self._toT(numV), Self._toT(denV))
    numV: long = Self._parseIntPart("")
    denV: long = long("1")
    dot: int = body.find(".")
    expPos: int = body.find("e")
    expPos2: int = body.find("E")
    if expPos2 >= 0:
      if expPos < 0 or expPos2 < expPos:
        expPos = expPos2
    intPart: str = ""
    fracPart: str = ""
    expPart: str = ""
    if dot >= 0:
      intPart = Self._parseDigits(body[:dot])
      rest: str = body[dot + 1 :]
      if expPos >= 0:
        fracPart = Self._parseDigits(rest[: expPos - dot - 1])
        expPart = Self._parseDigits(rest[expPos - dot :])
      else:
        fracPart = Self._parseDigits(rest)
    elif expPos >= 0:
      intPart = Self._parseDigits(body[:expPos])
      expPart = Self._parseDigits(body[expPos + 1 :])
    else:
      intPart = Self._parseDigits(body)
    numV = Self._parseIntPart(intPart)
    if fracPart:
      scale: long = new.pow10(len(fracPart))
      fracV: long = Self._parseIntPart(fracPart)
      numV = numV * scale + fracV
      denV = scale
    if expPart:
      expV: long = Self._parseIntPart(expPart)
      if int(expV) >= 0:
        numV *= long.pow10(int(expV))
      else:
        denV *= long.pow10(-int(expV))
    if signNeg:
      numV = -numV
    return (Self._toT(numV), Self._toT(denV))

  @property
  def numerator(self) -> Scalar:
    return self._num

  @property
  def denominator(self) -> Scalar:
    return self._den

  @immutable
  def isInteger(self) -> bool:
    one: Scalar = Self._tOne()
    return self._den == one

  @immutable
  def asIntegerRatio(self) -> (Scalar, Scalar):
    return (self._num, self._den)

  @immutable
  def limitDenominator(self, maxDenominator: int = 1000000) -> Self:
    if maxDenominator < 1:
      raise ValueError("maxDenominator should be at least 1")
    if int(self._den) <= maxDenominator:
      return new(self._num, self._den)
    p0: int = 0
    q0: int = 1
    p1: int = 1
    q1: int = 0
    n: Scalar = self._num
    d: Scalar = self._den
    while True:
      a: Scalar = Self._floordiv(n, d)
      q2: int = q0 + int(a) * q1
      if q2 > maxDenominator:
        break
      p0, q0, p1, q1 = p1, q1, p0 + int(a) * p1, q2
      if q0 < 0:
        q0 = q0
      nr: Scalar = d
      dr: Scalar = n - a * d
      n = nr
      d = dr
    k: int = (maxDenominator - q0) // q1
    if 2 * int(d) * (q0 + k * q1) <= int(self._den):
      return new(p1, q1)
    return new(p0 + k * p1, q0 + k * q1)

  @immutable
  def __float__(self) -> float:
    return float(self._num) / float(self._den)

  @immutable
  def __int__(self) -> int:
    if self._num < 0:
      return -int(Self._floordiv(-self._num, self._den))
    return int(Self._floordiv(self._num, self._den))

  @immutable
  def __bool__(self) -> bool:
    zero: Scalar = Self._tZero()
    return self._num != zero

  @immutable
  def __neg__(self) -> Self:
    return new(-self._num, self._den)

  @immutable
  def __pos__(self) -> Self:
    return new(self._num, self._den)

  @immutable
  def __abs__(self) -> Self:
    n: Scalar = self._num
    zero: Scalar = Self._tZero()
    if n < zero:
      n = -n
    return new(n, self._den)

  @immutable
  def __cmp__(self, other: Self) -> int:
    left: Scalar = self._num * other._den
    right: Scalar = other._num * self._den
    if left < right:
      return -1
    if left > right:
      return 1
    return 0

  @overload
  @immutable
  def __add__(self, other: Self) -> Self:
    na: Scalar = self._num
    da: Scalar = self._den
    nb: Scalar = other._num
    db: Scalar = other._den
    g: Scalar = Self._gcd(da, db)
    one: Scalar = Self._tOne()
    if g == one:
      return new(na * db + da * nb, da * db)
    s: Scalar = Self._floordiv(da, g)
    t: Scalar = na * Self._floordiv(db, g) + nb * s
    g2: Scalar = Self._gcd(t, g)
    if g2 == one:
      return new(t, s * db)
    return new(Self._floordiv(t, g2), s * Self._floordiv(db, g2))

  @overload
  @immutable
  def __add__(self, other: Scalar) -> Self:
    return self + Self(other)

  @overload
  @immutable
  def __add__(self, other: float64) -> float64:
    return float(self) + other

  @overload
  @immutable
  def __sub__(self, other: Self) -> Self:
    na: Scalar = self._num
    da: Scalar = self._den
    nb: Scalar = other._num
    db: Scalar = other._den
    g: Scalar = Self._gcd(da, db)
    one: Scalar = Self._tOne()
    if g == one:
      return new(na * db - da * nb, da * db)
    s: Scalar = Self._floordiv(da, g)
    t: Scalar = na * Self._floordiv(db, g) - nb * s
    g2: Scalar = Self._gcd(t, g)
    if g2 == one:
      return new(t, s * db)
    return new(Self._floordiv(t, g2), s * Self._floordiv(db, g2))

  @overload
  @immutable
  def __sub__(self, other: Scalar) -> Self:
    return self - Self(other)

  @overload
  @immutable
  def __sub__(self, other: float64) -> float64:
    return float(self) - other

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    na: Scalar = self._num
    da: Scalar = self._den
    nb: Scalar = other._num
    db: Scalar = other._den
    g1: Scalar = Self._gcd(na, db)
    g2: Scalar = Self._gcd(nb, da)
    one: Scalar = Self._tOne()
    if g1 == one and g2 == one:
      return new(na * nb, da * db)
    return new(
      Self._floordiv(na, g1) * Self._floordiv(nb, g2),
      Self._floordiv(da, g2) * Self._floordiv(db, g1),
    )

  @overload
  @immutable
  def __mul__(self, other: Scalar) -> Self:
    return self * Self(other)

  @overload
  @immutable
  def __mul__(self, other: float64) -> float64:
    return float(self) * other

  @overload
  @immutable
  def __truediv__(self, other: Self) -> Self:
    zero: Scalar = Self._tZero()
    if other._num == zero:
      raise ZeroDivisionError("division by zero")
    return self * Self(other._den, other._num)

  @overload
  @immutable
  def __truediv__(self, other: Scalar) -> Self:
    return self / Self(other)

  @overload
  @immutable
  def __truediv__(self, other: float64) -> float64:
    return float(self) / other

  @immutable
  def __str__(self) -> str:
    one: Scalar = Self._tOne()
    if self._den == one:
      return str(self._num)
    return str(self._num) + "/" + str(self._den)

  @immutable
  def __repr__(self) -> str:
    return "Fraction(" + str(self._num) + ", " + str(self._den) + ")"

  @immutable
  def __hash__(self) -> int:
    one: Scalar = Self._tOne()
    if self._den == one:
      return hash(self._num)
    try:
      dinv: Scalar = pow(self._den, -1, Self._HashModulus)
    except ValueError:
      return Self._HashInf
    an: Scalar = Self._abs(self._num)
    prod: int = hash(int(an)) * int(dinv)
    h: int = hash(prod)
    if self._num < 0:
      h = -h
    if h == -1:
      return -2
    return h
