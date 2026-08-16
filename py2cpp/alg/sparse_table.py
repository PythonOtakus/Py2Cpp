"""稀疏表（静态区间 min/max RMQ，O(1) 查询）。

公开 API（对齐 ``FenTree`` 下标/切片约定；**静态**，无 ``__setitem__``）：

| 写法 | 说明 |
|------|------|
| ``st[i]`` | 下标 ``i`` 处原数组值（点查） |
| ``st[l:r]`` | 半开区间 ``[l, r)`` 上 min/max（切片；``mode`` 为 ``AggModeEnum.Min`` / ``AggModeEnum.Max``） |
| ``len(st)`` / ``i in st`` | 长度 ``n``、下标是否合法 |
"""
from ..builtins import *
from ..core.exceptions import IndexError, ValueError
from ..util.list import list
from .agg_mode import AggModeEnum
from ..util.mixins import ContainerMixin


class SparseTable(ContainerMixin):
  """静态 RMQ；构建后不可改原数组。"""

  def __init__(self, data: list[int], mode: AggModeEnum):
    match mode:
      case AggModeEnum.Min | AggModeEnum.Max:
        pass
      case _:
        raise ValueError("sparse table mode must be AggModeEnum.Min or AggModeEnum.Max")
    n: int = len(data)
    self._n: int = n
    self._mode: AggModeEnum = mode
    if n == 0:
      self._log: int[:] = new(1)
      self._log[0] = 0
      self._st: list[int[:]] = []
      return
    self._log: int[:] = new(n + 1)
    self._log[0] = 0
    self._log[1] = 0
    for i in range(2, n + 1):
      self._log[i] = self._log[i // 2] + 1
    levels: int = self._log[n] + 1
    self._st: list[int[:]] = []
    row0: int[:] = new(n)
    for i in range(n):
      row0[i] = data[i]
    self._st.append(row0)
    for k in range(1, levels):
      span: int = 1 << k
      half: int = span // 2
      prev: int[:] = self._st[k - 1]
      row: int[:] = new(n)
      last: int = n - span
      if last < 0:
        last = -1
      for i in range(last + 1):
        a: int = prev[i]
        b: int = prev[i + half]
        if mode == AggModeEnum.Min:
          row[i] = a if a < b else b
        else:
          row[i] = a if a > b else b
      self._st.append(row)

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._n = other._n
    self._mode = other._mode
    self._log = new(other._n + 1)
    for i in range(other._n + 1):
      self._log[i] = other._log[i]
    st: list[int[:]] = []
    self._st = st
    for k in range(len(other._st)):
      row: int[:] = new(other._n)
      src: int[:] = other._st[k]
      for i in range(other._n):
        row[i] = src[i]
      self._st.append(row)

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._n = other._n
    self._mode = other._mode
    self._log = other._log
    self._st = other._st
    other._n = 0
    other._log = new(1)
    other._log[0] = 0
    st: list[int[:]] = []
    other._st = st

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    data: list[int] = []
    if self._n > 0:
      for i in range(self._n):
        data.append(self._st[0][i])
    return new(data, self._mode)

  @immutable
  def __len__(self) -> int:
    return self._n

  @immutable
  def __bool__(self) -> bool:
    return self._n > 0

  @immutable
  def __contains__(self, i: int) -> bool:
    return 0 <= i < self._n

  @immutable
  def _check(self, i: int) -> None:
    if i not in self:
      raise IndexError("sparse table index out of range")

  @immutable
  def _checkRange(self, left: int, right: int) -> None:
    if self._n == 0:
      raise IndexError("sparse table index out of range")
    if left < 0 or right < left or right >= self._n:
      raise IndexError("sparse table range out of range")

  @immutable
  def _combine(self, a: int, b: int) -> int:
    if self._mode == AggModeEnum.Min:
      return a if a < b else b
    return a if a > b else b

  @immutable
  def _identity(self) -> int:
    if self._mode == AggModeEnum.Min:
      return Self._maxInt()
    return Self._minInt()

  @immutable
  @staticmethod
  def _minInt() -> int:
    return -2147483647

  @immutable
  @staticmethod
  def _maxInt() -> int:
    return 2147483647

  @immutable
  @overload
  def __getitem__(self, i: int) -> int:
    self._check(i)
    return self._st[0][i]

  @immutable
  @overload
  def __getitem__(self, index: slice[int, int]) -> int:
    if self._n == 0:
      raise IndexError("sparse table index out of range")
    start: int
    stop: int
    step: int
    start, stop, step = index.indices(self._n)
    if step != 1:
      raise ValueError("sparse table slice step must be 1")
    if start >= stop:
      return self._identity()
    return self._rangeQuery(start, stop - 1)

  @immutable
  def _rangeQuery(self, left: int, right: int) -> int:
    self._checkRange(left, right)
    if left == right:
      return self._st[0][left]
    k: int = self._log[right - left + 1]
    row: int[:] = self._st[k]
    j: int = right - (1 << k) + 1
    a: int = row[left]
    b: int = row[j]
    return self._combine(a, b)
