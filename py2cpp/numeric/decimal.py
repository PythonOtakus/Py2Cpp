"""十进制定点 ``Decimal``（对齐 CPython 3.13 ``decimal.Decimal`` P0 子集）。

模块级 ``Context``（``prec=28``、``RoundingModeEnum.RoundHalfEven``）、``getContext``/``setContext``、
字符串构造、四则比较、``quantize``/``normalize``、``NaN``/``Infinity``。
"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import InvalidOperationError, OverflowError, ValueError
from .varint import varint


@enum
class RoundingModeEnum:
  """``decimal`` 舍入模式（对齐 CPython ``decimal`` 模块常量）。"""

  RoundDown = 0
  RoundHalfUp = 1
  RoundHalfEven = 2
  RoundCeiling = 3
  RoundFloor = 4
  RoundUp = 5
  RoundHalfDown = 6
  Round05up = 7


@copyable
@native_name("PyDecimalContext")
class Context:
  """算术上下文（``prec`` / ``rounding``）。"""

  def __init__(self, prec: int = 28, rounding: int = 2):
    self.prec: int = prec
    self.rounding: int = rounding
    self.Emin: int = -999999
    self.Emax: int = 999999
    self.traps: int = 0
    self.flags: int = 0

  def __copy__(self, other: Self):
    self.prec = other.prec
    self.rounding = other.rounding
    self.Emin = other.Emin
    self.Emax = other.Emax
    self.traps = other.traps
    self.flags = other.flags


_defaultContext: Context = new()


@immutable
def getContext() -> Context:
  return _defaultContext


def setContext(ctx: Context) -> None:
  _defaultContext.prec = ctx.prec
  _defaultContext.rounding = ctx.rounding
  _defaultContext.Emin = ctx.Emin
  _defaultContext.Emax = ctx.Emax
  _defaultContext.traps = ctx.traps
  _defaultContext.flags = ctx.flags


@copyable
class Decimal:
  """符号 + 系数 × 10^指数；特殊值 ``NaN`` / ``Inf``。"""

  _sign: bool
  _coeff: varint
  _exp: int
  _special: int

  @staticmethod
  @immutable
  def _pow10(n: int) -> varint:
    return new.pow10(n)

  @overload
  def __init__(self):
    zero: varint = 0
    self._sign = False
    self._coeff = zero
    self._exp = 0
    self._special = 0

  @overload
  def __init__(self, text: str):
    zero: varint = 0
    self._sign = False
    self._coeff = zero
    self._exp = 0
    self._special = 0
    self._initFromStr(text)

  @overload
  def __init__(self, value: int):
    zero: varint = 0
    self._sign = False
    self._coeff = zero
    self._exp = 0
    self._special = 0
    if value < 0:
      self._sign = True
      self._coeff = varint(str(-value))
    else:
      self._coeff = varint(str(value))
    self._exp = 0
    self._normalizeCoeff()

  def __copy__(self, other: Self):
    self._special = other._special
    self._sign = other._sign
    self._coeff = other._coeff
    self._exp = other._exp

  @staticmethod
  @immutable
  def _parseDigitsOnly(s: str) -> str:
    out: str = ""
    for i in range(len(s)):
      c: int = s[i]
      if c != ord("_"):
        out += chr(c)
    return out

  def _initFromStr(self, text: str) -> None:
    t: str = text.strip()
    if not t:
      raise ValueError("Invalid literal for Decimal: " + repr(text))
    lower: str = t.lower()
    match lower:
      case "nan":
        self._special = 1
        return
      case "inf":
        self._special = 2
        return
      case "infinity":
        self._special = 2
        return
      case "-inf":
        self._sign = True
        self._special = 2
        return
      case "-infinity":
        self._sign = True
        self._special = 2
        return
      case _:
        pass
    signNeg: bool = False
    start: int = 0
    c0: int = t[0]
    if c0 == ord("-"):
      signNeg = True
      start = 1
    elif c0 == ord("+"):
      start = 1
    body: str = Self._parseDigitsOnly(t[start:])
    if not body:
      raise ValueError("Invalid literal for Decimal: " + repr(text))
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
      intPart = body[:dot]
      rest: str = body[dot + 1 :]
      if expPos >= 0:
        fracPart = rest[: expPos - dot - 1]
        expPart = rest[expPos - dot :]
      else:
        fracPart = rest
    elif expPos >= 0:
      intPart = body[:expPos]
      expPart = body[expPos + 1 :]
    else:
      intPart = body
    coeff: varint = varint(intPart if intPart else "0")
    expVal: int = 0
    if fracPart:
      coeff = coeff * Self._pow10(len(fracPart)) + varint(fracPart if fracPart else "0")
      expVal -= len(fracPart)
    if expPart:
      expVal += int(varint(expPart))
    zero: varint = 0
    self._sign = signNeg and coeff != zero
    self._coeff = coeff
    self._exp = expVal
    self._normalizeCoeff()

  def _normalizeCoeff(self) -> None:
    if self._special:
      return
    zero: varint = 0
    if self._coeff == zero:
      self._sign = False
      self._exp = 0
      return
    ten: varint = 10
    while self._coeff % ten == zero:
      self._coeff //= ten
      self._exp += 1

  @staticmethod
  @immutable
  def _fromFinite(sign: bool, coeff: varint, exp: int) -> Self:
    """由符号/系数/指数直接构造（避免字符串往返）。"""
    zero: varint = 0
    out: Self = new()
    out._sign = sign and coeff != zero
    out._coeff = coeff
    out._exp = exp
    out._normalizeCoeff()
    return out

  @property
  def isNegative(self) -> bool:
    return self._sign

  @property
  def coefficient(self) -> varint:
    return self._coeff

  @property
  def exponent(self) -> int:
    return self._exp

  @staticmethod
  @immutable
  def _formatFinite(sign: bool, coeff: varint, exp: int) -> str:
    zero: varint = 0
    if coeff == zero:
      return "0"
    c = str(coeff)
    if exp == 0:
      if sign:
        return "-" + c
      return c
    if exp > 0:
      pad: str = c + "0" * exp
      if sign:
        return "-" + pad
      return pad
    e: int = exp
    pos: int = len(c) + e
    if pos <= 0:
      frac: str = "0." + ("0" * (-pos)) + c
      if sign:
        return "-" + frac
      return frac
    if pos >= len(c):
      frac2: str = c + ("0" * (pos - len(c)))
      if sign:
        return "-" + frac2
      return frac2
    whole: str = c[:pos]
    frac3: str = c[pos:]
    text: str = whole + "." + frac3
    if sign:
      return "-" + text
    return text

  @staticmethod
  @immutable
  def _makeSpecial(sign: bool, kind: int) -> Self:
    if kind == 1:
      return new("NaN")
    if sign:
      return new("-Infinity")
    return new("Infinity")

  @staticproperty
  @immutable
  def NaN() -> Self:
    return new("NaN")

  @staticproperty
  @immutable
  def Infinity() -> Self:
    return new("Infinity")

  @immutable
  def isNan(self) -> bool:
    return self._special == 1

  @immutable
  def isInfinite(self) -> bool:
    return self._special == 2

  @immutable
  def isFinite(self) -> bool:
    return self._special == 0

  @immutable
  def asTuple(self) -> (int, int, int):
    return ((1 if self._sign else 0), int(self._coeff), self._exp)

  @staticmethod
  @immutable
  def _gcdVarint(a: varint, b: varint) -> varint:
    x: varint = a
    y: varint = b
    zero: varint = 0
    while y != zero:
      t: varint = y
      y = x % y
      x = t
    return x

  @immutable
  def asIntegerRatio(self) -> (varint, varint):
    if self._special:
      raise OverflowError("cannot convert NaN or Infinity to integer ratio")
    zero: varint = 0
    one: varint = 1
    if self._coeff == zero:
      return (zero, one)
    num: varint = self._coeff
    den: varint = one
    if self._exp >= 0:
      num *= Self._pow10(self._exp)
    else:
      den *= Self._pow10(-self._exp)
    if self._sign:
      num = -num
    g: varint = Self._gcdVarint(abs(num), den)
    num //= g
    den //= g
    return (num, den)

  @immutable
  def __bool__(self) -> bool:
    zero: varint = 0
    if self._special:
      return True
    return self._coeff != zero

  @immutable
  def __float__(self) -> float:
    if self._special == 1:
      return float.NaN
    if self._special == 2:
      if self._sign:
        return -float.Inf
      return float.Inf
    return float(self._toSciStr())

  @immutable
  def _toSciStr(self) -> str:
    if self._special == 1:
      return "nan"
    if self._special == 2:
      if self._sign:
        return "-inf"
      return "inf"
    c = str(self._coeff)
    if self._exp == 0:
      if self._sign:
        return "-" + c
      return c
    if self._exp > 0:
      pad: str = c + "0" * self._exp
      if self._sign:
        return "-" + pad
      return pad
    e: int = self._exp
    pos: int = len(c) + e
    if pos <= 0:
      frac: str = "0." + ("0" * (-pos)) + c
      if self._sign:
        return "-" + frac
      return frac
    if pos >= len(c):
      frac2: str = c + ("0" * (pos - len(c)))
      if self._sign:
        return "-" + frac2
      return frac2
    whole: str = c[:pos]
    frac3: str = c[pos:]
    out: str = whole + "." + frac3
    if self._sign:
      return "-" + out
    return out

  @immutable
  def __cmp__(self, other: Self) -> int:
    if self.isNan() or other.isNan():
      raise InvalidOperationError("comparison involving NaN")
    if self.isInfinite() and other.isInfinite():
      if self.isNegative == other.isNegative:
        return 0
      if self.isNegative:
        return -1
      return 1
    if self.isInfinite():
      if self.isNegative:
        return -1
      return 1
    if other.isInfinite():
      if other.isNegative:
        return 1
      return -1
    ac: varint
    bc: varint
    c: int = 0
    if self._exp < other.exponent:
      scale: int = other.exponent - self._exp
      ac = self._coeff * Self._pow10(scale)
      bc = other.coefficient
    elif self._exp > other.exponent:
      scale2: int = self._exp - other.exponent
      ac = self._coeff * Self._pow10(scale2)
      bc = other.coefficient
    else:
      ac = self._coeff
      bc = other.coefficient
    if ac < bc:
      c = -1
    elif ac > bc:
      c = 1
    if self._sign and other.isNegative:
      return -c
    if self._sign:
      return -1 if c > 0 else (1 if c < 0 else 0)
    if other.isNegative:
      return 1 if c > 0 else (-1 if c < 0 else 0)
    return c

  @immutable
  def _alignExp(self, other: Self) -> (varint, varint, int):
    ac: varint
    bc: varint
    exp: int
    if self._exp <= other.exponent:
      shift: int = other.exponent - self._exp
      ac = self._coeff * Self._pow10(shift)
      bc = other.coefficient
      exp = other.exponent
    else:
      shift2: int = self._exp - other.exponent
      ac = self._coeff * Self._pow10(shift2)
      bc = other.coefficient
      exp = self._exp
    return (ac, bc, exp)

  @immutable
  def __add__(self, other: Self) -> Self:
    if not self.isFinite() or not other.isFinite():
      if self.isNan() or other.isNan():
        return new.NaN
      if self.isInfinite() and other.isInfinite():
        if self.isNegative != other.isNegative:
          return new.NaN
        return new._makeSpecial(self.isNegative, 2)
      if self.isInfinite():
        return new._makeSpecial(self.isNegative, 2)
      if other.isNegative:
        return new("-Infinity")
      return new("Infinity")
    ac: varint
    bc: varint
    exp: int
    ac, bc, exp = self._alignExp(other)
    if self.isNegative == other.isNegative:
      return new._fromFinite(self._sign, ac + bc, exp)
    if ac >= bc:
      return new._fromFinite(self._sign, ac - bc, exp)
    return new._fromFinite(not self._sign, bc - ac, exp)

  @immutable
  def __sub__(self, other: Self) -> Self:
    return self + (-other)

  @immutable
  def __neg__(self) -> Self:
    if self._special:
      if self.isNan():
        return new.NaN
      if self._sign:
        return new("Infinity")
      return new("-Infinity")
    return new._fromFinite(not self._sign, self._coeff, self._exp)

  @immutable
  def __mul__(self, other: Self) -> Self:
    if self.isNan() or other.isNan():
      return new.NaN
    if self.isInfinite() or other.isInfinite():
      zero: varint = 0
      if other.coefficient == zero and not other.isInfinite() and not other.isNan():
        return new.NaN
      if self._coeff == zero and not self.isInfinite() and not self.isNan():
        return new.NaN
      sign: bool = self.isNegative != other.isNegative
      return new._makeSpecial(sign, 2)
    return new._fromFinite(
      self.isNegative != other.isNegative,
      self._coeff * other.coefficient,
      self._exp + other.exponent,
    )

  @immutable
  def __truediv__(self, other: Self) -> Self:
    if self.isNan() or other.isNan():
      return new.NaN
    zero: varint = 0
    if not other.isFinite() and other.coefficient == zero:
      if self._special:
        return new.NaN
      if self._coeff == zero:
        return new.NaN
      return new._makeSpecial(self.isNegative != other.isNegative, 2)
    if self.isInfinite():
      if other.isInfinite():
        return new.NaN
      return new._makeSpecial(self.isNegative != other.isNegative, 2)
    if other.isInfinite():
      return new(0)
    rem: varint = self._coeff % other.coefficient
    if rem != zero:
      scale: varint = 10
      num: varint = self._coeff
      num *= scale
      den: varint = other.coefficient
      extra: int = 1
      while num % den and extra < 28:
        num *= scale
        extra += 1
      coeffQ: varint = num // den
      expQ: int = self._exp - other.exponent - extra
      return new._fromFinite(self.isNegative != other.isNegative, coeffQ, expQ)
    return new._fromFinite(
      self.isNegative != other.isNegative,
      self._coeff // other.coefficient,
      self._exp - other.exponent,
    )

  @immutable
  def normalize(self) -> Self:
    if self._special:
      return new(self)
    return new._fromFinite(self._sign, self._coeff, self._exp)

  @immutable
  def quantize(self, exp: Self, context: Context | None = None) -> Self:
    if self._special:
      return new(self)
    targetExp: int = exp.exponent
    if self._exp > targetExp:
      pad: int = self._exp - targetExp
      return new._fromFinite(self._sign, self._coeff * Self._pow10(pad), targetExp)
    shift: int = targetExp - self._exp
    div: varint = Self._pow10(shift)
    q: varint = self._coeff // div
    r: varint = self._coeff % div
    two: varint = 2
    one: varint = 1
    half: varint = div // two
    if r > half or (r == half and q % two == one):
      q += one
    return new._fromFinite(self._sign, q, targetExp)

  @immutable
  def __str__(self) -> str:
    return self._toSciStr()

  @immutable
  def __repr__(self) -> str:
    return "Decimal('" + self._toSciStr() + "')"
