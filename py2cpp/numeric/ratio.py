"""有理数基础设施：``float`` 精确 ``asIntegerRatio``（IEEE 754 位模式）。"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import OverflowError
from .varint import varint


@native
@native_name("numeric_ratio_*")
@immutable
def float64Bits(x: float64) -> uint64:
  ...


@immutable
def floatAsIntegerRatio(x: float64) -> (varint, varint):
  """对齐 CPython ``float.asIntegerRatio()``（约分、分母为正）。"""
  if float64.isNaN(x) or float64.isInf(x):
    raise OverflowError("cannot convert NaN or infinity to integer ratio")
  zero: varint = varint("0")
  one: varint = varint("1")
  if x == 0.0:
    return (zero, one)
  bits: uint64 = float64Bits(x)
  sign: bool = (bits >> 63) != 0
  expField: int = (bits >> 52) & 0x7FF
  fracMask: uint64 = 4503599627370495
  fraction: uint64 = bits & fracMask
  num: varint
  den: varint = one
  expVal: int = 0
  if expField == 0:
    if fraction == 0:
      return (zero, one)
    expVal = -1022
    while (fraction & 1) == 0:
      fraction >>= 1
      expVal -= 1
    num = varint(str(int64(fraction)))
    expVal -= 52
  else:
    oneU: uint64 = 1
    fraction |= oneU << 52
    expVal = expField - 1023 - 52
    num = varint(str(int64(fraction)))
  if expVal >= 0:
    num <<= varint(str(expVal))
  else:
    den <<= varint(str(-expVal))
  if sign:
    num = -num
  g: varint = gcdVarint(abs(num), den)
  num //= g
  den //= g
  if den < zero:
    num = -num
    den = -den
  return (num, den)


@immutable
def gcdVarint(a: varint, b: varint) -> varint:
  """``math.gcd`` 的 ``varint`` 版（非负输入）。"""
  x: varint = a
  y: varint = b
  zero: varint = varint("0")
  while y != zero:
    t: varint = y
    y = x % y
    x = t
  return x
