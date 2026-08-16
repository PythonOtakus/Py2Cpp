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
from ..numeric.protocols import ComplexType
from ..util.mixins import ContainerMixin


class FenTree[Element: ComplexType](ContainerMixin):
  """一点修改 + 前缀和；内部 1-indexed BIT，对外 0-indexed。"""

  def __init__(self, n: int):
    if n < 0:
      raise ValueError("n must be non-negative")
    self._n: int = n
    self._bit: Element[:] = new(n + 1)

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._n = other._n
    self._bit = new(other._n + 1)
    for i in range(other._n + 1):
      self._bit[i] = other._bit[i]

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._n = other._n
    self._bit = other._bit
    other._n = 0
    other._bit = new(1)

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
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
  def __getitem__(self, i: int) -> Element:
    self._check(i)
    if i == 0:
      return self._prefixSum(0)
    return self._prefixSum(i) - self._prefixSum(i - 1)

  @immutable
  @overload
  def __getitem__(self, index: slice[int, int]) -> Element:
    start: int
    stop: int
    step: int
    start, stop, step = index.indices(self._n)
    if step != 1:
      raise ValueError("fentree slice step must be 1")
    if start >= stop:
      return self._prefixSum(-1)
    return self._rangeSum(start, stop - 1)

  def __setitem__(self, i: int, value: Element) -> None:
    old: Element = self[i]
    self.add(i, value - old)

  def add(self, i: int, delta: Element) -> None:
    self._check(i)
    idx: int = i + 1
    while idx <= self._n:
      self._bit[idx] += delta
      idx += idx & -idx

  @immutable
  def _prefixSum(self, i: int) -> Element:
    if i < 0:
      total: Element = 0
      return total
    if i >= self._n:
      raise IndexError("fentree index out of range")
    idx: int = i + 1
    total: Element = 0
    while idx > 0:
      total += self._bit[idx]
      idx -= idx & -idx
    return total

  @immutable
  def _rangeSum(self, left: int, right: int) -> Element:
    if left > right:
      raise ValueError("empty range")
    if right < 0 or left >= self._n:
      raise IndexError("fentree range out of range")
    if left < 0:
      left = 0
    if right >= self._n:
      right = self._n - 1
    if left == 0:
      return self._prefixSum(right)
    return self._prefixSum(right) - self._prefixSum(left - 1)

