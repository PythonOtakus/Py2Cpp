"""``set[T]`` / ``frozenset[T]``：无序哈希集合（CPython 3.13 子集）。

``FrozenSetMixin`` 为二者共享核心；``frozenset_entry`` 为共用桶节点。
仅支持正向 ``__iter__``（桶链顺序，非插入序），**无** ``__reversed__``。
``set``：可变；空 ``set()`` / 非空 ``{…}``（勿用 ``{}``，那是 ``dict``）。
``frozenset``：不可变；``frozenset()``、``{…}``、``frozenset(iterable)``。
"""
from ..builtins import *
from .list import list
from ..core.exceptions import KeyError, StopIteration, ValueError
from .mixins import ContainerMixin
from .protocols import DictKey


@boxing
@native_name("PyFrozenSetEntry")
class frozenset_entry[T: DictKey]:
  def __init__(self, key: T, next_entry: Self):
    self.key: T = key
    self.next: Self = next_entry


@mixin
class FrozenSetMixin[T: DictKey]:
  """无序哈希集合核心；宿主须声明 ``_capacity``、``_size``、``_buckets`` 并在 ``__init__`` 中初始化。"""

  def __del__(self):
    self._clear_entries()

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    if self._size > 0:
      self._clear_entries()
    else:
      self._size = 0
    self._capacity = other._capacity
    self._buckets = new(self._capacity)
    for b in range(other._capacity):
      cur: frozenset_entry[T] = other._buckets[b]
      while cur is not None:
        self._insert_new(cur.key)
        cur = cur.next

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    if self._size > 0:
      self._clear_entries()
    self._capacity = other._capacity
    self._size = other._size
    self._buckets = other._buckets
    other._reset_after_move()

  @immutable
  def __bool__(self) -> bool:
    return self._size > 0

  @immutable
  def __cmp__(self, other: Self) -> int:
    c: int = __cmp__(len(self), len(other))
    if c:
      return c
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        if cur.key not in other:
          return 1
        cur = cur.next
    return 0

  @immutable
  def __len__(self) -> int:
    self._ensure_active()
    return self._size

  @immutable
  def __contains__(self, key: T) -> bool:
    return self._find_node(key) is not None

  @immutable
  def __sub__(self, other: Self) -> Self:
    out: Self = new()
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        if cur.key not in other:
          out._insert_new(cur.key)
        cur = cur.next
    return out

  @immutable
  def __and__(self, other: Self) -> Self:
    out: Self = new()
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        if cur.key in other:
          out._insert_new(cur.key)
        cur = cur.next
    return out

  @immutable
  def __or__(self, other: Self) -> Self:
    out: Self = new()
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        out._insert_new(cur.key)
        cur = cur.next
    for b in range(other._capacity):
      cur: frozenset_entry[T] = other._buckets[b]
      while cur is not None:
        out._insert_new(cur.key)
        cur = cur.next
    return out

  @immutable
  def __xor__(self, other: Self) -> Self:
    out: Self = new()
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        if cur.key not in other:
          out._insert_new(cur.key)
        cur = cur.next
    for b in range(other._capacity):
      cur: frozenset_entry[T] = other._buckets[b]
      while cur is not None:
        if cur.key not in self:
          out._insert_new(cur.key)
        cur = cur.next
    return out

  @immutable
  def issubset(self, other: Self) -> bool:
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        if cur.key not in other:
          return False
        cur = cur.next
    return True

  @immutable
  def issuperset(self, other: Self) -> bool:
    return other.issubset(self)

  @immutable
  def isdisjoint(self, other: Self) -> bool:
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        if cur.key in other:
          return False
        cur = cur.next
    return True

  def _clear_entries(self):
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        nxt: frozenset_entry[T] = cur.next
        self._free_entry(cur)
        cur = nxt
      self._buckets[b] = None
    self._size = 0

  @immutable
  def _find_node(self, key: T) -> frozenset_entry[T]:
    idx: int = self._index(key)
    cur: frozenset_entry[T] = self._buckets[idx]
    while cur is not None:
      if cur.key == key:
        return cur
      cur = cur.next
    return None

  def _free_entry(self, node: frozenset_entry[T]):
    destroy(node)
    free(node)

  @immutable
  def _index(self, key: T) -> int:
    h: int = key
    if h < 0:
      h = -h
    return h % self._capacity

  def _insert_new(self, key: T) -> None:
    self._ensure_active()
    if self._find_node(key) is not None:
      return
    idx: int = self._index(key)
    entry = frozenset_entry[T](key, self._buckets[idx])
    self._buckets[idx] = entry
    self._size += 1

  def _reset_after_move(self):
    self._size = 0
    self._buckets = new(self._capacity)


@mixin
class FrozenSetIteratorMixin[T: DictKey]:
  """桶链正向迭代；宿主 ``__init__`` 须设 ``_owner``、``_bucket=0``、``_skip=0``。"""

  def __iter__(self):
    return self

  def __next__(self) -> T:
    for b in range(self._bucket, self._owner._capacity):
      cur: frozenset_entry[T] = self._owner._buckets[b]
      n: int = 0
      while cur:
        if n >= self._skip:
          key: T = cur.key
          self._bucket = b
          self._skip += 1
          return key
        n += 1
        cur = cur.next
      self._skip = 0
      self._bucket = b + 1
    raise StopIteration


