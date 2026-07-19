"""数值塔 ``@protocol`` 概念（``numbers`` / PEP 3141，对齐 Python 3.13 ``Lib/numbers.py``）。

仅用于翻译期 SFINAE（``Protocol_requires<T>``），不生成 C++ 类、不作继承基类。
"""
from __future__ import annotations

from ..builtins import *
from ..core.protocols import Self, protocol


@protocol
class Number:
  """``numbers.Number``：可哈希（``hash(x)`` → ``__hash__``）。"""

  def __hash__(self) -> int: ...


@protocol
class Complex:
  """``numbers.Complex`` 核心运算（``+`` ``-`` ``*`` ``/`` ``**`` ``==``；``/`` 走 ``::__truediv__``）。"""

  def __eq__(self, other: Self) -> bool: ...

  def __add__(self, other: Self) -> Self: ...

  def __mul__(self, other: Self) -> Self: ...

  def __truediv__(self, other: Self) -> float: ...

  def __pow__(self, other: Self) -> Self: ...

  def __neg__(self) -> Self: ...

  def __pos__(self) -> Self: ...


@protocol
class Real(Complex):
  """``numbers.Real``：实数比较、整除/取模、转 ``float``。"""

  def __lt__(self, other: Self) -> bool: ...

  def __le__(self, other: Self) -> bool: ...

  def __gt__(self, other: Self) -> bool: ...

  def __ge__(self, other: Self) -> bool: ...

  def __floordiv__(self, other: Self) -> Self: ...

  def __mod__(self, other: Self) -> Self: ...

  def __float__(self) -> float: ...


@protocol
class Rational(Real):
  """``numbers.Rational``：``numerator`` / ``denominator`` 字段或 ``@property``（见 ``numbers``）。"""

  denominator: int = ...

  numerator: int = ...


@protocol
class Integral(Real):
  """``numbers.Integral``（不含 ``Rational`` 属性探测）：``int`` 与位运算。"""

  def __lshift__(self, other: Self) -> Self: ...

  def __rshift__(self, other: Self) -> Self: ...

  def __and__(self, other: Self) -> Self: ...

  def __or__(self, other: Self) -> Self: ...

  def __xor__(self, other: Self) -> Self: ...

  def __int__(self) -> int: ...

  def __invert__(self) -> Self: ...


@protocol
class Arithmetic:
  """兼容别名：``Real`` 的 ``%`` / ``/`` / ``//`` 三项（``::__mod__`` 等全局函数）。"""

  def __truediv__(self, other: Self) -> float: ...

  def __floordiv__(self, other: Self) -> Self: ...

  def __mod__(self, other: Self) -> Self: ...
