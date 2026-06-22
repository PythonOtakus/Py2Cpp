"""树状数组（Fenwick / Binary Indexed Tree）。

公开 API（Python 下标/常用命名，**非** STL ``fenwick_tree::update/query``）：

| 写法 | 说明 |
|------|------|
| ``bit[i]`` | 下标 ``i`` 处当前值（点查，``__getitem__``） |
| ``bit[l:r]`` | 半开区间 ``[l, r)`` 之和（``__getitem__`` 切片） |
| ``bit[i] = v`` | 将下标 ``i`` 置为 ``v``（``__setitem__``，内部差分更新） |
| ``bit.add(i, delta)`` | 单点加 ``delta`` |
| ``len(bit)`` / ``x in bit`` | 长度 ``n``、下标是否合法 |
"""
from ..builtins import *
from ..core.exceptions import IndexError, ValueError
from ..core.protocols import Complex
from .container_mixin import AlgContainerMixin


class FenTree[T: Complex](AlgContainerMixin):
  """一点修改 + 前缀和；内部 1-indexed BIT，对外 0-indexed。"""

  def __init__(self, n: int):
    if n < 0:
      raise ValueError("n must be non-negative")
    self._n: int = n
    self._bit: T[:] = new(n + 1)

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    self._n = other._n
    self._bit = new(other._n + 1)
    for i in range(other._n + 1):
      self._bit[i] = other._bit[i]

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    self._n = other._n
    self._bit = other._bit
    other._n = 0
    other._bit = new(1)

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new(self._n)
    out.__copy__(self)
    return out

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
      raise IndexError("fentree index out of range")

  @immutable
  @overload
  def __getitem__(self, i: int) -> T:
    self._check(i)
    if i == 0:
      return self._prefix_sum(0)
    return self._prefix_sum(i) - self._prefix_sum(i - 1)

  @immutable
  @overload
  def __getitem__(self, index: slice[int, int]) -> T:
    start: int
    stop: int
    step: int
    start, stop, step = index.indices(self._n)
    if step != 1:
      raise ValueError("fentree slice step must be 1")
    if start >= stop:
      return self._prefix_sum(-1)
    return self._range_sum(start, stop - 1)

  def __setitem__(self, i: int, value: T) -> None:
    old: T = self[i]
    self.add(i, value - old)

  def add(self, i: int, delta: T) -> None:
    self._check(i)
    idx: int = i + 1
    while idx <= self._n:
      self._bit[idx] += delta
      idx += idx & -idx

  @immutable
  def _prefix_sum(self, i: int) -> T:
    if i < 0:
      total: T = 0
      return total
    if i >= self._n:
      raise IndexError("fentree index out of range")
    idx: int = i + 1
    total: T = 0
    while idx > 0:
      total += self._bit[idx]
      idx -= idx & -idx
    return total

  @immutable
  def _range_sum(self, left: int, right: int) -> T:
    if left > right:
      raise ValueError("empty range")
    if right < 0 or left >= self._n:
      raise IndexError("fentree range out of range")
    if left < 0:
      left = 0
    if right >= self._n:
      right = self._n - 1
    if left == 0:
      return self._prefix_sum(right)
    return self._prefix_sum(right) - self._prefix_sum(left - 1)

