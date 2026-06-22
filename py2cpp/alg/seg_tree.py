"""线段树（点修 + 区间聚合，v1 无懒标记）。

公开 API（对齐 ``FenTree`` 下标/切片约定）：

| 写法 | 说明 |
|------|------|
| ``st[i]`` | 下标 ``i`` 处当前值（点查，``__getitem__``） |
| ``st[l:r]`` | 半开区间 ``[l, r)`` 聚合（``__getitem__`` 切片；``mode`` 为 ``AggMode``） |
| ``st[i] = v`` | 单点赋值（``__setitem__``） |
| ``len(st)`` / ``i in st`` | 长度 ``n``、下标是否合法 |
"""
from ..builtins import *
from ..core.exceptions import IndexError, ValueError
from .agg_mode import AggMode
from .container_mixin import AlgContainerMixin


class SegTree(AlgContainerMixin):
  """迭代线段树；下标 0-based。"""

  def __init__(self, n: int, mode: AggMode):
    if n < 0:
      raise ValueError("n must be non-negative")
    self._n: int = n
    self._mode: AggMode = mode
    self._size: int = 1
    while self._size < n:
      self._size *= 2
    cap: int = self._size * 2
    self._tree: int[:] = new(cap)
    sentinel: int = 0
    if mode == AggMode.Min:
      sentinel = Self._max_int()
    elif mode == AggMode.Max:
      sentinel = Self._min_int()
    for i in range(cap):
      self._tree[i] = sentinel

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    self._n = other._n
    self._mode = other._mode
    self._size = other._size
    cap: int = other._size * 2
    self._tree = new(cap)
    for i in range(cap):
      self._tree[i] = other._tree[i]

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    mode: AggMode = other._mode
    self._n = other._n
    self._mode = other._mode
    self._size = other._size
    self._tree = other._tree
    other._n = 0
    other._mode = mode
    other._size = 1
    other._tree = new(2)
    sentinel: int = 0
    if mode == AggMode.Min:
      sentinel = Self._max_int()
    elif mode == AggMode.Max:
      sentinel = Self._min_int()
    for i in range(2):
      other._tree[i] = sentinel

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new(0, self._mode)
    out.__copy__(self)
    return out

  @immutable
  @staticmethod
  def _min_int() -> int:
    return -2147483647

  @immutable
  @staticmethod
  def _max_int() -> int:
    return 2147483647

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
      raise IndexError("segtree index out of range")

  @immutable
  def _check_range(self, left: int, right: int) -> None:
    if left < 0 or right < left or right >= self._n:
      raise IndexError("segtree range out of range")

  @immutable
  def _combine(self, a: int, b: int) -> int:
    if self._mode == AggMode.Sum:
      return a + b
    if self._mode == AggMode.Min:
      return a if a < b else b
    return a if a > b else b

  @immutable
  def _identity(self) -> int:
    if self._mode == AggMode.Sum:
      return 0
    if self._mode == AggMode.Min:
      return Self._max_int()
    return Self._min_int()

  @immutable
  @overload
  def __getitem__(self, i: int) -> int:
    self._check(i)
    return self._tree[self._size + i]

  @immutable
  @overload
  def __getitem__(self, index: slice[int, int]) -> int:
    start: int
    stop: int
    step: int
    start, stop, step = index.indices(self._n)
    if step != 1:
      raise ValueError("segtree slice step must be 1")
    if start >= stop:
      return self._identity()
    return self._range_query(start, stop - 1)

  def __setitem__(self, i: int, value: int) -> None:
    self._check(i)
    pos: int = self._size + i
    self._tree[pos] = value
    pos //= 2
    while pos >= 1:
      left: int = pos * 2
      right: int = left + 1
      self._tree[pos] = self._combine(self._tree[left], self._tree[right])
      pos //= 2

  @immutable
  def _range_query(self, left: int, right: int) -> int:
    self._check_range(left, right)
    l: int = self._size + left
    r: int = self._size + right
    res: int = self._identity()
    while l <= r:
      if l % 2 == 1:
        res = self._combine(res, self._tree[l])
        l += 1
      if r % 2 == 0:
        res = self._combine(res, self._tree[r])
        r -= 1
      l //= 2
      r //= 2
    return res
