"""参数校验 ``@descriptor``（内联到宿主字段 / 函数签名）。"""
from ..builtins import *
from py2cpp import descriptor
from py2cpp.util.protocols import ComparableType, SizedType


@descriptor
class RangeVar[Element: ComparableType]:
  """闭区间 ``[lo, hi]``；越界 ``ValueError``。宿主写法：``x: int @RangeVar(0, 10) = 0``。"""

  def __init__(self, lo: Element, hi: Element):
    if lo > hi:
      raise ValueError("invalid range")
    self._lo = lo
    self._hi = hi

  def __get__(self):
    ...

  def __set__(self, value: Element):
    if value < self._lo or value > self._hi:
      raise ValueError("out of range")
    self.__value__ = value


@descriptor
class LenRangeVar[Element: SizedType]:
  """``minLen <= len(value) <= maxLen``；越界 ``ValueError``。"""

  def __init__(self, minLen: int, maxLen: int):
    if minLen < 0 or maxLen < minLen:
      raise ValueError("invalid length range")
    self._minLen = minLen
    self._maxLen = maxLen

  def __get__(self):
    ...

  def __set__(self, value: Element):
    n: int = len(value)
    if n < self._minLen or n > self._maxLen:
      raise ValueError("bad length")
    self.__value__ = value
