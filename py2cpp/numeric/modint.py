"""模整数 ``ModInt[T, Mod]``（``Mod`` 为编译期非类型模板实参）。

路径：``py2cpp.numeric.modint``。``Mod`` 在类头写作 ``Mod: T``，译为 C++ ``template<typename T, T Mod>``。
``/`` 为模乘逆元（``a / b == a * b.inv``）；``//`` 仍为整数地板除（作用在剩余类上）。
不同 ``Mod`` 的 ``ModInt`` 相加由 C++ 模板实参不匹配在编译期拒绝。
"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import ValueError
from ..core.protocols import Integral


@copyable
class ModInt[T: Integral, Mod: T]:
  """剩余类 ``[0, Mod)`` 上的模算术；``Mod`` 须为编译期正整数常量。"""

  def __init__(self, v: T = 0):
    self._v: T = Self._normalize(v)

  def __copy__(self, other: Self):
    self._v = other._v

  @staticmethod
  @immutable
  def _normalize(v: T) -> T:
    r: T = v % Mod
    if r < 0:
      r += Mod
    return r

  @staticmethod
  @immutable
  def _mod_mul(a: T, b: T) -> T:
    return modmul(a, b, Mod)

  @staticmethod
  @immutable
  def _mod_inverse(v: T) -> T:
    return pow(v, -1, Mod)

  @staticmethod
  @immutable
  def zero() -> Self:
    return new(0)

  @staticmethod
  @immutable
  def one() -> Self:
    return new(1)

  @immutable
  def __int__(self) -> T:
    return self._v

  @property
  def inv(self) -> Self:
    return new(Self._mod_inverse(self._v))

  @immutable
  def __eq__(self, other: Self) -> bool:
    return self._v == other._v

  @immutable
  def __bool__(self) -> bool:
    return self._v != 0

  @immutable
  def __neg__(self) -> Self:
    if self._v == 0:
      return new(0)
    return new(Mod - self._v)

  @immutable
  def __add__(self, other: Self) -> Self:
    return new(self._v + other._v)

  @immutable
  def __sub__(self, other: Self) -> Self:
    return new(self._v - other._v)

  @immutable
  def __mul__(self, other: Self) -> Self:
    return new(Self._mod_mul(self._v, other._v))

  @immutable
  def __truediv__(self, other: Self) -> Self:
    return self * other.inv

  @immutable
  def __floordiv__(self, other: Self) -> T:
    return self._v // other._v

  @immutable
  def __pow__(self, e: T) -> Self:
    return new(pow(self._v, e, Mod))
