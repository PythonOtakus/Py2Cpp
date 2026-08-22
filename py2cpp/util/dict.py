"""``dict[Key, Value]`` / ``frozendict[Key, Value]``：链式哈希表，插入序与 Python 3.13 ``dict`` API 对齐。

``FrozenDictMixin`` 为二者共享核心；``DictEntryUnsafe`` 为共用桶节点。
键 ``Key`` 须满足 ``DictKeyType``。``dict`` 可变；``{}`` / ``dict()``。
``frozendict`` 不可变；空表 ``{}``；拷贝 ``new(dict|frozendict)``；``initFrom*``。
可变 ``dict`` 的迭代器 / view 对宿主做 ``copy()`` 快照；``frozendict`` 按值持有宿主。
内部 ``copy`` / ``update`` / ``__copy__`` 等按 ``_order`` 下标遍历；``class dict(friends=(frozendict, …))`` 要求本模块内 ``frozendict`` 已定义（见文件内声明顺序）。勿 ``for k in other``（会与 ``__iter__``→``copy`` 互递归栈溢出）。
"""
from ..builtins import *
from .list import list
from ..core.exceptions import KeyError, StopIteration, ValueError
from .mixins import ContainerMixin
from .protocols import DictKeyType


@boxing
class DictEntryUnsafe[Key: DictKeyType, Value]:
  def __init__(self, key: Key, value: Value, nextEntry: Self):
    self.key: Key = key
    self.value: Value = value
    self.next: Self = nextEntry


@mixin
class FrozenDictMixin[Key: DictKeyType, Value]:
  """映射共享核心（``dict`` / ``frozendict``）；宿主须声明 ``_capacity``、``_size``、``_order``、``_values``、``_buckets``。"""

  def __del__(self):
    self._clearEntries()

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    if self._size > 0:
      self._clearEntries()
    else:
      self._order.clear()
      self._values.clear()
      self._size = 0
    self._capacity = other._capacity
    self._buckets = new(self._capacity)
    for i in range(len(other._order)):
      k: Key = other._order[i]
      self._insertNew(k, other[k])

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    if self._size > 0:
      self._clearEntries()
    self._capacity = other._capacity
    self._size = other._size
    self._order = other._order
    self._values = other._values
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
    for i in range(len(self._order)):
      k: Key = self._order[i]
      if k not in other:
        return 1
      c = __cmp__(self[k], other[k])
      if c:
        return c
    return 0

  @immutable
  def __len__(self) -> int:
    self._ensureActive()
    return self._size

  @immutable
  def keyAt(self, index: int) -> Key:
    """插入序第 ``index`` 个键（O(1)；JSON 等热路径勿 ``for k in d`` 触发迭代器 ``copy()``）。"""
    self._ensureActive()
    return self._order[index]

  @immutable
  def valueAt(self, index: int) -> Value:
    """插入序第 ``index`` 个值（O(1)；与 ``_order`` 同步的 ``_values``）。"""
    self._ensureActive()
    return self._values[index]

  @immutable
  def __getitem__(self, key: Key) -> Value:
    self._ensureActive()
    node: DictEntryUnsafe[Key, Value] = self._findNode(key)
    if node is None:
      raise KeyError("key not found")
    return node.value

  @immutable
  def __contains__(self, key: Key) -> bool:
    return self._findNode(key) is not None

  @immutable
  def get(self, key: Key, default: Value @lazy = None) -> Value:
    if key in self:
      return self[key]
    if default is None:
      return None
    return default

  def _clearEntries(self):
    for b in range(self._capacity):
      cur: DictEntryUnsafe[Key, Value] = self._buckets[b]
      while cur is not None:
        nxt: DictEntryUnsafe[Key, Value] = cur.next
        self._freeEntry(cur)
        cur = nxt
      self._buckets[b] = None
    self._size = 0
    self._order.clear()
    self._values.clear()

  @immutable
  def _findNode(self, key: Key) -> DictEntryUnsafe[Key, Value]:
    idx: int = self._index(key)
    cur: DictEntryUnsafe[Key, Value] = self._buckets[idx]
    while cur is not None:
      if cur.key == key:
        return cur
      cur = cur.next
    return None

  def _freeEntry(self, node: DictEntryUnsafe[Key, Value]):
    destroy(node)
    free(node)

  @immutable
  def _index(self, key: Key) -> int:
    h: int = hash(key)
    if h < 0:
      h = -h
    return h % self._capacity

  def _insertNew(self, key: Key, value: Value) -> None:
    self._ensureActive()
    if self._findNode(key) is not None:
      return
    idx: int = self._index(key)
    entry = DictEntryUnsafe[Key, Value](key, value, self._buckets[idx])
    self._buckets[idx] = entry
    self._size += 1
    self._order.append(key)
    self._values.append(value)

  def _resetAfterMove(self):
    self._size = 0
    self._order = new()
    self._values = new()
    self._buckets = new(self._capacity)


