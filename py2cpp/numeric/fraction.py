"""有理数 ``Fraction[T: Integral]``（对齐 CPython 3.13 ``fractions.Fraction`` 核心语义）。

``T`` 为 ``int`` 或 ``varint``；字符串解析、``float`` / ``Decimal`` 构造重载（浮点经 ``float.as_integer_ratio``）。
"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import OverflowError, TypeError, ValueError, ZeroDivisionError
from .decimal import Decimal
from .protocols import Integral
from .ratio import float_as_integer_ratio
from .varint import varint


@copyable
@native_name("PyFraction")
class Fraction[T: Integral]:
  """约分存储的有理数；分母恒正，符号在分子。"""

  _HASH_MODULUS: int64 @const = 2305843009213693951
  _HASH_INF: int @const = 314159

  _num: T
  _den: T

  @overload
  def __init__(self, text: str):
    parsed: (T, T) = Self._parse_str(text)
    self._num = parsed[0]
    self._den = parsed[1]
    self._normalize_inplace()

  @overload
  def __init__(self, f: float64):
    ratio: (varint, varint) = float_as_integer_ratio(f)
    self._num = Self._to_T(ratio[0])
    self._den = Self._to_T(ratio[1])

  @overload
  def __init__(self, dec: Decimal):
    if dec.is_nan() or dec.is_infinite():
      raise OverflowError("cannot convert NaN or Infinity to Fraction")
    r: (varint, varint) = dec.as_integer_ratio()
    self._num = Self._to_T(r[0])
    self._den = Self._to_T(r[1])

  @staticmethod
  @immutable
  def _t_zero() -> T:
    z: int = 0
    out: T = z
    return out

  @staticmethod
  @immutable
  def _t_one() -> T:
    o: int = 1
    out: T = o
    return out

  @staticmethod
  @immutable
  def _abs(v: T) -> T:
    zero: T = Self._t_zero()
    if v < zero:
      return -v
    return v

  @overload
  def __init__(self, numerator: Self, denominator: Self):
    n: T = numerator._num * denominator._den
    d: T = denominator._num * numerator._den
    self._num = n
    self._den = d
    self._normalize_inplace()

  @overload
  def __init__(self, numerator: T, denominator: T):
    self._num = numerator
    self._den = denominator
    self._normalize_inplace()

  @overload
  def __init__(self, numerator: T):
    one: T = Self._t_one()
    self._num = numerator
    self._den = one
    self._normalize_inplace()

  @overload
  def __init__(self):
    self._num = Self._t_zero()
    self._den = Self._t_one()
    self._normalize_inplace()

  def __copy__(self, other: Self):
    self._num = other._num
    self._den = other._den

  @staticmethod
  @immutable
  def _to_T(v: varint) -> T:
    if not v:
      z: int = 0
      out: T = z
      return out
    return int(str(v))

  @staticmethod
  @immutable
  def _gcd(a: T, b: T) -> T:
    x: T = Self._abs(a)
    y: T = Self._abs(b)
    zero: T = Self._t_zero()
    while y != zero:
      t: T = y
      y = x % y
      x = t
    return x

  @staticmethod
  @immutable
  def _floordiv(a: T, b: T) -> T:
    return a // b

  def _normalize_inplace(self) -> None:
    zero: T = Self._t_zero()
    if self._den == zero:
      raise ZeroDivisionError("Fraction(" + str(self._num) + ", 0)")
    g: T = Self._gcd(self._num, self._den)
    if self._den < zero:
      g = -g
    self._num = Self._floordiv(self._num, g)
    self._den = Self._floordiv(self._den, g)

  @staticmethod
  @immutable
  def _parse_digits(s: str) -> str:
    out: str = ""
    for i in range(len(s)):
      c: int = s[i]
      if c != ord("_"):
        out += chr(c)
    return out

  @staticmethod
  @immutable
  def _parse_int_part(s: str) -> varint:
    if not s:
      return varint("0")
    return varint(s)

  @staticmethod
  @immutable
  def _parse_str(text: str) -> (T, T):
    t: str = text.strip()
    if not t:
      raise ValueError("Invalid literal for Fraction: " + repr(text))
    sign_neg: bool = False
    start: int = 0
    c0: int = t[0]
    if c0 == ord("-"):
      sign_neg = True
      start = 1
    elif c0 == ord("+"):
      start = 1
    body: str = t[start:]
    if not body:
      raise ValueError("Invalid literal for Fraction: " + repr(text))
    slash: int = body.find("/")
    if slash >= 0:
      left: str = Self._parse_digits(body[:slash].strip())
      right: str = Self._parse_digits(body[slash + 1 :].strip())
      if not right:
        raise ValueError("Invalid literal for Fraction: " + repr(text))
      num_v: varint = Self._parse_int_part(left)
      den_v: varint = Self._parse_int_part(right)
      if sign_neg:
        num_v = -num_v
      return (Self._to_T(num_v), Self._to_T(den_v))
    num_v: varint = Self._parse_int_part("")
    den_v: varint = varint("1")
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
      int_part = Self._parse_digits(body[:dot])
      rest: str = body[dot + 1 :]
      if exp_pos >= 0:
        frac_part = Self._parse_digits(rest[: exp_pos - dot - 1])
        exp_part = Self._parse_digits(rest[exp_pos - dot :])
      else:
        frac_part = Self._parse_digits(rest)
    elif exp_pos >= 0:
      int_part = Self._parse_digits(body[:exp_pos])
      exp_part = Self._parse_digits(body[exp_pos + 1 :])
    else:
      int_part = Self._parse_digits(body)
    num_v = Self._parse_int_part(int_part)
    if frac_part:
      scale: varint = new.pow10(len(frac_part))
      frac_v: varint = Self._parse_int_part(frac_part)
      num_v = num_v * scale + frac_v
      den_v = scale
    if exp_part:
      exp_v: varint = Self._parse_int_part(exp_part)
      if int(exp_v) >= 0:
        num_v *= varint.pow10(int(exp_v))
      else:
        den_v *= varint.pow10(-int(exp_v))
    if sign_neg:
      num_v = -num_v
    return (Self._to_T(num_v), Self._to_T(den_v))

  @property
  def numerator(self) -> T:
    return self._num

  @property
  def denominator(self) -> T:
    return self._den

  @immutable
  def is_integer(self) -> bool:
    one: T = Self._t_one()
    return self._den == one

  @immutable
  def as_integer_ratio(self) -> (T, T):
    return (self._num, self._den)

  @immutable
  def limit_denominator(self, max_denominator: int = 1000000) -> Self:
    if max_denominator < 1:
      raise ValueError("max_denominator should be at least 1")
    if int(self._den) <= max_denominator:
      return new(self._num, self._den)
    p0: int = 0
    q0: int = 1
    p1: int = 1
    q1: int = 0
    n: T = self._num
    d: T = self._den
    while True:
      a: T = Self._floordiv(n, d)
      q2: int = q0 + int(a) * q1
      if q2 > max_denominator:
        break
      p0, q0, p1, q1 = p1, q1, p0 + int(a) * p1, q2
      if q0 < 0:
        q0 = q0
      nr: T = d
      dr: T = n - a * d
      n = nr
      d = dr
    k: int = (max_denominator - q0) // q1
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
    zero: T = Self._t_zero()
    return self._num != zero

  @immutable
  def __neg__(self) -> Self:
    return new(-self._num, self._den)

  @immutable
  def __pos__(self) -> Self:
    return new(self._num, self._den)

  @immutable
  def __abs__(self) -> Self:
    n: T = self._num
    zero: T = Self._t_zero()
    if n < zero:
      n = -n
    return new(n, self._den)

  @immutable
  def __cmp__(self, other: Self) -> int:
    left: T = self._num * other._den
    right: T = other._num * self._den
    if left < right:
      return -1
    if left > right:
      return 1
    return 0

  @overload
  @immutable
  def __add__(self, other: Self) -> Self:
    na: T = self._num
    da: T = self._den
    nb: T = other._num
    db: T = other._den
    g: T = Self._gcd(da, db)
    one: T = Self._t_one()
    if g == one:
      return new(na * db + da * nb, da * db)
    s: T = Self._floordiv(da, g)
    t: T = na * Self._floordiv(db, g) + nb * s
    g2: T = Self._gcd(t, g)
    if g2 == one:
      return new(t, s * db)
    return new(Self._floordiv(t, g2), s * Self._floordiv(db, g2))

  @overload
  @immutable
  def __add__(self, other: T) -> Self:
    return self + Self(other)

  @overload
  @immutable
  def __add__(self, other: float64) -> float64:
    return float(self) + other

  @overload
  @immutable
  def __sub__(self, other: Self) -> Self:
    na: T = self._num
    da: T = self._den
    nb: T = other._num
    db: T = other._den
    g: T = Self._gcd(da, db)
    one: T = Self._t_one()
    if g == one:
      return new(na * db - da * nb, da * db)
    s: T = Self._floordiv(da, g)
    t: T = na * Self._floordiv(db, g) - nb * s
    g2: T = Self._gcd(t, g)
    if g2 == one:
      return new(t, s * db)
    return new(Self._floordiv(t, g2), s * Self._floordiv(db, g2))

  @overload
  @immutable
  def __sub__(self, other: T) -> Self:
    return self - Self(other)

  @overload
  @immutable
  def __sub__(self, other: float64) -> float64:
    return float(self) - other

  @overload
  @immutable
  def __mul__(self, other: Self) -> Self:
    na: T = self._num
    da: T = self._den
    nb: T = other._num
    db: T = other._den
    g1: T = Self._gcd(na, db)
    g2: T = Self._gcd(nb, da)
    one: T = Self._t_one()
    if g1 == one and g2 == one:
      return new(na * nb, da * db)
    return new(
      Self._floordiv(na, g1) * Self._floordiv(nb, g2),
      Self._floordiv(da, g2) * Self._floordiv(db, g1),
    )

  @overload
  @immutable
  def __mul__(self, other: T) -> Self:
    return self * Self(other)

  @overload
  @immutable
  def __mul__(self, other: float64) -> float64:
    return float(self) * other

  @overload
  @immutable
  def __truediv__(self, other: Self) -> Self:
    zero: T = Self._t_zero()
    if other._num == zero:
      raise ZeroDivisionError("division by zero")
    return self * Self(other._den, other._num)

  @overload
  @immutable
  def __truediv__(self, other: T) -> Self:
    return self / Self(other)

  @overload
  @immutable
  def __truediv__(self, other: float64) -> float64:
    return float(self) / other

  @immutable
  def __str__(self) -> str:
    one: T = Self._t_one()
    if self._den == one:
      return str(self._num)
    return str(self._num) + "/" + str(self._den)

  @immutable
  def __repr__(self) -> str:
    return "Fraction(" + str(self._num) + ", " + str(self._den) + ")"

  @immutable
  def __hash__(self) -> int:
    one: T = Self._t_one()
    if self._den == one:
      return hash(self._num)
    try:
      dinv: T = pow(self._den, -1, Self._HASH_MODULUS)
    except ValueError:
      return Self._HASH_INF
    an: T = Self._abs(self._num)
    prod: int = hash(int(an)) * int(dinv)
    h: int = hash(prod)
    if self._num < 0:
      h = -h
    if h == -1:
      return -2
    return h
