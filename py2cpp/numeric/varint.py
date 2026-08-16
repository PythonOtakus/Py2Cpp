"""任意精度整数 ``varint``（CPython 3.13 ``int`` 语义，30 位 limb）。"""
from ..builtins import *
from py2cpp import native_name, Self, const, copyable, immutable, int64, overload, property
from py2cpp.core.exceptions import ValueError


@copyable
@native_name("PyVarInt")
class varint:
  """注解 ``varint``、``from py2cpp import varint``；字面量 ``100`` 等由译器生成十进制字符串构造。"""

  _VarintShift: int @const = 30
  _VarintBase: int @const = 1073741824
  _HashBits: int @const = 61
  _HashModulus: int64 @const = 2305843009213693951

  _hash: int = 0
  _hashOk: bool = False

  def __init__(self, value: str = ""):
    self._neg: bool = False
    self._digits: list[int] = []
    self._hash = 0
    self._hashOk = False
    self._parseDecimal(value)

  def __copy__(self, other: Self):
    self._neg = other._neg
    self._digits.__copy__(other._digits)
    self._hash = other._hash
    self._hashOk = other._hashOk

  def __move__(self, other: Self):
    self._neg = other._neg
    self._digits = other._digits
    self._hash = other._hash
    self._hashOk = other._hashOk
    other._neg = False
    digits: list[int] = []
    other._digits = digits
    other._hash = 0
    other._hashOk = False

  @staticmethod
  @immutable
  def _zero() -> Self:
    return new()

  @staticmethod
  @immutable
  def _one() -> Self:
    limb: list[int] = [1]
    return new._fromAbsDigits(False, limb)

  @staticmethod
  @immutable
  def _fromAbsDigits(neg: bool, digits: list[int]) -> Self:
    out: Self = new()
    out._digits = digits
    out._normalize()
    if neg and out:
      return -out
    return out

  @staticmethod
  @immutable
  def _addLimbs(a: list[int], b: list[int]) -> list[int]:
    va: Self = new()
    va._digits = a
    vb: Self = new()
    vb._digits = b
    na: int = va._topIndex()
    nb: int = vb._topIndex()
    n: int = na
    if nb > n:
      n = nb
    out: list[int] = []
    carry: int = 0
    for i in range(n):
      s: int = va._digitAt(i) + vb._digitAt(i) + carry
      carry = 0
      if s >= Self._VarintBase:
        s -= Self._VarintBase
        carry = 1
      out.append(s)
    if carry:
      out.append(carry)
    return out

  @staticmethod
  @immutable
  def pow10(n: int) -> Self:
    if n <= 0:
      return new._one()
    result: Self = new._one()
    ten: Self = new._fromAbsDigits(False, Self._digitsFromInt(10))
    for _ in range(n):
      result *= ten
    return result

  @staticmethod
  @immutable
  def _digitsFromInt(n: int) -> list[int]:
    if n == 0:
      zero: list[int] = []
      return zero
    v: int = n
    if v < 0:
      v = -v
    out: list[int] = []
    while v:
      out.append(v % Self._VarintBase)
      v //= Self._VarintBase
    return out

  @staticmethod
  @immutable
  def _mul10Limbs(digits: list[int]) -> list[int]:
    d2: list[int] = Self._addLimbs(digits, digits)
    d4: list[int] = Self._addLimbs(d2, d2)
    d8: list[int] = Self._addLimbs(d4, d4)
    return Self._addLimbs(d8, d2)

  @immutable
  def _topIndex(self) -> int:
    n: int = len(self._digits)
    while n > 0 and self._digitAt(n - 1) == 0:
      n -= 1
    return n

  def _normalize(self) -> None:
    n: int = self._topIndex()
    for _ in range(len(self._digits) - n):
      self._digits.pop()
    if not n:
      self._neg = False

  @immutable
  def _digitAt(self, i: int) -> int:
    if i < 0 or i >= len(self._digits):
      return 0
    return self._digits[i]

  @immutable
  def _cmpAbs(self, other: Self) -> int:
    na: int = self._topIndex()
    nb: int = other._topIndex()
    if na < nb:
      return -1
    if na > nb:
      return 1
    for i in range(na - 1, -1, -1):
      da: int = self._digitAt(i)
      db: int = other._digitAt(i)
      if da < db:
        return -1
      if da > db:
        return 1
    return 0

  @immutable
  def _divmod10Limbs(self) -> (list[int], int):
    """绝对值 limb 向量除以 10，返回 (商, 余数 0–9)。"""
    n: int = self._topIndex()
    if not n:
      zeroLimbs: list[int] = []
      return (zeroLimbs, 0)
    work: list[int] = []
    for i in range(n):
      work.append(self._digitAt(i))
    carry: int = 0
    base64: int64 = Self._VarintBase
    for j in range(n - 1, -1, -1):
      temp: int64 = work[j] + int64(carry) * base64
      work[j] = temp // 10
      carry = temp % 10
    w: Self = new()
    w._digits = work
    m: int = w._topIndex()
    for _ in range(len(work) - m):
      work.pop()
    return (work, carry)

  def _parseDecimal(self, text: str) -> None:
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
    ten: Self = new._fromAbsDigits(False, Self._digitsFromInt(10))
    for i in range(start, len(t)):
      d: int = int(t[i]) - ord("0")
      inc: Self = new._fromAbsDigits(False, Self._digitsFromInt(d))
      mag = mag * ten + inc
    self._digits = mag._digits
    self._normalize()

  @immutable
  def _toDecimalStr(self) -> str:
    if not self:
      return "0"
    src: Self = abs(self)
    v: list[int] = []
    for i in range(len(src._digits)):
      v.append(src._digitAt(i))
    out: list[int] = []
    work: Self = new()
    work._digits = v
    while work._topIndex() > 0:
      step: (list[int], int) = work._divmod10Limbs()
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
  def _addAbs(self, other: Self) -> Self:
    na: int = self._topIndex()
    nb: int = other._topIndex()
    n: int = na
    if nb > n:
      n = nb
    digits: list[int] = []
    carry: int = 0
    for i in range(n):
      s: int = self._digitAt(i) + other._digitAt(i) + carry
      carry = 0
      if s >= Self._VarintBase:
        s -= Self._VarintBase
        carry = 1
      digits.append(s)
    if carry:
      digits.append(carry)
    return new._fromAbsDigits(False, digits)

  @immutable
  def _subAbs(self, other: Self) -> Self:
    na: int = self._topIndex()
    digits: list[int] = []
    borrow: int = 0
    for i in range(na):
      av: int = self._digitAt(i) - borrow
      bv: int = other._digitAt(i)
      borrow = 0
      diff: int = av - bv
      if diff < 0:
        diff += Self._VarintBase
        borrow = 1
      digits.append(diff)
    return new._fromAbsDigits(False, digits)

  @immutable
  def _mulAbs(self, other: Self) -> Self:
    na: int = self._topIndex()
    nb: int = other._topIndex()
    if not na or not nb:
      return new._zero()
    prod: list[int] = []
    for k in range(na + nb):
      prod.append(0)
    for i in range(na):
      carry: int64 = 0
      ai: int = self._digitAt(i)
      for j in range(nb):
        t: int64 = prod[i + j] + int64(ai) * other._digitAt(j) + carry
        carry = t // Self._VarintBase
        prod[i + j] = t % Self._VarintBase
      k: int = i + nb
      while carry:
        if k >= len(prod):
          prod.append(0)
        t2: int64 = prod[k] + carry
        carry = t2 // Self._VarintBase
        prod[k] = t2 % Self._VarintBase
        k += 1
    return new._fromAbsDigits(False, prod)

  @immutable
  def _divmodAbs(self, other: Self) -> (Self, Self):
    zero: Self = new._zero()
    if not other:
      return (zero, zero)
    if self._cmpAbs(other) < 0:
      return (zero, self)
    one: Self = new._one()
    cur: Self = one
    denom: Self = other
    accQ: Self = new._zero()
    rem: Self = self
    while denom._cmpAbs(rem) <= 0:
      cur <<= one
      denom <<= one
    cur >>= one
    denom >>= one
    while cur:
      if rem._cmpAbs(denom) >= 0:
        rem = rem._subAbs(denom)
        accQ = accQ._addAbs(cur)
      cur >>= one
      denom >>= one
    return (accQ, rem)

  @immutable
  def _shlAbs(self, nBits: int) -> Self:
    if nBits <= 0 or not self:
      return self
    digitShift: int = nBits // Self._VarintShift
    bitShift: int = nBits % Self._VarintShift
    na: int = self._topIndex()
    digits: list[int] = []
    for k in range(digitShift):
      digits.append(0)
    carry: int = 0
    for i in range(na):
      v: int = (self._digitAt(i) << bitShift) | carry
      carry = v >> Self._VarintShift
      digits.append(v & (Self._VarintBase - 1))
    if carry:
      digits.append(carry)
    return new._fromAbsDigits(False, digits)

  @immutable
  def _shrAbs(self, nBits: int) -> Self:
    if nBits <= 0 or not self:
      return self
    na: int = self._topIndex()
    digitShift: int = nBits // Self._VarintShift
    bitShift: int = nBits % Self._VarintShift
    if digitShift >= na:
      return new._zero()
    digits: list[int] = []
    carry: int = 0
    for j in range(na - 1, digitShift - 1, -1):
      v: int = self._digitAt(j)
      out: int = v >> bitShift
      if bitShift:
        if j > digitShift:
          low: int = v & ((1 << bitShift) - 1)
          out |= carry
          carry = low << (Self._VarintShift - bitShift)
        else:
          out |= carry
      digits.append(out)
    rev: list[int] = []
    for k in range(len(digits) - 1, -1, -1):
      rev.append(digits[k])
    return new._fromAbsDigits(False, rev)

  @immutable
  @immutable
  def _powAbs(self, exp: Self) -> Self:
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

  def _modInverse(self, mod: Self) -> Self:
    """模 ``mod`` 下的乘法逆元（``self`` 须与 ``mod`` 互素）。"""
    if not mod:
      raise ValueError("pow() 3rd argument cannot be 0")
    absSelf: Self = abs(self)
    a: Self = absSelf % mod
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

  @immutable
  def _powMod(self, exp: Self, mod: Self) -> Self:
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
      base = base._modInverse(mod)
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

  @immutable
  def __bool__(self) -> bool:
    return self._topIndex() > 0

  @immutable
  def __neg__(self) -> Self:
    if not self:
      return new._zero()
    out: Self = self
    out._neg = not self._neg
    out._hashOk = False
    if not out:
      out._neg = False
    return out

  @immutable
  def __pos__(self) -> Self:
    return self

  @immutable
  def __abs__(self) -> Self:
    if not self._neg:
      return self
    out: Self = self
    out._neg = False
    out._hashOk = False
    return out

  @immutable
  def __invert__(self) -> Self:
    one: Self = new._one()
    return -(self + one)

  @immutable
  def __add__(self, other: Self) -> Self:
    if not self._neg and not other._neg:
      return self._addAbs(other)
    if self._neg and other._neg:
      return -self._addAbs(other)
    c: int = self._cmpAbs(other)
    if not self._neg and other._neg:
      if c >= 0:
        return self._subAbs(other)
      return -other._subAbs(self)
    if c >= 0:
      return -self._subAbs(other)
    return other._subAbs(self)

  @immutable
  def __sub__(self, other: Self) -> Self:
    return self + (-other)

  @immutable
  def __mul__(self, other: Self) -> Self:
    p: Self = self._mulAbs(other)
    if (self._neg != other._neg) and p:
      return -p
    return p

  @immutable
  def __floordiv__(self, other: Self) -> Self:
    one: Self = new._one()
    parts: (Self, Self) = abs(self)._divmodAbs(abs(other))
    q: Self = parts[0]
    r: Self = parts[1]
    if self._neg != other._neg:
      if r:
        q += one
      q = -q
    return q

  @immutable
  def __mod__(self, other: Self) -> Self:
    q: Self = self // other
    prod: Self = q * other
    return self - prod

  @immutable
  def __truediv__(self, other: Self) -> float:
    return float(str(self)) / float(str(other))

  @overload
  @immutable
  def __pow__(self, other: Self) -> Self:
    base: Self = self
    return base._powAbs(other)

  @overload
  @immutable
  def __pow__(self, other: Self, mod: Self) -> Self:
    base: Self = self
    return base._powMod(other, mod)

  def __modmul__(self, other: Self, mod: Self) -> Self:
    return (self * other) % mod

  @immutable
  def __and__(self, other: Self) -> Self:
    na: int = self._topIndex()
    nb: int = other._topIndex()
    lim: int = na
    if nb < lim:
      lim = nb
    digits: list[int] = []
    for i in range(lim):
      digits.append(self._digitAt(i) & other._digitAt(i))
    return new._fromAbsDigits(False, digits)

  @immutable
  def __or__(self, other: Self) -> Self:
    na: int = self._topIndex()
    nb: int = other._topIndex()
    lim: int = na
    if nb > lim:
      lim = nb
    digits: list[int] = []
    for i in range(lim):
      digits.append(self._digitAt(i) | other._digitAt(i))
    return new._fromAbsDigits(False, digits)

  @immutable
  def __xor__(self, other: Self) -> Self:
    na: int = self._topIndex()
    nb: int = other._topIndex()
    lim: int = na
    if nb > lim:
      lim = nb
    digits: list[int] = []
    for i in range(lim):
      digits.append(self._digitAt(i) ^ other._digitAt(i))
    return new._fromAbsDigits(False, digits)

  @immutable
  def __lshift__(self, other: Self) -> Self:
    if int(other) < 0:
      return self >> (-other)
    return self._shlAbs(int(other))

  @immutable
  def __rshift__(self, other: Self) -> Self:
    if int(other) < 0:
      return self << (-other)
    return self._shrAbs(int(other))

  @immutable
  def __cmp__(self, other: Self) -> int:
    if self._neg != other._neg:
      if self._neg:
        return -1
      return 1
    c: int = self._cmpAbs(other)
    if self._neg:
      return -c
    return c

  def cacheHash(self, h: int) -> None:
    """外部已算好哈希时写入缓存（算法须与 ``__hash__`` 一致）。"""
    self._hash = h
    self._hashOk = True

  @immutable
  def _peekHash(self) -> int:
    """只读哈希（``const`` 比较用）；已缓存则直接返回，否则现场计算不落盘。"""
    if self._hashOk:
      return self._hash
    na: int = self._topIndex()
    if not na:
      return 0
    if na == 1:
      d: int = self._digitAt(0)
      if self._neg:
        return -2 if d == 1 else -d
      return d
    sign: int64 = -1 if self._neg else 1
    i: int = na - 1
    x: int64 = self._digitAt(i)
    i -= 1
    if Self._HashBits >= Self._VarintShift + Self._VarintShift and i >= 0:
      x = (x << Self._VarintShift) + self._digitAt(i)
      i -= 1
    for i in range(i, -1, -1):
      top: int64 = x >> (Self._HashBits - Self._VarintShift)
      x = ((x << Self._VarintShift) & Self._HashModulus) | top
      x += self._digitAt(i)
      if x >= Self._HashModulus:
        x -= Self._HashModulus
    x *= sign
    if x == -1:
      return -2
    return int(x)

  def __hash__(self) -> int:
    """对齐 CPython ``long_hash``（惰性缓存），供 ``dict[varint, …]`` 等。"""
    if self._hashOk:
      return self._hash
    h: int = self._peekHash()
    self._hash = h
    self._hashOk = True
    return h

  def __repr__(self) -> str:
    return str(self)

  def __str__(self) -> str:
    return self._toDecimalStr()

  def __format__(self, formatSpec: str) -> str:
    if not formatSpec:
      return str(self)
    return str(self)

  @immutable
  def __int__(self) -> int:
    na: int = self._topIndex()
    if not na:
      return 0
    acc: int = 0
    for i in range(na - 1, -1, -1):
      acc *= Self._VarintBase
      acc += self._digitAt(i)
    if self._neg:
      acc = -acc
    return acc

  @immutable
  def __float__(self) -> float:
    return float(str(self))

  def bitLength(self) -> int:
    if not self:
      return 0
    na: int = self._topIndex()
    top: int = self._digitAt(na - 1)
    bits: int = (na - 1) * Self._VarintShift
    while top:
      bits += 1
      top >>= 1
    return bits

  def bitCount(self) -> int:
    c: int = 0
    na: int = self._topIndex()
    for i in range(na):
      v: int = self._digitAt(i)
      while v:
        if v & 1:
          c += 1
        v >>= 1
    return c

  def conjugate(self) -> Self:
    return self

  def isInteger(self) -> bool:
    return True

  def asIntegerRatio(self) -> (Self, Self):
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
