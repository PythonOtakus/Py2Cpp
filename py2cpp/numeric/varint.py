"""任意精度整数 ``varint``（CPython 3.13 ``int`` 语义，30 位 limb）。"""
from ..builtins import *
from py2cpp import native_name, Self, const, copyable, immutable, int64, overload, property
from py2cpp.core.exceptions import ValueError


@copyable
@native_name("PyVarInt")
class varint:
  """注解 ``varint``、``from py2cpp import varint``；字面量 ``100`` 等由译器生成十进制字符串构造。"""

  _VARINT_SHIFT: int @const = 30
  _VARINT_BASE: int @const = 1073741824
  _HASH_BITS: int @const = 61
  _HASH_MODULUS: int64 @const = 2305843009213693951

  _hash: int = 0
  _hash_ok: bool = False

  def __init__(self, value: str = ""):
    self._neg: bool = False
    self._digits: list[int] = []
    self._hash = 0
    self._hash_ok = False
    self._parse_decimal(value)

  def __copy__(self, other: Self):
    self._neg = other._neg
    self._digits.__copy__(other._digits)
    self._hash = other._hash
    self._hash_ok = other._hash_ok

  def __move__(self, other: Self):
    self._neg = other._neg
    self._digits = other._digits
    self._hash = other._hash
    self._hash_ok = other._hash_ok
    other._neg = False
    digits: list[int] = []
    other._digits = digits
    other._hash = 0
    other._hash_ok = False

  @staticmethod
  @immutable
  def _zero() -> Self:
    return new()

  @staticmethod
  @immutable
  def _one() -> Self:
    limb: list[int] = [1]
    return new._from_abs_digits(False, limb)

  @staticmethod
  @immutable
  def _from_abs_digits(neg: bool, digits: list[int]) -> Self:
    out: Self = new()
    out._digits = digits
    out._normalize()
    if neg and out:
      return -out
    return out

  @staticmethod
  @immutable
  def _add_limbs(a: list[int], b: list[int]) -> list[int]:
    va: Self = new()
    va._digits = a
    vb: Self = new()
    vb._digits = b
    na: int = va._top_index()
    nb: int = vb._top_index()
    n: int = na
    if nb > n:
      n = nb
    out: list[int] = []
    carry: int = 0
    for i in range(n):
      s: int = va._digit_at(i) + vb._digit_at(i) + carry
      carry = 0
      if s >= Self._VARINT_BASE:
        s -= Self._VARINT_BASE
        carry = 1
      out.append(s)
    if carry:
      out.append(carry)
    return out

  @staticmethod
  @immutable
  def _digits_from_int(n: int) -> list[int]:
    if n == 0:
      zero: list[int] = []
      return zero
    v: int = n
    if v < 0:
      v = -v
    out: list[int] = []
    while v:
      out.append(v % Self._VARINT_BASE)
      v //= Self._VARINT_BASE
    return out

  @staticmethod
  @immutable
  def _mul_10_limbs(digits: list[int]) -> list[int]:
    d2: list[int] = Self._add_limbs(digits, digits)
    d4: list[int] = Self._add_limbs(d2, d2)
    d8: list[int] = Self._add_limbs(d4, d4)
    return Self._add_limbs(d8, d2)

  @immutable
  def _top_index(self) -> int:
    n: int = len(self._digits)
    while n > 0 and self._digit_at(n - 1) == 0:
      n -= 1
    return n

  def _normalize(self) -> None:
    n: int = self._top_index()
    for _ in range(len(self._digits) - n):
      self._digits.pop()
    if not n:
      self._neg = False

  @immutable
  def _digit_at(self, i: int) -> int:
    if i < 0 or i >= len(self._digits):
      return 0
    return self._digits[i]

  @immutable
  def _cmp_abs(self, other: Self) -> int:
    na: int = self._top_index()
    nb: int = other._top_index()
    if na < nb:
      return -1
    if na > nb:
      return 1
    for i in range(na - 1, -1, -1):
      da: int = self._digit_at(i)
      db: int = other._digit_at(i)
      if da < db:
        return -1
      if da > db:
        return 1
    return 0

  @immutable
  def _divmod_10_limbs(self) -> (list[int], int):
    """绝对值 limb 向量除以 10，返回 (商, 余数 0–9)。"""
    n: int = self._top_index()
    if not n:
      zero_limbs: list[int] = []
      return (zero_limbs, 0)
    work: list[int] = []
    for i in range(n):
      work.append(self._digit_at(i))
    carry: int = 0
    base64: int64 = Self._VARINT_BASE
    for j in range(n - 1, -1, -1):
      temp: int64 = work[j] + int64(carry) * base64
      work[j] = temp // 10
      carry = temp % 10
    w: Self = new()
    w._digits = work
    m: int = w._top_index()
    for _ in range(len(work) - m):
      work.pop()
    return (work, carry)

  def _parse_decimal(self, text: str) -> None:
    self._neg = False
    self._digits = []
    if not text:
      return
    t: str = text.strip()
    if not t:
      return
    start: int = 0
    if t[0] == ord("-"):
      self._neg = True
      start = 1
    elif t[0] == ord("+"):
      start = 1
    mag: Self = new._zero()
    ten: Self = new._from_abs_digits(False, Self._digits_from_int(10))
    for i in range(start, len(t)):
      d: int = int(t[i]) - ord("0")
      inc: Self = new._from_abs_digits(False, Self._digits_from_int(d))
      mag = mag * ten + inc
    self._digits = mag._digits
    self._normalize()

  @immutable
  def _to_decimal_str(self) -> str:
    if not self:
      return "0"
    src: Self = abs(self)
    v: list[int] = []
    for i in range(len(src._digits)):
      v.append(src._digit_at(i))
    out: list[int] = []
    work: Self = new()
    work._digits = v
    while work._top_index() > 0:
      step: (list[int], int) = work._divmod_10_limbs()
      work._digits = step[0]
      out.append(step[1])
    s: str = ""
    if self._neg:
      s = "-"
    for j in range(len(out) - 1, -1, -1):
      s += str(out[j])
    if not s:
      return "0"
    return s

  @immutable
  def _add_abs(self, other: Self) -> Self:
    na: int = self._top_index()
    nb: int = other._top_index()
    n: int = na
    if nb > n:
      n = nb
    digits: list[int] = []
    carry: int = 0
    for i in range(n):
      s: int = self._digit_at(i) + other._digit_at(i) + carry
      carry = 0
      if s >= Self._VARINT_BASE:
        s -= Self._VARINT_BASE
        carry = 1
      digits.append(s)
    if carry:
      digits.append(carry)
    return new._from_abs_digits(False, digits)

  @immutable
  def _sub_abs(self, other: Self) -> Self:
    na: int = self._top_index()
    digits: list[int] = []
    borrow: int = 0
    for i in range(na):
      av: int = self._digit_at(i) - borrow
      bv: int = other._digit_at(i)
      borrow = 0
      diff: int = av - bv
      if diff < 0:
        diff += Self._VARINT_BASE
        borrow = 1
      digits.append(diff)
    return new._from_abs_digits(False, digits)

  @immutable
  def _mul_abs(self, other: Self) -> Self:
    na: int = self._top_index()
    nb: int = other._top_index()
    if not na or not nb:
      return new._zero()
    prod: list[int] = []
    for k in range(na + nb):
      prod.append(0)
    for i in range(na):
      carry: int64 = 0
      ai: int = self._digit_at(i)
      for j in range(nb):
        t: int64 = prod[i + j] + int64(ai) * other._digit_at(j) + carry
        carry = t // Self._VARINT_BASE
        prod[i + j] = t % Self._VARINT_BASE
      k: int = i + nb
      while carry:
        if k >= len(prod):
          prod.append(0)
        t2: int64 = prod[k] + carry
        carry = t2 // Self._VARINT_BASE
        prod[k] = t2 % Self._VARINT_BASE
        k += 1
    return new._from_abs_digits(False, prod)

  @immutable
  def _divmod_abs(self, other: Self) -> (Self, Self):
    zero: Self = new._zero()
    if not other:
      return (zero, zero)
    if self._cmp_abs(other) < 0:
      return (zero, self)
    one: Self = new._one()
    cur: Self = one
    denom: Self = other
    acc_q: Self = new._zero()
    rem: Self = self
    while denom._cmp_abs(rem) <= 0:
      cur <<= one
      denom <<= one
    cur >>= one
    denom >>= one
    while cur:
      if rem._cmp_abs(denom) >= 0:
        rem = rem._sub_abs(denom)
        acc_q = acc_q._add_abs(cur)
      cur >>= one
      denom >>= one
    return (acc_q, rem)

  @immutable
  def _shl_abs(self, nbits: int) -> Self:
    if nbits <= 0 or not self:
      return self
    digit_shift: int = nbits // Self._VARINT_SHIFT
    bit_shift: int = nbits % Self._VARINT_SHIFT
    na: int = self._top_index()
    digits: list[int] = []
    for k in range(digit_shift):
      digits.append(0)
    carry: int = 0
    for i in range(na):
      v: int = (self._digit_at(i) << bit_shift) | carry
      carry = v >> Self._VARINT_SHIFT
      digits.append(v & (Self._VARINT_BASE - 1))
    if carry:
      digits.append(carry)
    return new._from_abs_digits(False, digits)

  @immutable
  def _shr_abs(self, nbits: int) -> Self:
    if nbits <= 0 or not self:
      return self
    na: int = self._top_index()
    digit_shift: int = nbits // Self._VARINT_SHIFT
    bit_shift: int = nbits % Self._VARINT_SHIFT
    if digit_shift >= na:
      return new._zero()
    digits: list[int] = []
    carry: int = 0
    for j in range(na - 1, digit_shift - 1, -1):
      v: int = self._digit_at(j)
      out: int = v >> bit_shift
      if bit_shift:
        if j > digit_shift:
          low: int = v & ((1 << bit_shift) - 1)
          out |= carry
          carry = low << (Self._VARINT_SHIFT - bit_shift)
        else:
          out |= carry
      digits.append(out)
    rev: list[int] = []
    for k in range(len(digits) - 1, -1, -1):
      rev.append(digits[k])
    return new._from_abs_digits(False, rev)

  @immutable
  def _pow_abs(self, exp: Self) -> Self:
    if exp._neg:
      return new._zero()
    result: Self = new._one()
    b: Self = self
    e: Self = exp
    two: Self = Self._one() + Self._one()
    while e:
      half: Self = e // two
      rem: Self = e % two
      if rem:
        result *= b
      b *= b
      e = half
    return result

  def _mod_inverse(self, mod: Self) -> Self:
    """模 ``mod`` 下的乘法逆元（``self`` 须与 ``mod`` 互素）。"""
    if not mod:
      raise ValueError("pow() 3rd argument cannot be 0")
    abs_self: Self = abs(self)
    a: Self = abs_self % mod
    t: Self = new._zero()
    newt: Self = new._one()
    r: Self = mod
    newr: Self = a
    one: Self = new._one()
    while newr:
      q: Self = r // newr
      tr: Self = newt
      newt = t - q * newt
      t = tr
      rr: Self = newr
      newr = r - q * newr
      r = rr
    if r != one:
      raise ValueError("base is not invertible modulo mod")
    out: Self = t % mod
    if out._neg:
      out += mod
    return out

  def _pow_mod(self, exp: Self, mod: Self) -> Self:
    """``pow(base, exp, mod)`` 语义（含负指数逆元）。"""
    one: Self = new._one()
    if not mod:
      raise ValueError("pow() 3rd argument cannot be 0")
    if mod == one:
      return new._zero()
    base: Self = self % mod
    e: Self = exp
    if not e and not base:
      raise ValueError("pow() 3rd argument not allowed unless all arguments are non-negative")
    if e._neg:
      base = base._mod_inverse(mod)
      e = -e
    if not e:
      return new._one()
    result: Self = new._one()
    b: Self = base
    two: Self = Self._one() + Self._one()
    while e:
      half: Self = e // two
      rem: Self = e % two
      if rem:
        result = (result * b) % mod
      b = (b * b) % mod
      e = half
    return result

  def __bool__(self) -> bool:
    return self._top_index() > 0

  def __neg__(self) -> Self:
    if not self:
      return new._zero()
    out: Self = self
    out._neg = not self._neg
    out._hash_ok = False
    if not out:
      out._neg = False
    return out

  def __pos__(self) -> Self:
    return self

  @immutable
  def __abs__(self) -> Self:
    if not self._neg:
      return self
    out: Self = self
    out._neg = False
    out._hash_ok = False
    return out

  def __invert__(self) -> Self:
    one: Self = new._one()
    return -(self + one)

  def __add__(self, other: Self) -> Self:
    if not self._neg and not other._neg:
      return self._add_abs(other)
    if self._neg and other._neg:
      return -self._add_abs(other)
    c: int = self._cmp_abs(other)
    if not self._neg and other._neg:
      if c >= 0:
        return self._sub_abs(other)
      return -other._sub_abs(self)
    if c >= 0:
      return -self._sub_abs(other)
    return other._sub_abs(self)

  def __sub__(self, other: Self) -> Self:
    return self + (-other)

  def __mul__(self, other: Self) -> Self:
    p: Self = self._mul_abs(other)
    if (self._neg != other._neg) and p:
      return -p
    return p

  def __floordiv__(self, other: Self) -> Self:
    one: Self = new._one()
    parts: (Self, Self) = abs(self)._divmod_abs(abs(other))
    q: Self = parts[0]
    r: Self = parts[1]
    if self._neg != other._neg:
      if r:
        q += one
      q = -q
    return q

  def __mod__(self, other: Self) -> Self:
    q: Self = self // other
    prod: Self = q * other
    return self - prod

  def __truediv__(self, other: Self) -> float:
    return float(str(self)) / float(str(other))

  @overload
  def __pow__(self, other: Self) -> Self:
    return self._pow_abs(other)

  @overload
  def __pow__(self, other: Self, mod: Self) -> Self:
    return self._pow_mod(other, mod)

  def __modmul__(self, other: Self, mod: Self) -> Self:
    return (self * other) % mod

  def __and__(self, other: Self) -> Self:
    na: int = self._top_index()
    nb: int = other._top_index()
    lim: int = na
    if nb < lim:
      lim = nb
    digits: list[int] = []
    for i in range(lim):
      digits.append(self._digit_at(i) & other._digit_at(i))
    return new._from_abs_digits(False, digits)

  def __or__(self, other: Self) -> Self:
    na: int = self._top_index()
    nb: int = other._top_index()
    lim: int = na
    if nb > lim:
      lim = nb
    digits: list[int] = []
    for i in range(lim):
      digits.append(self._digit_at(i) | other._digit_at(i))
    return new._from_abs_digits(False, digits)

  def __xor__(self, other: Self) -> Self:
    na: int = self._top_index()
    nb: int = other._top_index()
    lim: int = na
    if nb > lim:
      lim = nb
    digits: list[int] = []
    for i in range(lim):
      digits.append(self._digit_at(i) ^ other._digit_at(i))
    return new._from_abs_digits(False, digits)

  def __lshift__(self, other: Self) -> Self:
    if int(other) < 0:
      return self >> (-other)
    return self._shl_abs(int(other))

  def __rshift__(self, other: Self) -> Self:
    if int(other) < 0:
      return self << (-other)
    return self._shr_abs(int(other))

  @immutable
  def __cmp__(self, other: Self) -> int:
    if self._neg != other._neg:
      if self._neg:
        return -1
      return 1
    c: int = self._cmp_abs(other)
    if self._neg:
      return -c
    return c

  def cache_hash(self, h: int) -> None:
    """外部已算好哈希时写入缓存（算法须与 ``__hash__`` 一致）。"""
    self._hash = h
    self._hash_ok = True

  @immutable
  def _peek_hash(self) -> int:
    """只读哈希（``const`` 比较用）；已缓存则直接返回，否则现场计算不落盘。"""
    if self._hash_ok:
      return self._hash
    na: int = self._top_index()
    if not na:
      return 0
    if na == 1:
      d: int = self._digit_at(0)
      if self._neg:
        return -2 if d == 1 else -d
      return d
    sign: int64 = -1 if self._neg else 1
    i: int = na - 1
    x: int64 = self._digit_at(i)
    i -= 1
    if Self._HASH_BITS >= Self._VARINT_SHIFT + Self._VARINT_SHIFT and i >= 0:
      x = (x << Self._VARINT_SHIFT) + self._digit_at(i)
      i -= 1
    for i in range(i, -1, -1):
      top: int64 = x >> (Self._HASH_BITS - Self._VARINT_SHIFT)
      x = ((x << Self._VARINT_SHIFT) & Self._HASH_MODULUS) | top
      x += self._digit_at(i)
      if x >= Self._HASH_MODULUS:
        x -= Self._HASH_MODULUS
    x *= sign
    if x == -1:
      return -2
    return int(x)

  def __hash__(self) -> int:
    """对齐 CPython ``long_hash``（惰性缓存），供 ``dict[varint, …]`` 等。"""
    if self._hash_ok:
      return self._hash
    h: int = self._peek_hash()
    self._hash = h
    self._hash_ok = True
    return h

  def __repr__(self) -> str:
    return str(self)

  def __str__(self) -> str:
    return self._to_decimal_str()

  def __format__(self, format_spec: str) -> str:
    if not format_spec:
      return str(self)
    return str(self)

  @immutable
  def __int__(self) -> int:
    na: int = self._top_index()
    if not na:
      return 0
    acc: int = 0
    for i in range(na - 1, -1, -1):
      acc *= Self._VARINT_BASE
      acc += self._digit_at(i)
    if self._neg:
      acc = -acc
    return acc

  def bit_length(self) -> int:
    if not self:
      return 0
    na: int = self._top_index()
    top: int = self._digit_at(na - 1)
    bits: int = (na - 1) * Self._VARINT_SHIFT
    while top:
      bits += 1
      top >>= 1
    return bits

  def bit_count(self) -> int:
    c: int = 0
    na: int = self._top_index()
    for i in range(na):
      v: int = self._digit_at(i)
      while v:
        if v & 1:
          c += 1
        v >>= 1
    return c

  def conjugate(self) -> Self:
    return self

  def is_integer(self) -> bool:
    return True

  def as_integer_ratio(self) -> (Self, Self):
    den: Self = new._one()
    return (self, den)

  @property
  def numerator(self) -> Self:
    return self

  @property
  def denominator(self) -> Self:
    return new._one()

  @property
  def real(self) -> Self:
    return self

  @property
  def imag(self) -> int:
    return 0
