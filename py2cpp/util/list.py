"""``list[Element]`` / ``frozenlist[Element]``：动态数组（可扩容 ``array``），语义对齐 Python 3.13 ``list``。

``FrozenListMixin`` 为二者共享核心。``list``：可变；``[]`` / ``list()``。
``frozenlist``：不可变；``frozenlist()``、``[…]``、``initFromList`` / ``initFromFrozenlist``。
"""
from ..builtins import *
from .array import array
from .span import span
from ..core.exceptions import IndexError, StopIteration, ValueError
from .mixins import ContainerMixin
from .slice import slice


@mixin
class FrozenListMixin[Element, StackLength: int = 0]:
  """序列共享核心（``list`` / ``frozenlist``）；宿主须声明 ``_length``、``_capacity``、``_data``。"""

  def __del__(self):
    self._clear()

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._clear()
    for i in range(len(other)):
      self._insertNew(other[i])

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._clear()
    self._length = other._length
    self._capacity = other._capacity
    self._data.__move__(other._data)
    other._length = 0
    other._capacity = 0

  @immutable
  def __bool__(self) -> bool:
    return self._length > 0

  @immutable
  def __eq__(self, other: Self) -> bool:
    n: int = len(self)
    m: int = len(other)
    if n != m:
      return False
    for i in range(n):
      if self[i] != other[i]:
        return False
    return True

  @immutable
  def __cmp__(self, other: Self) -> int:
    n: int = len(self)
    m: int = len(other)
    lim: int = n
    if m < lim:
      lim = m
    for i in range(lim):
      c: int = __cmp__(self[i], other[i])
      if c:
        return c
    return __cmp__(n, m)

  @immutable
  def __len__(self) -> int:
    self._ensureActive()
    return self._length

  @immutable
  @overload
  def __getitem__(self, index: int) -> Element:
    self._ensureActive()
    index = self._normIndex(index)
    if index < 0 or index >= self._length:
      raise IndexError("frozenlist index out of range")
    return self._data[index]

  @immutable
  @overload
  def __getitem__(self, index: slice[int, int]) -> Self:
    self._ensureActive()
    start: int
    stop: int
    step: int
    start, stop, step = index.indices(self._length)
    out: Self = []
    if step > 0:
      for i in range(start, stop, step):
        out._insertNew(self[i])
    else:
      for i in range(start, stop, step):
        out._insertNew(self[i])
    return out

  @immutable
  def __contains__(self, item: Element) -> bool:
    for i in range(self._length):
      if self[i] == item:
        return True
    return False

  @immutable
  def _allocatedSize(self, newSize: int) -> int:
    return (newSize + (newSize >> 3) + 6) & ~3

  def _clear(self) -> None:
    if self._data.view.at(0) is None and self._length == 0:
      return
    self._data.releaseBuffer(self._length)
    self._length = 0
    self._capacity = 0

  def _grow(self):
    need: int = self._length + 1
    if need < 1:
      need = 1
    newCap: int = self._allocatedSize(need)
    if newCap <= self._capacity:
      newCap = self._allocatedSize(self._capacity + 1)
    self._data.reshape(newCap, self._length)
    self._capacity = newCap

  def _insertNew(self, item: Element):
    if self._length >= self._capacity:
      self._grow()
    self._data.initSlot(self._length, item)
    self._length += 1

  def serdePushSlot(self) -> Pointer[Element]:
    """serde 热路径：预留尾槽（未 ``init``、未计入 ``_length``），返回槽位指针。"""
    self._ensureActive()
    if self._length >= self._capacity:
      self._grow()
    return self._data.view.at(self._length)

  def serdeCommitPush(self) -> None:
    """与 ``serdePushSlot`` 成对：槽位已 ``init`` 后提交。"""
    self._length += 1

  @immutable
  def _normIndex(self, index: int) -> int:
    if index < 0:
      index = self._length + index
    return index

  @immutable
  def _normStart(self, start: int) -> int:
    if start < 0:
      start = self._length + start
    if start < 0:
      start = 0
    return start

  @immutable
  def _normStop(self, end: int) -> int:
    if end == int.Max:
      return self._length
    if end < 0:
      end = self._length + end
    if end > self._length:
      end = self._length
    if end < 0:
      end = 0
    return end


