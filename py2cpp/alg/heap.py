"""二叉堆 / 优先队列（最小堆，对齐 ``heapq`` 语义）。

``Heap``：纯堆，无成员查询。

``IndexedHeap``：堆 + ``dict[T, int]`` 下标；**每个 ``T`` 至多出现一次**（重复 ``push`` 忽略）。

| 类 | 方法 | 说明 |
|----|------|------|
| ``Heap`` | ``push`` / ``pop`` / ``top`` / ``len`` / ``bool`` | 标准最小堆 |
| ``IndexedHeap`` | 上列 + ``word in h`` / ``remove`` / ``discard`` / ``clear`` | ``remove`` 删任意元；``discard`` 缺失不报错 |
"""
from ..builtins import *
from ..core.exceptions import IndexError, KeyError
from ..util.protocols import Comparable, DictKey
from ..util.dict import dict
from ..util.list import list
from ..util.mixins import ContainerMixin


class Heap[T: Comparable](ContainerMixin):
  """数组二叉最小堆；根为 ``_data[0]``。"""

  def __init__(self):
    self._data: list[T] = []

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    data: list[T] = []
    self._data = data
    for i in range(len(other._data)):
      self._data.append(other._data[i])

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    self._data = other._data
    data: list[T] = []
    other._data = data

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new()
    out.__copy__(self)
    return out

  def push(self, x: T) -> None:
    self._data.append(x)
    self._sift_up(len(self._data) - 1)

  def pop(self) -> T:
    if not self._data:
      raise IndexError("pop from empty heap")
    n: int = len(self._data)
    out: T = self.top()
    if n == 1:
      self._data.pop()
      return out
    self._data[0] = self._data[n - 1]
    self._data.pop()
    self._sift_down(0)
    return out

  def top(self) -> T:
    if not self._data:
      raise IndexError("top from empty heap")
    return self._data[0]

  @immutable
  def __len__(self) -> int:
    return len(self._data)

  @immutable
  def __bool__(self) -> bool:
    return bool(self._data)

  @immutable
  @staticmethod
  def _parent(i: int) -> int:
    return (i - 1) // 2

  @immutable
  @staticmethod
  def _left(i: int) -> int:
    return i * 2 + 1

  def _sift_up(self, i: int) -> None:
    while i > 0:
      p: int = Self._parent(i)
      if self._data[p] <= self._data[i]:
        break
      self._data[p], self._data[i] = self._data[i], self._data[p]
      i = p

  def _sift_down(self, i: int) -> None:
    n: int = len(self._data)
    while True:
      left: int = Self._left(i)
      if left >= n:
        break
      best: int = left
      right: int = left + 1
      if right < n and self._data[right] < self._data[left]:
        best = right
      if self._data[i] <= self._data[best]:
        break
      self._data[i], self._data[best] = self._data[best], self._data[i]
      i = best


class IndexedHeap[T: Comparable & DictKey](ContainerMixin):
  """二叉最小堆 + 元素→下标表；``_swap`` 时同步更新 ``_pos``。"""

  def __init__(self):
    self._data: list[T] = []
    self._pos: dict[T, int] = {}

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    data: list[T] = []
    pos: dict[T, int] = {}
    self._data = data
    self._pos = pos
    for i in range(len(other._data)):
      x: T = other._data[i]
      self._data.append(x)
      self._pos[x] = i

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    self._data = other._data
    self._pos = other._pos
    data: list[T] = []
    pos: dict[T, int] = {}
    other._data = data
    other._pos = pos

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new()
    out.__copy__(self)
    return out

  def push(self, x: T) -> None:
    if x in self._pos:
      return
    self._data.append(x)
    i: int = len(self._data) - 1
    self._pos[x] = i
    self._sift_up(i)

  def pop(self) -> T:
    if not self._data:
      raise IndexError("pop from empty heap")
    out: T = self.top()
    self._erase_at(0)
    return out

  def top(self) -> T:
    if not self._data:
      raise IndexError("top from empty heap")
    return self._data[0]

  def remove(self, x: T) -> None:
    if x not in self._pos:
      raise KeyError("remove")
    self._erase_at(self._pos[x])

  def discard(self, x: T) -> None:
    if x not in self._pos:
      return
    self._erase_at(self._pos[x])

  def clear(self) -> None:
    self._data = []
    self._pos = {}

  @immutable
  def __contains__(self, x: T) -> bool:
    return x in self._pos

  @immutable
  def __len__(self) -> int:
    return len(self._data)

  @immutable
  def __bool__(self) -> bool:
    return bool(self._data)

  @immutable
  @staticmethod
  def _parent(i: int) -> int:
    return (i - 1) // 2

  @immutable
  @staticmethod
  def _left(i: int) -> int:
    return i * 2 + 1

  def _swap(self, i: int, j: int) -> None:
    if i == j:
      return
    if i > j:
      self._swap(j, i)
      return
    b: T = self._data.pop(j)
    a: T = self._data.pop(i)
    self._data.insert(i, b)
    self._data.insert(j, a)
    self._pos[b] = i
    self._pos[a] = j

  def _erase_at(self, i: int) -> None:
    del self._pos[self._data[i]]
    n: int = len(self._data)
    if i == n - 1:
      self._data.pop()
      return
    self._data[i] = self._data[n - 1]
    self._pos[self._data[i]] = i
    self._data.pop()
    if i > 0 and self._data[i] < self._data[Self._parent(i)]:
      self._sift_up(i)
    else:
      self._sift_down(i)

  def _sift_up(self, i: int) -> None:
    while i > 0:
      p: int = Self._parent(i)
      if self._data[p] <= self._data[i]:
        break
      self._swap(p, i)
      i = p

  def _sift_down(self, i: int) -> None:
    n: int = len(self._data)
    while True:
      left: int = Self._left(i)
      if left >= n:
        break
      best: int = left
      right: int = left + 1
      if right < n and self._data[right] < self._data[left]:
        best = right
      if self._data[i] <= self._data[best]:
        break
      self._swap(i, best)
      i = best
