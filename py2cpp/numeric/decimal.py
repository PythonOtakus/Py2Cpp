"""十进制定点 ``Decimal``（对齐 CPython 3.13 ``decimal.Decimal`` P0 子集）。

模块级 ``Context``（``prec=28``、``RoundingMode.ROUND_HALF_EVEN``）、``getcontext``/``setcontext``、
字符串构造、四则比较、``quantize``/``normalize``、``NaN``/``Infinity``。
"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import InvalidOperation, OverflowError, ValueError
from .varint import varint


@enum
class RoundingMode:
  """``decimal`` 舍入模式（对齐 CPython ``decimal`` 模块常量）。"""

  ROUND_DOWN = 0
  ROUND_HALF_UP = 1
  ROUND_HALF_EVEN = 2
  ROUND_CEILING = 3
  ROUND_FLOOR = 4
  ROUND_UP = 5
  ROUND_HALF_DOWN = 6
  ROUND_05UP = 7


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


_default_context: Context = new()


@immutable
def getcontext() -> Context:
  return _default_context


def setcontext(ctx: Context) -> None:
  _default_context.prec = ctx.prec
  _default_context.rounding = ctx.rounding
  _default_context.Emin = ctx.Emin
  _default_context.Emax = ctx.Emax
  _default_context.traps = ctx.traps
  _default_context.flags = ctx.flags


@copyable
@native_name("PyDecimal")
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
    self._init_from_str(text)

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
    self._normalize_coeff()

  def __copy__(self, other: Self):
    self._special = other._special
    self._sign = other._sign
    self._coeff = other._coeff
    self._exp = other._exp

  @staticmethod
  @immutable
  def _parse_digits_only(s: str) -> str:
    out: str = ""
    for i in range(len(s)):
      c: int = s[i]
      if c != ord("_"):
        out += chr(c)
    return out

  def _init_from_str(self, text: str) -> None:
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
    sign_neg: bool = False
    start: int = 0
    c0: int = t[0]
    if c0 == ord("-"):
      sign_neg = True
      start = 1
    elif c0 == ord("+"):
      start = 1
    body: str = Self._parse_digits_only(t[start:])
    if not body:
      raise ValueError("Invalid literal for Decimal: " + repr(text))
    dot: int = body.find(".")
    exp_pos: int = body.find("e")
    exp_pos2: int = body.find("E")
    if exp_pos2 >= 0:
      if exp_pos < 0 or exp_pos2 < exp_pos:
        exp_pos = exp_pos2
    int_part: str = ""
    frac_part: str = ""
    exp_part: str = ""
    if dot >= 0:
      int_part = body[:dot]
      rest: str = body[dot + 1 :]
      if exp_pos >= 0:
        frac_part = rest[: exp_pos - dot - 1]
        exp_part = rest[exp_pos - dot :]
      else:
        frac_part = rest
    elif exp_pos >= 0:
      int_part = body[:exp_pos]
      exp_part = body[exp_pos + 1 :]
    else:
      int_part = body
    coeff: varint = varint(int_part if int_part else "0")
    exp_val: int = 0
    if frac_part:
      coeff = coeff * Self._pow10(len(frac_part)) + varint(frac_part if frac_part else "0")
      exp_val -= len(frac_part)
    if exp_part:
      exp_val += int(varint(exp_part))
    zero: varint = 0
    self._sign = sign_neg and coeff != zero
    self._coeff = coeff
    self._exp = exp_val
    self._normalize_coeff()

  def _normalize_coeff(self) -> None:
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
  def _from_finite(sign: bool, coeff: varint, exp: int) -> Self:
    """由符号/系数/指数直接构造（避免字符串往返）。"""
    zero: varint = 0
    out: Self = new()
    out._sign = sign and coeff != zero
    out._coeff = coeff
    out._exp = exp
    out._normalize_coeff()
    return out

  @property
  def is_negative(self) -> bool:
    return self._sign

  @property
  def coefficient(self) -> varint:
    return self._coeff

  @property
  def exponent(self) -> int:
    return self._exp

  @staticmethod
  @immutable
  def _format_finite(sign: bool, coeff: varint, exp: int) -> str:
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
  def _make_special(sign: bool, kind: int) -> Self:
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
  def is_nan(self) -> bool:
    return self._special == 1

  @immutable
  def is_infinite(self) -> bool:
    return self._special == 2

  @immutable
  def is_finite(self) -> bool:
    return self._special == 0

  @immutable
  def as_tuple(self) -> (int, int, int):
    return ((1 if self._sign else 0), int(self._coeff), self._exp)

  @staticmethod
  @immutable
  def _gcd_varint(a: varint, b: varint) -> varint:
    x: varint = a
    y: varint = b
    zero: varint = 0
    while y != zero:
      t: varint = y
      y = x % y
      x = t
    return x

  @immutable
  def as_integer_ratio(self) -> (varint, varint):
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
    g: varint = Self._gcd_varint(abs(num), den)
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
    return float(self._to_sci_str())

  @immutable
  def _to_sci_str(self) -> str:
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
    if self.is_nan() or other.is_nan():
      raise InvalidOperation("comparison involving NaN")
    if self.is_infinite() and other.is_infinite():
      if self.is_negative == other.is_negative:
        return 0
      if self.is_negative:
        return -1
      return 1
    if self.is_infinite():
      if self.is_negative:
        return -1
      return 1
    if other.is_infinite():
      if other.is_negative:
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
    if self._sign and other.is_negative:
      return -c
    if self._sign:
      return -1 if c > 0 else (1 if c < 0 else 0)
    if other.is_negative:
      return 1 if c > 0 else (-1 if c < 0 else 0)
    return c

  @immutable
  def _align_exp(self, other: Self) -> (varint, varint, int):
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
    if not self.is_finite() or not other.is_finite():
      if self.is_nan() or other.is_nan():
        return new.NaN
      if self.is_infinite() and other.is_infinite():
        if self.is_negative != other.is_negative:
          return new.NaN
        return new._make_special(self.is_negative, 2)
      if self.is_infinite():
        return new._make_special(self.is_negative, 2)
      if other.is_negative:
        return new("-Infinity")
      return new("Infinity")
    ac: varint
    bc: varint
    exp: int
    ac, bc, exp = self._align_exp(other)
    if self.is_negative == other.is_negative:
      return new._from_finite(self._sign, ac + bc, exp)
    if ac >= bc:
      return new._from_finite(self._sign, ac - bc, exp)
    return new._from_finite(not self._sign, bc - ac, exp)

  @immutable
  def __sub__(self, other: Self) -> Self:
    return self + (-other)

  @immutable
  def __neg__(self) -> Self:
    if self._special:
      if self.is_nan():
        return new.NaN
      if self._sign:
        return new("Infinity")
      return new("-Infinity")
    return new._from_finite(not self._sign, self._coeff, self._exp)

  @immutable
  def __mul__(self, other: Self) -> Self:
    if self.is_nan() or other.is_nan():
      return new.NaN
    if self.is_infinite() or other.is_infinite():
      zero: varint = 0
      if other.coefficient == zero and not other.is_infinite() and not other.is_nan():
        return new.NaN
      if self._coeff == zero and not self.is_infinite() and not self.is_nan():
        return new.NaN
      sign: bool = self.is_negative != other.is_negative
      return new._make_special(sign, 2)
    return new._from_finite(
      self.is_negative != other.is_negative,
      self._coeff * other.coefficient,
      self._exp + other.exponent,
    )

  @immutable
  def __truediv__(self, other: Self) -> Self:
    if self.is_nan() or other.is_nan():
      return new.NaN
    zero: varint = 0
    if not other.is_finite() and other.coefficient == zero:
      if self._special:
        return new.NaN
      if self._coeff == zero:
        return new.NaN
      return new._make_special(self.is_negative != other.is_negative, 2)
    if self.is_infinite():
      if other.is_infinite():
        return new.NaN
      return new._make_special(self.is_negative != other.is_negative, 2)
    if other.is_infinite():
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
      coeff_q: varint = num // den
      exp_q: int = self._exp - other.exponent - extra
      return new._from_finite(self.is_negative != other.is_negative, coeff_q, exp_q)
    return new._from_finite(
      self.is_negative != other.is_negative,
      self._coeff // other.coefficient,
      self._exp - other.exponent,
    )

  @immutable
  def normalize(self) -> Self:
    if self._special:
      return new(self)
    return new._from_finite(self._sign, self._coeff, self._exp)

  @immutable
  def quantize(self, exp: Self, context: Context | None = None) -> Self:
    if self._special:
      return new(self)
    target_exp: int = exp.exponent
    if self._exp > target_exp:
      pad: int = self._exp - target_exp
      return new._from_finite(self._sign, self._coeff * Self._pow10(pad), target_exp)
    shift: int = target_exp - self._exp
    div: varint = Self._pow10(shift)
    q: varint = self._coeff // div
    r: varint = self._coeff % div
    two: varint = 2
    one: varint = 1
    half: varint = div // two
    if r > half or (r == half and q % two == one):
      q += one
    return new._from_finite(self._sign, q, target_exp)

  @immutable
  def __str__(self) -> str:
    return self._to_sci_str()

  @immutable
  def __repr__(self) -> str:
    return "Decimal('" + self._to_sci_str() + "')"