@mixin
class FrozenListIteratorMixin[Element]:
  """正向序列迭代；宿主 ``__init__`` 须设 ``_owner``、``_index=0``。"""

  def __iter__(self):
    return self

  def __next__(self) -> Element:
    if self._index >= len(self._owner):
      raise StopIteration
    value: Element = self._owner[self._index]
    self._index += 1
    return value

  def copyFrom(self, other: Self):
    """``yield from`` 等场景重绑迭代器（MSVC 下避免未定义的复制赋值）。"""
    self._owner = other._owner
    self._index = other._index


@mixin
class FrozenListReverseIteratorMixin[Element]:
  """反向序列迭代；宿主 ``__init__`` 须设 ``_owner``、``_index=len(owner)-1``。"""

  def __iter__(self):
    return self

  def __next__(self) -> Element:
    if self._index < 0:
      raise StopIteration
    value: Element = self._owner[self._index]
    self._index -= 1
    return value

  def copyFrom(self, other: Self):
    self._owner = other._owner
    self._index = other._index


class ListIterator[Element](FrozenListIteratorMixin[Element]):
  _index: int = 0

  @overload
  def __init__(self):
    pass

  @overload
  def __init__(self, owner: list[Element]):
    self._owner: list[Element] = owner


class ListReverseIterator[Element](FrozenListReverseIteratorMixin[Element]):
  @overload
  def __init__(self):
    pass

  @overload
  def __init__(self, owner: list[Element]):
    self._owner: list[Element] = owner
    self._index: int = len(owner) - 1


class FrozenListIterator[Element](FrozenListIteratorMixin[Element]):
  _index: int = 0

  @overload
  def __init__(self):
    pass

  @overload
  def __init__(self, owner: frozenlist[Element]):
    self._owner: frozenlist[Element] = owner


