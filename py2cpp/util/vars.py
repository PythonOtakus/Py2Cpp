"""参数校验 ``@descriptor``（内联到宿主字段 / 函数签名）。"""
from ..builtins import *
from py2cpp import descriptor
from py2cpp.core.protocols import Comparable, Sized


@descriptor
class RangeVar[T: Comparable]:
  """闭区间 ``[lo, hi]``；越界 ``ValueError``。宿主写法：``x: int @RangeVar(0, 10) = 0``。"""

  def __init__(self, lo: T, hi: T):
    if lo > hi:
      raise ValueError("invalid range")
    self._lo = lo
    self._hi = hi

  def __get__(self):
    ...

  def __set__(self, value: T):
    if value < self._lo or value > self._hi:
      raise ValueError("out of range")
    self.__value__ = value


@descriptor
class LenRangeVar[T: Sized]:
  """``min_len <= len(value) <= max_len``；越界 ``ValueError``。"""

  def __init__(self, min_len: int, max_len: int):
    if min_len < 0 or max_len < min_len:
      raise ValueError("invalid length range")
    self._min_len = min_len
    self._max_len = max_len

  def __get__(self):
    ...

  def __set__(self, value: T):
    n: int = len(value)
    if n < self._min_len or n > self._max_len:
      raise ValueError("bad length")
    self.__value__ = value
