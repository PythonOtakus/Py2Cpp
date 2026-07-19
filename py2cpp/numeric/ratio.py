"""有理数基础设施：``float`` 精确 ``as_integer_ratio``（IEEE 754 位模式）。"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import OverflowError
from .varint import varint


@native
@native_name("numeric_ratio_*")
@immutable
def float64_bits(x: float64) -> uint64:
  ...


@immutable
def float_as_integer_ratio(x: float64) -> (varint, varint):
  """对齐 CPython ``float.as_integer_ratio()``（约分、分母为正）。"""
  if float64.isNaN(x) or float64.isInf(x):
    raise OverflowError("cannot convert NaN or infinity to integer ratio")
  zero: varint = varint("0")
  one: varint = varint("1")
  if x == 0.0:
    return (zero, one)
  bits: uint64 = float64_bits(x)
  sign: bool = (bits >> 63) != 0
  exp_field: int = (bits >> 52) & 0x7FF
  frac_mask: uint64 = 4503599627370495
  fraction: uint64 = bits & frac_mask
  num: varint
  den: varint = one
  exp_val: int = 0
  if exp_field == 0:
    if fraction == 0:
      return (zero, one)
    exp_val = -1022
    while (fraction & 1) == 0:
      fraction >>= 1
      exp_val -= 1
    num = varint(str(int64(fraction)))
    exp_val -= 52
  else:
    one_u: uint64 = 1
    fraction |= one_u << 52
    exp_val = exp_field - 1023 - 52
    num = varint(str(int64(fraction)))
  if exp_val >= 0:
    num <<= varint(str(exp_val))
  else:
    den <<= varint(str(-exp_val))
  if sign:
    num = -num
  g: varint = gcd_varint(abs(num), den)
  num //= g
  den //= g
  if den < zero:
    num = -num
    den = -den
  return (num, den)


@immutable
def gcd_varint(a: varint, b: varint) -> varint:
  """``math.gcd`` 的 ``varint`` 版（非负输入）。"""
  x: varint = a
  y: varint = b
  zero: varint = varint("0")
  while y != zero:
    t: varint = y
    y = x % y
    x = t
  return x