class list[Element, StackLength: int = 0](
  FrozenListMixin[Element, StackLength],
  ContainerMixin,
  friends=(ListIterator, ListReverseIterator),
):
  __repr__ = __str__
  _length: int = 0
  _capacity: int = 0

  def __init__(self):
    self._data: array[Element, StackLength] = new()

  @immutable
  def __str__(self) -> str:
    n: int = self._length
    if n == 0:
      return "[]"
    out: str = "["
    for i in range(n):
      if i > 0:
        out += ", "
      out += repr(self[i])
    return out + "]"

  @immutable
  def __format__(self, formatSpec: str) -> str:
    return str(self)

  @immutable
  @overload
  def __getitem__(self, index: int) -> Element:
    self._ensureActive()
    index = self._normIndex(index)
    if index < 0 or index >= self._length:
      raise IndexError("list index out of range")
    return self._data[index]

  @immutable
  @overload
  def __getitem__(self, index: slice[int, int]) -> Self:
    self._ensureActive()
    start: int
    stop: int
    step: int
    start, stop, step = index.indices(self._length)
    out: Self = []
    for i in range(start, stop, step):
      out.append(self[i])
    return out

  def __setitem__(self, index: int, value: Element):
    index = self._normIndex(index)
    if index < 0 or index >= self._length:
      raise IndexError("list assignment index out of range")
    self._data[index] = value

  @overload
  def __delitem__(self, index: int):
    index = self._normIndex(index)
    if index < 0 or index >= self._length:
      raise IndexError("list assignment index out of range")
    self.pop(index)

  @overload
  def __delitem__(self, index: slice[int, int]):
    self._delSlice(index)

  @immutable
  def __iter__(self) -> ListIterator[Element]:
    return new(self)

  def __reversed__(self) -> ListReverseIterator[Element]:
    return new(self)

  @property
  @immutable
  def capacity(self) -> int:
    return self._capacity

  @property.setter
  def capacity(self, value: int):
    self._reserve(value)

  @property
  @immutable
  def view(self) -> span[Element]:
    self._ensureActive()
    return new(self._data.view.at(0), self._length, 1)

  @immutable
  def __add__(self, other: Self) -> Self:
    out: Self = []
    out.extend(self)
    out.extend(other)
    return out

  def __iadd__(self, other: Self) -> Self:
    self.extend(other)
    return self

  @immutable
  def __mul__(self, n: int) -> Self:
    if n <= 0:
      return []
    out: Self = []
    for _ in range(n):
      out.extend(self)
    return out

  @immutable
  def __rmul__(self, n: int) -> Self:
    if n <= 0:
      return []
    out: Self = []
    for _ in range(n):
      out.extend(self)
    return out

  def __imul__(self, n: int) -> Self:
    if n <= 0:
      self.clear()
      return self
    if n == 1:
      return self
    snap: Self = self.copy()
    for _ in range(1, n):
      self.extend(snap)
    return self

  def append(self, item: Element):
    self._ensureActive()
    self._insertNew(item)

  def clear(self):
    self._clear()

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = []
    out.extend(self)
    return out

  @immutable
  def count(self, value: Element) -> int:
    n: int = 0
    for i in range(self._length):
      if self[i] == value:
        n += 1
    return n

  def extend(self, other: Self):
    for i in range(other._length):
      self.append(other[i])

  @immutable
  def index(self, value: Element, start: int = 0, end: int = int.Max) -> int:
    start = self._normStart(start)
    stop: int = self._normStop(end)
    for i in range(start, stop):
      if self[i] == value:
        return i
    raise ValueError("list.index(x): x not in list")

  def insert(self, index: int, item: Element):
    if index < 0:
      index = self._length + index
    if index < 0:
      index = 0
    if index > self._length:
      index = self._length
    if index == self._length:
      self.append(item)
      return
    if self._length >= self._capacity:
      self._grow()
    for j in range(self._length - 1, index - 1, -1):
      if j + 1 >= self._length:
        self._data.initSlot(j + 1, self._data[j])
      else:
        self._data[j + 1] = self._data[j]
    self._data.destroySlot(index)
    self._data.initSlot(index, item)
    self._length += 1

  def pop(self, index: int = -1) -> Element:
    if self._length == 0:
      raise IndexError("pop from empty list")
    index = self._normIndex(index)
    if index < 0 or index >= self._length:
      raise IndexError("pop index out of range")
    value: Element = self[index]
    for j in range(index, self._length - 1):
      self._data[j] = self._data[j + 1]
    self._data.destroySlot(self._length - 1)
    self._length -= 1
    return value

  def remove(self, value: Element):
    for i in range(self._length):
      if self[i] == value:
        self.pop(i)
        return
    raise ValueError("list.remove(x): x not in list")

  def reverse(self):
    lo: int = 0
    hi: int = self._length - 1
    while lo < hi:
      self._swap(lo, hi)
      lo += 1
      hi -= 1

  def sort(self, key: Function[[Element], int] = None, reverse: bool = False):
    """稳定原地 Timsort（CPython ``listsort``：自然 run + minrun + 归并）；``key`` 为 ``None`` 时按元素值。"""
    n: int = self._length
    if n < 2:
      return
    minrun: int = self._timComputeMinrun(n)
    scratch: Self = []
    i: int = 0
    while i < n:
      run: int = self._timCountRun(i, n, key, reverse)
      if run > 1 and self._sortLess(i + 1, i, key, reverse):
        self._timReverseRange(i, i + run)
      if run < minrun:
        end: int = i + minrun
        if end > n:
          end = n
        self._timBinaryInsertionSort(i, end, key, reverse)
        i = end
      else:
        i += run
    size: int = minrun
    while size < n:
      start: int = 0
      while start < n:
        mid: int = start + size
        end: int = start + size + size
        if mid > n:
          mid = n
        if end > n:
          end = n
        if mid < end:
          self._timMerge(start, mid, end, key, reverse, scratch)
        start = end
      size += size

  def _delSlice(self, sl: slice[int, int]):
    start: int
    stop: int
    step: int
    start, stop, step = sl.indices(self._length)
    if step == 1:
      n: int = stop - start
      if n <= 0:
        return
      for i in range(start, self._length - n):
        self._data[i] = self._data[i + n]
      for _ in range(n):
        self._data.destroySlot(self._length - 1)
        self._length -= 1
      return
    kept: Self = []
    for i in range(self._length):
      if not self._sliceHasIndex(i, start, stop, step):
        kept.append(self[i])
    self._clear()
    self.extend(kept)

  def _reserve(self, capacity: int):
    """预分配容量；按 CPython 规则取分配大小，不改变 length。"""
    if capacity > self._capacity:
      newCap: int = self._allocatedSize(capacity)
      if newCap < capacity:
        newCap = capacity
      self._data.reshape(newCap, self._length)
      self._capacity = newCap

  def setCapacity(self, capacity: int):
    """``@serializable`` 等解码路径预分配 list 容量（不改变 ``len``）。"""
    self._reserve(capacity)

  @immutable
  def _sliceHasIndex(self, i: int, start: int, stop: int, step: int) -> bool:
    if step > 0:
      if i < start or i >= stop:
        return False
      return ((i - start) % step) == 0
    if i > start or i <= stop:
      return False
    return ((start - i) % (-step)) == 0

  @immutable
  def _sortLess(self, ia: int, ib: int, key: Function[[Element], int], reverse: bool) -> bool:
    """``True`` 表示 ``ia`` 应在 ``ib`` 之前；``key`` 为 ``None`` 时按元素值比较。"""
    return self._sortLessElems(self[ia], self[ib], key, reverse)

  @immutable
  def _sortLessElems(self, va: Element, vb: Element, key: Function[[Element], int], reverse: bool) -> bool:
    if key is not None:
      ka: int = key(va)
      kb: int = key(vb)
      if reverse:
        return ka > kb
      return ka < kb
    if reverse:
      return va > vb
    return va < vb

  def _swap(self, i: int, j: int):
    self._data[i], self._data[j] = self._data[j], self._data[i]

  def _timBinaryInsertionSort(self, lo: int, hi: int, key: Function[[Element], int], reverse: bool):
    for i in range(lo + 1, hi):
      loIdx: int = lo
      hiIdx: int = i
      while loIdx < hiIdx:
        mid: int = (loIdx + hiIdx) // 2
        if self._sortLess(i, mid, key, reverse):
          hiIdx = mid
        else:
          loIdx = mid + 1
      val: Element = self[i]
      for j in range(i, loIdx, -1):
        self._data[j] = self._data[j - 1]
      self._data[loIdx] = val

  @immutable
  def _timComputeMinrun(self, n: int) -> int:
    """CPython ``listsort`` 的 minrun（``merge_compute_minrun``）。"""
    r: int = 0
    while n >= 64:
      r |= n & 1
      n //= 2
    return n + r

  @immutable
  def _timCountRun(self, start: int, n: int, key: Function[[Element], int], reverse: bool) -> int:
    if start >= n - 1:
      return 1
    end: int = start + 1
    if self._sortLess(end, start, key, reverse):
      while end < n and self._sortLess(end, end - 1, key, reverse):
        end += 1
    else:
      while end < n and not self._sortLess(end, end - 1, key, reverse):
        end += 1
    return end - start

  def _timMerge(self, lo: int, mid: int, hi: int, key: Function[[Element], int], reverse: bool, tmp: Self @ref):
    tmp.clear()
    for k in range(lo, mid):
      tmp.append(self[k])
    li: int = 0
    leftLen: int = mid - lo
    j: int = mid
    k: int = lo
    while li < leftLen and j < hi:
      if self._sortLessElems(tmp[li], self[j], key, reverse):
        self._data[k] = tmp[li]
        li += 1
      else:
        self._data[k] = self[j]
        j += 1
      k += 1
    for t in range(li, leftLen):
      self._data[k] = tmp[t]
      k += 1

  def _timReverseRange(self, lo: int, hi: int):
    hi -= 1
    while lo < hi:
      self._swap(lo, hi)
      lo += 1
      hi -= 1


