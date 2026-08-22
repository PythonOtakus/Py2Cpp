"""``set[T]`` / ``frozenset[T]``：无序哈希集合（CPython 3.13 子集）。

``FrozenSetMixin`` 为二者共享核心；``FrozenSetEntryUnsafe`` 为共用桶节点。
仅支持正向 ``__iter__``（桶链顺序，非插入序），**无** ``__reversed__``。
``set``：可变；空 ``set()`` / 非空 ``{…}``（勿用 ``{}``，那是 ``dict``）。
``frozenset``：不可变；``frozenset()``、``{…}``、``frozenset(iterable)``。
"""
from ..builtins import *
from .list import list
from ..core.exceptions import KeyError, StopIteration, ValueError
from .mixins import ContainerMixin
from .protocols import DictKeyType


@boxing
class FrozenSetEntryUnsafe[Element: DictKeyType]:
  def __init__(self, key: Element, nextEntry: Self):
    self.key: Element = key
    self.next: Self = nextEntry


@mixin
class FrozenSetMixin[Element: DictKeyType]:
  """无序哈希集合核心；宿主须声明 ``_capacity``、``_size``、``_buckets`` 并在 ``__init__`` 中初始化。"""

  def __del__(self):
    self._clearEntries()

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    if self._size > 0:
      self._clearEntries()
    else:
      self._size = 0
    self._capacity = other._capacity
    self._buckets = new(self._capacity)
    for b in range(other._capacity):
      cur: FrozenSetEntryUnsafe[Element] = other._buckets[b]
      while cur is not None:
        self._insertNew(cur.key)
        cur = cur.next

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    if self._size > 0:
      self._clearEntries()
    self._capacity = other._capacity
    self._size = other._size
    self._buckets = other._buckets
    other._resetAfterMove()

  @immutable
  def __bool__(self) -> bool:
    return self._size > 0

  @immutable
  def __cmp__(self, other: Self) -> int:
    c: int = __cmp__(len(self), len(other))
    if c:
      return c
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if cur.key not in other:
          return 1
        cur = cur.next
    return 0

  @immutable
  def __len__(self) -> int:
    self._ensureActive()
    return self._size

  @immutable
  def __contains__(self, key: Element) -> bool:
    return self._findNode(key) is not None

  @immutable
  def __sub__(self, other: Self) -> Self:
    out: Self = new()
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if cur.key not in other:
          out._insertNew(cur.key)
        cur = cur.next
    return out

  @immutable
  def __and__(self, other: Self) -> Self:
    out: Self = new()
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if cur.key in other:
          out._insertNew(cur.key)
        cur = cur.next
    return out

  @immutable
  def __or__(self, other: Self) -> Self:
    out: Self = new()
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        out._insertNew(cur.key)
        cur = cur.next
    for b in range(other._capacity):
      cur: FrozenSetEntryUnsafe[Element] = other._buckets[b]
      while cur is not None:
        out._insertNew(cur.key)
        cur = cur.next
    return out

  @immutable
  def __xor__(self, other: Self) -> Self:
    out: Self = new()
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if cur.key not in other:
          out._insertNew(cur.key)
        cur = cur.next
    for b in range(other._capacity):
      cur: FrozenSetEntryUnsafe[Element] = other._buckets[b]
      while cur is not None:
        if cur.key not in self:
          out._insertNew(cur.key)
        cur = cur.next
    return out

  @immutable
  def isSubset(self, other: Self) -> bool:
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if cur.key not in other:
          return False
        cur = cur.next
    return True

  @immutable
  def isSuperset(self, other: Self) -> bool:
    return other.isSubset(self)

  @immutable
  def isDisjoint(self, other: Self) -> bool:
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if cur.key in other:
          return False
        cur = cur.next
    return True

  def _clearEntries(self):
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        nxt: FrozenSetEntryUnsafe[Element] = cur.next
        self._freeEntry(cur)
        cur = nxt
      self._buckets[b] = None
    self._size = 0

  @immutable
  def _findNode(self, key: Element) -> FrozenSetEntryUnsafe[Element]:
    idx: int = self._index(key)
    cur: FrozenSetEntryUnsafe[Element] = self._buckets[idx]
    while cur is not None:
      if cur.key == key:
        return cur
      cur = cur.next
    return None

  def _freeEntry(self, node: FrozenSetEntryUnsafe[Element]):
    destroy(node)
    free(node)

  @immutable
  def _index(self, key: Element) -> int:
    h: int = key
    if h < 0:
      h = -h
    return h % self._capacity

  def _insertNew(self, key: Element) -> None:
    self._ensureActive()
    if self._findNode(key) is not None:
      return
    idx: int = self._index(key)
    entry = FrozenSetEntryUnsafe[Element](key, self._buckets[idx])
    self._buckets[idx] = entry
    self._size += 1

  def _resetAfterMove(self):
    self._size = 0
    self._buckets = new(self._capacity)