@mixin
class FrozenDictKeyIteratorMixin[Key: DictKeyType, Value]:
  """插入序键迭代；宿主 ``__init__`` 须设 ``_dct``、``_index=0``。"""

  def __iter__(self):
    return self

  def __next__(self) -> Key:
    if self._index >= len(self._dct._order):
      raise StopIteration
    key: Key = self._dct._order[self._index]
    self._index += 1
    return key


@mixin
class FrozenDictKeyReverseIteratorMixin[Key: DictKeyType, Value]:
  """插入序反向键迭代；宿主 ``__init__`` 须设 ``_dct``、``_index=len(dct)-1``。"""

  def __iter__(self):
    return self

  def __next__(self) -> Key:
    if self._index < 0:
      raise StopIteration
    key: Key = self._dct._order[self._index]
    self._index -= 1
    return key


@mixin
class FrozenDictValuesIteratorMixin[Key: DictKeyType, Value]:
  """插入序值迭代；宿主 ``__init__`` 须设 ``_dct``、``_index=0``。"""

  def __iter__(self):
    return self

  def __next__(self) -> Value:
    if self._index >= len(self._dct._order):
      raise StopIteration
    key: Key = self._dct._order[self._index]
    self._index += 1
    return self._dct[key]


@mixin
class FrozenDictItemsIteratorMixin[Key: DictKeyType, Value]:
  """插入序项迭代；宿主 ``__init__`` 须设 ``_dct``、``_index=0``。"""

  def __iter__(self):
    return self

  def __next__(self) -> (Key, Value):
    if self._index >= len(self._dct._order):
      raise StopIteration
    key: Key = self._dct._order[self._index]
    self._index += 1
    return (key, self._dct[key])


@mixin
class FrozenDictKeysViewMixin[Key: DictKeyType, Value]:
  @immutable
  def __bool__(self) -> bool:
    return bool(self._dct)

  @immutable
  def __len__(self) -> int:
    return len(self._dct)


class FrozenDictKeyIterator[Key: DictKeyType, Value](FrozenDictKeyIteratorMixin[Key, Value]):
  _index: int = 0

  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct


class FrozenDictKeyReverseIterator[Key: DictKeyType, Value](FrozenDictKeyReverseIteratorMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct
    self._index: int = len(self._dct) - 1


class FrozenDictValuesIterator[Key: DictKeyType, Value](FrozenDictValuesIteratorMixin[Key, Value]):
  _index: int = 0

  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct


class FrozenDictItemsIterator[Key: DictKeyType, Value](FrozenDictItemsIteratorMixin[Key, Value]):
  _index: int = 0

  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct


class FrozenDictKeysView[Key: DictKeyType, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct

  def __iter__(self) -> FrozenDictKeyIterator[Key, Value]:
    return new(self._dct)

  def __reversed__(self) -> FrozenDictKeyReverseIterator[Key, Value]:
    return new(self._dct)


class FrozenDictValuesView[Key: DictKeyType, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct

  def __iter__(self) -> FrozenDictValuesIterator[Key, Value]:
    return new(self._dct)


class FrozenDictItemsView[Key: DictKeyType, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct

  def __iter__(self) -> FrozenDictItemsIterator[Key, Value]:
    return new(self._dct)


@native_name("PyFrozenDict")
class frozendict[Key: DictKeyType, Value](
  FrozenDictMixin[Key, Value],
  ContainerMixin,
  friends=(
    FrozenDictKeyIterator,
    FrozenDictKeyReverseIterator,
    FrozenDictValuesIterator,
    FrozenDictItemsIterator,
    FrozenDictKeysView,
    FrozenDictValuesView,
    FrozenDictItemsView,
  ),
):
  __repr__ = __str__
  _capacity: int = 8
  _size: int = 0

  def __init__(self):
    self._order: list[Key] = []
    self._values: list[Value] = []
    self._buckets: DictEntryUnsafe[Key, Value][:] = new(self._capacity)

  @immutable
  def __str__(self) -> str:
    if not self:
      return "frozendict()"
    out: str = "frozendict({"
    first: bool = True
    for k in self:
      if not first:
        out += ", "
      first = False
      out += repr(k) + ": " + repr(self[k])
    return out + "})"

  @immutable
  def __iter__(self) -> FrozenDictKeyIterator[Key, Value]:
    return new(self)

  @immutable
  def __reversed__(self) -> FrozenDictKeyReverseIterator[Key, Value]:
    return new(self)

  @property
  @immutable
  def capacity(self) -> int:
    return self._capacity

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = {}
    out.initFromFrozendict(self)
    return out

  @immutable
  def items(self) -> FrozenDictItemsView[Key, Value]:
    return new(self)

  @immutable
  def keys(self) -> FrozenDictKeysView[Key, Value]:
    return new(self)

  @immutable
  def values(self) -> FrozenDictValuesView[Key, Value]:
    return new(self)

  def initFromDict(self, other: dict[Key, Value]) -> None:
    self._clearEntries()
    for i in range(len(other._order)):
      k: Key = other._order[i]
      self._insertNew(k, other[k])

  def initFromFrozendict(self, other: Self) -> None:
    self._clearEntries()
    for i in range(len(other._order)):
      k: Key = other._order[i]
      self._insertNew(k, other[k])


class DictKeyIterator[Key: DictKeyType, Value](FrozenDictKeyIteratorMixin[Key, Value]):
  _index: int = 0

  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()


class DictKeyReverseIterator[Key: DictKeyType, Value](FrozenDictKeyReverseIteratorMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()
    self._index: int = len(self._dct) - 1


class DictValuesIterator[Key: DictKeyType, Value](FrozenDictValuesIteratorMixin[Key, Value]):
  _index: int = 0

  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()


class DictItemsIterator[Key: DictKeyType, Value](FrozenDictItemsIteratorMixin[Key, Value]):
  _index: int = 0

  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()


class DictKeysView[Key: DictKeyType, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()

  def __iter__(self) -> DictKeyIterator[Key, Value]:
    return new(self._dct)

  def __reversed__(self) -> DictKeyReverseIterator[Key, Value]:
    return new(self._dct)


class DictValuesView[Key: DictKeyType, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()

  def __iter__(self) -> DictValuesIterator[Key, Value]:
    return new(self._dct)


class DictItemsView[Key: DictKeyType, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()

  def __iter__(self) -> DictItemsIterator[Key, Value]:
    return new(self._dct)


class dict[Key: DictKeyType, Value](
  FrozenDictMixin[Key, Value],
  ContainerMixin,
  friends=(
    DictKeyIterator,
    DictKeyReverseIterator,
    DictValuesIterator,
    DictItemsIterator,
    DictKeysView,
    DictValuesView,
    DictItemsView,
    frozendict,
  ),
):
  __repr__ = __str__
  _capacity: int = 8
  _size: int = 0

  @staticmethod
  def fromKeys(keys: list[Key], value: Value) -> Self:
    d: Self = {}
    for k in keys:
      d[k] = value
    return d

  def __init__(self):
    self._order: list[Key] = []
    self._values: list[Value] = []
    self._buckets: DictEntryUnsafe[Key, Value][:] = new(self._capacity)

  def __copy__(self, other: Self):
    """深拷贝条目（避免默认成员拷贝共享 ``_buckets`` 链）。

    复制构造时 ``_buckets`` 尚未分配（C++ 为 ``nullptr``），不可调 ``_clearEntries``。
    """
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    if self._size > 0:
      self._clearEntries()
    else:
      self._order.clear()
      self._values.clear()
      self._size = 0
    self._capacity = other._capacity
    self._buckets = new(self._capacity)
    for i in range(len(other._order)):
      k: Key = other._order[i]
      self._insertNew(k, other[k])

  @immutable
  def __str__(self) -> str:
    if not self:
      return "{}"
    out: str = "{"
    first: bool = True
    for k in self:
      if not first:
        out += ", "
      first = False
      out += repr(k) + ": " + repr(self[k])
    return out + "}"

  @immutable
  def __format__(self, formatSpec: str) -> str:
    return str(self)

  def __setitem__(self, key: Key, value: Value):
    self._ensureActive()
    node: DictEntryUnsafe[Key, Value] = self._findNode(key)
    if node is not None:
      node.value = value
      n: int = len(self._order)
      for i in range(n):
        if self._order[i] == key:
          self._values[i] = value
          return
      return
    idx: int = self._index(key)
    entry = DictEntryUnsafe[Key, Value](key, value, self._buckets[idx])
    self._buckets[idx] = entry
    self._size += 1
    self._order.append(key)
    self._values.append(value)
    self._maybeGrow()

  def __delitem__(self, key: Key):
    self._popKey(key)

  @immutable
  def __iter__(self) -> DictKeyIterator[Key, Value]:
    return new(self)

  def __reversed__(self) -> DictKeyReverseIterator[Key, Value]:
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

  @immutable
  def __or__(self, other: Self) -> Self:
    out: Self = {}
    out.update(self)
    out.update(other)
    return out

  def __ior__(self, other: Self) -> Self:
    self.update(other)
    return self

  def clear(self):
    self._clearEntries()

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = {}
    out.update(self)
    return out

  @immutable
  def items(self) -> DictItemsView[Key, Value]:
    return new(self)

  @immutable
  def keys(self) -> DictKeysView[Key, Value]:
    return new(self)

  def pop(self, key: Key) -> Value:
    if key not in self:
      raise KeyError("pop")
    return self._popKey(key)

  def popItem(self) -> (Key, Value):
    if not self:
      raise KeyError("popItem")
    key: Key = self._order.pop()
    val: Value = self._values.pop()
    self._eraseKey(key)
    return (key, val)

  def setDefault(self, key: Key, default: Value) -> Value:
    if key in self:
      return self[key]
    self[key] = default
    return default

  @virtual
  def update(self, other: Self):
    for i in range(len(other._order)):
      k: Key = other._order[i]
      self[k] = other[k]

  @immutable
  def values(self) -> DictValuesView[Key, Value]:
    return new(self)

  def _eraseKey(self, key: Key):
    """从哈希链删除 ``key``（不修改 ``order``）。"""
    idx: int = self._index(key)
    prev: DictEntryUnsafe[Key, Value] = None
    cur: DictEntryUnsafe[Key, Value] = self._buckets[idx]
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

  def _orderRemove(self, key: Key):
    n: int = len(self._order)
    for i in range(n):
      if self._order[i] == key:
        if i < n - 1:
          self._order[i] = self._order[-1]
          self._values[i] = self._values[-1]
        self._order.pop()
        self._values.pop()
        return
    raise KeyError("key not in order")

  def _popKey(self, key: Key) -> Value:
    """从哈希表与 ``order`` 同步移除 ``key`` 并返回值。"""
    val: Value = self[key]
    self._eraseKey(key)
    self._orderRemove(key)
    return val

  def _rehash(self, newCap: int):
    scratchK: list[Key] = []
    for i in range(len(self._order)):
      scratchK.append(self._order[i])
    scratchV: list[Value] = []
    for i in range(len(self._order)):
      scratchV.append(self._values[i])
    self._clearEntries()
    self._capacity = newCap
    self._buckets = new(newCap)
    for i in range(len(scratchK)):
      self[scratchK[i]] = scratchV[i]