@native_name("PySetReverseIterator")
class set_reverse_iterator[T: DictKey]:
  """类型名占位；``set`` 无 ``__reversed__``，供 ``new(set_reverse_iterator[T])`` 等派发。"""

  pass


@native_name("PySetIterator")
class set_iterator[T: DictKey](FrozenSetIteratorMixin[T]):
  def __init__(self, owner: set[T]):
    self._owner: set[T] = owner
    self._bucket: int = 0
    self._skip: int = 0


@native_name("PySet")
class set[T: DictKey](
  FrozenSetMixin[T],
  ContainerMixin,
  friends=(set_iterator,),
):
  __repr__ = __str__

  def __init__(self):
    self._capacity: int = 8
    self._size: int = 0
    self._buckets: frozenset_entry[T][:] = new(self._capacity)

  @immutable
  def __str__(self) -> str:
    if not self:
      return "set()"
    out: str = "{"
    first: bool = True
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        if not first:
          out += ", "
        first = False
        out += repr(cur.key)
        cur = cur.next
    return out + "}"

  @immutable
  def __iter__(self) -> set_iterator[T]:
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
    scratch: list[T] = []
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        if cur.key in other:
          scratch.append(cur.key)
        cur = cur.next
    for i in range(len(scratch)):
      self.remove(scratch[i])
    return self

  def __iand__(self, other: Self) -> Self:
    scratch: list[T] = []
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
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
      cur: frozenset_entry[T] = other._buckets[b]
      while cur is not None:
        if cur.key in self:
          self.remove(cur.key)
        else:
          self.add(cur.key)
        cur = cur.next
    return self

  def add(self, key: T) -> None:
    self._ensure_active()
    if self._find_node(key) is not None:
      return
    idx: int = self._index(key)
    entry = frozenset_entry[T](key, self._buckets[idx])
    self._buckets[idx] = entry
    self._size += 1
    self._maybe_grow()

  def clear(self) -> None:
    self._clear_entries()

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new()
    out.update(self)
    return out

  def discard(self, key: T) -> None:
    if key not in self:
      return
    self._erase_key(key)

  def pop(self) -> T:
    if self._size == 0:
      raise KeyError("pop")
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      if cur is not None:
        key: T = cur.key
        self._erase_key(key)
        return key
    raise KeyError("pop")

  def remove(self, key: T) -> None:
    if key not in self:
      raise KeyError("remove")
    self._erase_key(key)

  def update(self, other: Self) -> None:
    for b in range(other._capacity):
      cur: frozenset_entry[T] = other._buckets[b]
      while cur is not None:
        self.add(cur.key)
        cur = cur.next

  def _erase_key(self, key: T):
    idx: int = self._index(key)
    prev: frozenset_entry[T] = None
    cur: frozenset_entry[T] = self._buckets[idx]
    while cur is not None:
      if cur.key == key:
        if prev is None:
          self._buckets[idx] = cur.next
        else:
          prev.next = cur.next
        self._free_entry(cur)
        self._size -= 1
        return
      prev = cur
      cur = cur.next
    raise KeyError("key not found")

  @immutable
  def _load_limit(self) -> int:
    return (self._capacity * 2) // 3 + 1

  def _maybe_grow(self):
    if self._size < self._load_limit():
      return
    new_cap: int = self._capacity * 2
    if new_cap < 8:
      new_cap = 8
    self._rehash(new_cap)

  def _rehash(self, new_cap: int):
    scratch: list[T] = []
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        scratch.append(cur.key)
        cur = cur.next
    self._clear_entries()
    self._capacity = new_cap
    self._buckets = new(new_cap)
    for i in range(len(scratch)):
      self.add(scratch[i])


@native_name("PyFrozenSetIterator")
class frozenset_iterator[T: DictKey](FrozenSetIteratorMixin[T]):
  def __init__(self, fs: frozenset[T]):
    self._owner: frozenset[T] = fs
    self._bucket: int = 0
    self._skip: int = 0


@native_name("PyFrozenSet")
class frozenset[T: DictKey](
  FrozenSetMixin[T],
  ContainerMixin,
  friends=(frozenset_iterator,),
):
  __repr__ = __str__

  def __init__(self):
    self._capacity: int = 8
    self._size: int = 0
    self._buckets: frozenset_entry[T][:] = new(self._capacity)

  @immutable
  def __str__(self) -> str:
    if not self:
      return "frozenset()"
    out: str = "frozenset({"
    first: bool = True
    for b in range(self._capacity):
      cur: frozenset_entry[T] = self._buckets[b]
      while cur is not None:
        if not first:
          out += ", "
        first = False
        out += repr(cur.key)
        cur = cur.next
    return out + "})"

  @immutable
  def __iter__(self) -> frozenset_iterator[T]:
    return new(self)

  @property
  @immutable
  def capacity(self) -> int:
    return self._capacity

  def init_from_set(self, other: set[T]) -> None:
    for key in other:
      self._insert_new(key)

  def init_from_frozenset(self, other: Self) -> None:
    for key in other:
      self._insert_new(key)

  def init_from_list(self, items: list[T]) -> None:
    for i in range(len(items)):
      self._insert_new(items[i])
