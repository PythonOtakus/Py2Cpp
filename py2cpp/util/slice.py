"""slice[T, U]：切片对象；``T`` 为起止界类型，``U`` 为步长类型（如 ``slice[int,int]``、日后 ``slice[time,timedelta]``）。"""
from ..builtins import *
from ..core.exceptions import ValueError

# 与翻译器 ``visit_Subscript`` 中构造 ``PySlice<int,int>(...)`` 的缺省占位一致（仅用于整型界）
SLICE_START_UNSET: int = -2000000001
SLICE_STOP_UNSET: int = -2000000002


@native_name("PySlice")
class slice[T, U]:
  """``slice(start, stop, step)`` / ``seq[slice(...)]`` 的编译期表示。"""

  def __init__(self, start: T, stop: T, step: U):
    self._start: T = start
    self._stop: T = stop
    self._step: U = step

  @immutable
  def indices(self, length: int) -> (int, int, int):
    """等价于 CPython ``slice.indices(length)``（当前用于 ``slice[int,int]`` 等整型界）。"""
    step: int = self._step
    if step == 0:
      raise ValueError("slice step cannot be zero")
    start: int = self._start
    stop: int = self._stop
    if start == SLICE_START_UNSET:
      if step > 0:
        start = 0
      else:
        start = length - 1
    else:
      if start < 0:
        start += length
      if start < 0:
        if step > 0:
          start = 0
        else:
          start = -1
      elif start >= length:
        if step > 0:
          start = length
        else:
          start = length - 1
    if stop == SLICE_STOP_UNSET:
      if step > 0:
        stop = length
      else:
        stop = -1
    else:
      if stop < 0:
        stop += length
      if stop < 0:
        if step > 0:
          stop = 0
        else:
          stop = -1
      elif stop > length:
        stop = length
    return start, stop, step
