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
from ..util.protocols import ComparableType, DictKeyType
from ..util.dict import dict
from ..util.list import list
from ..util.mixins import ContainerMixin


class Heap[Element: ComparableType](ContainerMixin):
  """数组二叉最小堆；根为 ``_data[0]``。"""

  def __init__(self):
    self._data: list[Element] = []

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    data: list[Element] = []
    self._data = data
    for i in range(len(other._data)):
      self._data.append(other._data[i])

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._data = other._data
    data: list[Element] = []
    other._data = data

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = new()
    out.__copy__(self)
    return out

  def push(self, x: Element) -> None:
    self._data.append(x)
    self._siftUp(len(self._data) - 1)

  def pop(self) -> Element:
    if not self._data:
      raise IndexError("pop from empty heap")
    n: int = len(self._data)
    out: Element = self.top()
    if n == 1:
      self._data.pop()
      return out
    self._data[0] = self._data[n - 1]
    self._data.pop()
    self._siftDown(0)
    return out

  def top(self) -> Element:
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

  def _siftUp(self, i: int) -> None:
    while i > 0:
      p: int = Self._parent(i)
      if self._data[p] <= self._data[i]:
        break
      self._data[p], self._data[i] = self._data[i], self._data[p]
      i = p

  def _siftDown(self, i: int) -> None:
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


class IndexedHeap[Element: ComparableType & DictKeyType](ContainerMixin):
  """二叉最小堆 + 元素→下标表；``_swap`` 时同步更新 ``_pos``。"""

  def __init__(self):
    self._data: list[Element] = []
    self._pos: dict[Element, int] = {}

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    data: list[Element] = []
    pos: dict[Element, int] = {}
    self._data = data
    self._pos = pos
    for i in range(len(other._data)):
      x: Element = other._data[i]
      self._data.append(x)
      self._pos[x] = i

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._data = other._data
    self._pos = other._pos
    data: list[Element] = []
    pos: dict[Element, int] = {}
    other._data = data
    other._pos = pos

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = new()
    out.__copy__(self)
    return out

  def push(self, x: Element) -> None:
    if x in self._pos:
      return
    self._data.append(x)
    i: int = len(self._data) - 1
    self._pos[x] = i
    self._siftUp(i)

  def pop(self) -> Element:
    if not self._data:
      raise IndexError("pop from empty heap")
    out: Element = self.top()
    self._eraseAt(0)
    return out

  def top(self) -> Element:
    if not self._data:
      raise IndexError("top from empty heap")
    return self._data[0]

  def remove(self, x: Element) -> None:
    if x not in self._pos:
      raise KeyError("remove")
    self._eraseAt(self._pos[x])

  def discard(self, x: Element) -> None:
    if x not in self._pos:
      return
    self._eraseAt(self._pos[x])

  def clear(self) -> None:
    self._data = []
    self._pos = {}

  @immutable
  def __contains__(self, x: Element) -> bool:
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
    b: Element = self._data.pop(j)
    a: Element = self._data.pop(i)
    self._data.insert(i, b)
    self._data.insert(j, a)
    self._pos[b] = i
    self._pos[a] = j

  def _eraseAt(self, i: int) -> None:
    del self._pos[self._data[i]]
    n: int = len(self._data)
    if i == n - 1:
      self._data.pop()
      return
    self._data[i] = self._data[n - 1]
    self._pos[self._data[i]] = i
    self._data.pop()
    if i > 0 and self._data[i] < self._data[Self._parent(i)]:
      self._siftUp(i)
    else:
      self._siftDown(i)

  def _siftUp(self, i: int) -> None:
    while i > 0:
      p: int = Self._parent(i)
      if self._data[p] <= self._data[i]:
        break
      self._swap(p, i)
      i = p

  def _siftDown(self, i: int) -> None:
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