@mixin
class FrozenSetIteratorMixin[Element: DictKeyType]:
  """桶链正向迭代；宿主 ``__init__`` 须设 ``_owner``、``_bucket=0``、``_skip=0``。"""

  def __iter__(self):
    return self

  def __next__(self) -> Element:
    for b in range(self._bucket, self._owner._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._owner._buckets[b]
      n: int = 0
      while cur:
        if n >= self._skip:
          key: Element = cur.key
          self._bucket = b
          self._skip += 1
          return key
        n += 1
        cur = cur.next
      self._skip = 0
      self._bucket = b + 1
    raise StopIteration


class SetReverseIterator[Element: DictKeyType]:
  """类型名占位；``set`` 无 ``__reversed__``，供 ``new(SetReverseIterator[T])`` 等派发。"""

  pass


class SetIterator[Element: DictKeyType](FrozenSetIteratorMixin[Element]):
  _bucket: int = 0
  _skip: int = 0

  def __init__(self, owner: set[Element]):
    self._owner: set[Element] = owner


class set[Element: DictKeyType](
  FrozenSetMixin[Element],
  ContainerMixin,
  friends=(SetIterator,),
):
  __repr__ = __str__
  _capacity: int = 8
  _size: int = 0

  def __init__(self):
    self._buckets: FrozenSetEntryUnsafe[Element][:] = new(self._capacity)

  @immutable
  def __str__(self) -> str:
    if not self:
      return "set()"
    out: str = "{"
    first: bool = True
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if not first:
          out += ", "
        first = False
        out += repr(cur.key)
        cur = cur.next
    return out + "}"

  @immutable
  def __iter__(self) -> SetIterator[Element]:
    return new(self)

  @property
  @immutable
  def capacity(self) -> int:
    return self._capacity

  @property.setter
  def capacity(self, value: int):
    if value < 8:
      value = 8
    if value <= self._capacity:
      return
    if self._size == 0:
      self._capacity = value
      self._buckets = new(value)
      return
    self._rehash(value)

  def __isub__(self, other: Self) -> Self:
    scratch: list[Element] = []
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if cur.key in other:
          scratch.append(cur.key)
        cur = cur.next
    for i in range(len(scratch)):
      self.remove(scratch[i])
    return self

  def __iand__(self, other: Self) -> Self:
    scratch: list[Element] = []
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if cur.key not in other:
          scratch.append(cur.key)
        cur = cur.next
    for i in range(len(scratch)):
      self.remove(scratch[i])
    return self

  def __ior__(self, other: Self) -> Self:
    self.update(other)
    return self

  def __ixor__(self, other: Self) -> Self:
    for b in range(other._capacity):
      cur: FrozenSetEntryUnsafe[Element] = other._buckets[b]
      while cur is not None:
        if cur.key in self:
          self.remove(cur.key)
        else:
          self.add(cur.key)
        cur = cur.next
    return self

  def add(self, key: Element) -> None:
    self._ensureActive()
    if self._findNode(key) is not None:
      return
    idx: int = self._index(key)
    entry = FrozenSetEntryUnsafe[Element](key, self._buckets[idx])
    self._buckets[idx] = entry
    self._size += 1
    self._maybeGrow()

  def clear(self) -> None:
    self._clearEntries()

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = new()
    out.update(self)
    return out

  def discard(self, key: Element) -> None:
    if key not in self:
      return
    self._eraseKey(key)

  def pop(self) -> Element:
    if self._size == 0:
      raise KeyError("pop")
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      if cur is not None:
        key: Element = cur.key
        self._eraseKey(key)
        return key
    raise KeyError("pop")

  def remove(self, key: Element) -> None:
    if key not in self:
      raise KeyError("remove")
    self._eraseKey(key)

  def update(self, other: Self) -> None:
    for b in range(other._capacity):
      cur: FrozenSetEntryUnsafe[Element] = other._buckets[b]
      while cur is not None:
        self.add(cur.key)
        cur = cur.next

  def _eraseKey(self, key: Element):
    idx: int = self._index(key)
    prev: FrozenSetEntryUnsafe[Element] = None
    cur: FrozenSetEntryUnsafe[Element] = self._buckets[idx]
    while cur is not None:
      if cur.key == key:
        if prev is None:
          self._buckets[idx] = cur.next
        else:
          prev.next = cur.next
        self._freeEntry(cur)
        self._size -= 1
        return
      prev = cur
      cur = cur.next
    raise KeyError("key not found")

  @immutable
  def _loadLimit(self) -> int:
    return (self._capacity * 2) // 3 + 1

  def _maybeGrow(self):
    if self._size < self._loadLimit():
      return
    newCap: int = self._capacity * 2
    if newCap < 8:
      newCap = 8
    self._rehash(newCap)

  def _rehash(self, newCap: int):
    scratch: list[Element] = []
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        scratch.append(cur.key)
        cur = cur.next
    self._clearEntries()
    self._capacity = newCap
    self._buckets = new(newCap)
    for i in range(len(scratch)):
      self.add(scratch[i])


class FrozenSetIterator[Element: DictKeyType](FrozenSetIteratorMixin[Element]):
  _bucket: int = 0
  _skip: int = 0

  def __init__(self, fs: frozenset[Element]):
    self._owner: frozenset[Element] = fs


@native_name("PyFrozenSet")
class frozenset[Element: DictKeyType](
  FrozenSetMixin[Element],
  ContainerMixin,
  friends=(FrozenSetIterator,),
):
  __repr__ = __str__
  _capacity: int = 8
  _size: int = 0

  def __init__(self):
    self._buckets: FrozenSetEntryUnsafe[Element][:] = new(self._capacity)

  @immutable
  def __str__(self) -> str:
    if not self:
      return "frozenset()"
    out: str = "frozenset({"
    first: bool = True
    for b in range(self._capacity):
      cur: FrozenSetEntryUnsafe[Element] = self._buckets[b]
      while cur is not None:
        if not first:
          out += ", "
        first = False
        out += repr(cur.key)
        cur = cur.next
    return out + "})"

  @immutable
  def __iter__(self) -> FrozenSetIterator[Element]:
    return new(self)

  @property
  @immutable
  def capacity(self) -> int:
    return self._capacity

  def initFromSet(self, other: set[Element]) -> None:
    for key in other:
      self._insertNew(key)

  def initFromFrozenset(self, other: Self) -> None:
    for key in other:
      self._insertNew(key)

  def initFromList(self, items: list[Element]) -> None:
    for i in range(len(items)):
      self._insertNew(items[i])