@native_name("PyFrozenList")
class frozenlist[Element, StackLength: int = 0](
  FrozenListMixin[Element, StackLength],
  ContainerMixin,
  friends=(FrozenListIterator,),
):
  __repr__ = __str__
  _length: int = 0
  _capacity: int = 0

  def __init__(self):
    self._data: array[Element, StackLength] = new()

  @immutable
  def __str__(self) -> str:
    n: int = self._length
    if n == 0:
      return "frozenlist()"
    out: str = "frozenlist(["
    for i in range(n):
      if i > 0:
        out += ", "
      out += repr(self[i])
    return out + "])"

  @immutable
  def __iter__(self) -> FrozenListIterator[Element]:
    return new(self)

  @immutable
  def count(self, value: Element) -> int:
    n: int = 0
    for i in range(self._length):
      if self[i] == value:
        n += 1
    return n

  @immutable
  def index(self, value: Element, start: int = 0, end: int = int.Max) -> int:
    start = self._normStart(start)
    stop: int = self._normStop(end)
    for i in range(start, stop):
      if self[i] == value:
        return i
    raise ValueError("frozenlist.index(x): x not in frozenlist")

  def initFromList(self, other: list[Element]) -> None:
    for i in range(len(other)):
      self._insertNew(other[i])

  def initFromFrozenlist(self, other: Self) -> None:
    for i in range(len(other)):
      self._insertNew(other[i])

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = []
    out.initFromFrozenlist(self)
    return out
