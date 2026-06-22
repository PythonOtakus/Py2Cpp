"""``dict[Key, Value]`` / ``frozendict[Key, Value]``：链式哈希表，插入序与 Python 3.13 ``dict`` API 对齐。

``FrozenDictMixin`` 为二者共享核心；``dict_entry`` 为共用桶节点。
键 ``Key`` 须满足 ``DictKey``。``dict`` 可变；``{}`` / ``dict()``。
``frozendict`` 不可变；空表 ``{}``；拷贝 ``new(dict|frozendict)``；``init_from_*``。
可变 ``dict`` 的迭代器 / view 对宿主做 ``copy()`` 快照；``frozendict`` 按值持有宿主。
内部 ``copy`` / ``update`` / ``__copy__`` 等按 ``_order`` 下标遍历；``class dict(friends=(frozendict, …))`` 要求本模块内 ``frozendict`` 已定义（见文件内声明顺序）。勿 ``for k in other``（会与 ``__iter__``→``copy`` 互递归栈溢出）。
"""
from ..builtins import *
from .list import list
from ..core.exceptions import KeyError, StopIteration, ValueError
from ..core.protocols import DictKey


@boxing
@native_name("PyDictEntry")
class dict_entry[Key: DictKey, Value]:
  def __init__(self, key: Key, value: Value, next_entry: Self):
    self.key: Key = key
    self.value: Value = value
    self.next: Self = next_entry


@mixin
class FrozenDictMixin[Key: DictKey, Value]:
  """映射共享核心（``dict`` / ``frozendict``）；宿主须声明 ``_capacity``、``_size``、``_order``、``_values``、``buckets``。"""

  def __del__(self):
    self._clear_entries()

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    if self._size > 0:
      self._clear_entries()
    else:
      self._order.clear()
      self._values.clear()
      self._size = 0
    self._capacity = other._capacity
    self.buckets = new(self._capacity)
    for i in range(len(other._order)):
      k: Key = other._order[i]
      self._insert_new(k, other[k])

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    if self._size > 0:
      self._clear_entries()
    self._capacity = other._capacity
    self._size = other._size
    self._order = other._order
    self._values = other._values
    self.buckets = other.buckets
    other._reset_after_move()

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
    self._ensure_active()
    return self._size

  @immutable
  def key_at(self, index: int) -> Key:
    """插入序第 ``index`` 个键（O(1)；JSON 等热路径勿 ``for k in d`` 触发迭代器 ``copy()``）。"""
    self._ensure_active()
    return self._order[index]

  @immutable
  def value_at(self, index: int) -> Value:
    """插入序第 ``index`` 个值（O(1)；与 ``_order`` 同步的 ``_values``）。"""
    self._ensure_active()
    return self._values[index]

  @immutable
  def __getitem__(self, key: Key) -> Value:
    self._ensure_active()
    node: dict_entry[Key, Value] = self._find_node(key)
    if node is None:
      raise KeyError("key not found")
    return node.value

  @immutable
  def __contains__(self, key: Key) -> bool:
    return self._find_node(key) is not None

  @immutable
  def get(self, key: Key, default: Value @lazy = None) -> Value:
    if key in self:
      return self[key]
    if default is None:
      return None
    return default

  def _clear_entries(self):
    for b in range(self._capacity):
      cur: dict_entry[Key, Value] = self.buckets[b]
      while cur is not None:
        nxt: dict_entry[Key, Value] = cur.next
        self._free_entry(cur)
        cur = nxt
      self.buckets[b] = None
    self._size = 0
    self._order.clear()
    self._values.clear()

  @immutable
  def _ensure_active(self) -> None:
    if self.__moved__:
      raise ValueError("frozendict used after move")

  @immutable
  def _ensure_other_active(self, other: Self) -> None:
    if other.__moved__:
      raise ValueError("move from moved frozendict")

  @immutable
  def _find_node(self, key: Key) -> dict_entry[Key, Value]:
    idx: int = self._index(key)
    cur: dict_entry[Key, Value] = self.buckets[idx]
    while cur is not None:
      if cur.key == key:
        return cur
      cur = cur.next
    return None

  def _free_entry(self, node: dict_entry[Key, Value]):
    destroy(node)
    free(node)

  @immutable
  def _index(self, key: Key) -> int:
    h: int = hash(key)
    if h < 0:
      h = -h
    return h % self._capacity

  def _insert_new(self, key: Key, value: Value) -> None:
    self._ensure_active()
    if self._find_node(key) is not None:
      return
    idx: int = self._index(key)
    entry = dict_entry[Key, Value](key, value, self.buckets[idx])
    self.buckets[idx] = entry
    self._size += 1
    self._order.append(key)
    self._values.append(value)

  def _reset_after_move(self):
    self._size = 0
    self._order = new()
    self._values = new()
    self.buckets = new(self._capacity)


@mixin
class FrozenDictKeyIteratorMixin[Key: DictKey, Value]:
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
class FrozenDictKeyReverseIteratorMixin[Key: DictKey, Value]:
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
class FrozenDictValuesIteratorMixin[Key: DictKey, Value]:
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
class FrozenDictItemsIteratorMixin[Key: DictKey, Value]:
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
class FrozenDictKeysViewMixin[Key: DictKey, Value]:
  @immutable
  def __bool__(self) -> bool:
    return bool(self._dct)

  @immutable
  def __len__(self) -> int:
    return len(self._dct)


@native_name("PyFrozenDictKeyIterator")
class frozendict_key_iterator[Key: DictKey, Value](FrozenDictKeyIteratorMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct
    self._index: int = 0


@native_name("PyFrozenDictKeyReverseIterator")
class frozendict_key_reverse_iterator[Key: DictKey, Value](FrozenDictKeyReverseIteratorMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct
    self._index: int = len(self._dct) - 1


@native_name("PyFrozenDictValuesIterator")
class frozendict_values_iterator[Key: DictKey, Value](FrozenDictValuesIteratorMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct
    self._index: int = 0


@native_name("PyFrozenDictItemsIterator")
class frozendict_items_iterator[Key: DictKey, Value](FrozenDictItemsIteratorMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct
    self._index: int = 0


@native_name("PyFrozenDictKeysView")
class frozendict_keys_view[Key: DictKey, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct

  def __iter__(self) -> frozendict_key_iterator[Key, Value]:
    return new(self._dct)

  def __reversed__(self) -> frozendict_key_reverse_iterator[Key, Value]:
    return new(self._dct)


@native_name("PyFrozenDictValuesView")
class frozendict_values_view[Key: DictKey, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct

  def __iter__(self) -> frozendict_values_iterator[Key, Value]:
    return new(self._dct)


@native_name("PyFrozenDictItemsView")
class frozendict_items_view[Key: DictKey, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: frozendict[Key, Value]):
    self._dct: frozendict[Key, Value] = dct

  def __iter__(self) -> frozendict_items_iterator[Key, Value]:
    return new(self._dct)


@native_name("PyFrozenDict")
class frozendict[Key: DictKey, Value](
  FrozenDictMixin[Key, Value],
  friends=(
    frozendict_key_iterator,
    frozendict_key_reverse_iterator,
    frozendict_values_iterator,
    frozendict_items_iterator,
    frozendict_keys_view,
    frozendict_values_view,
    frozendict_items_view,
  ),
):
  __repr__ = __str__

  def __init__(self):
    self._capacity: int = 8
    self._size: int = 0
    self._order: list[Key] = []
    self._values: list[Value] = []
    self.buckets: dict_entry[Key, Value][:] = new(self._capacity)

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
  def __iter__(self) -> frozendict_key_iterator[Key, Value]:
    return new(self)

  @immutable
  def __reversed__(self) -> frozendict_key_reverse_iterator[Key, Value]:
    return new(self)

  @property
  @immutable
  def capacity(self) -> int:
    return self._capacity

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = {}
    out.init_from_frozendict(self)
    return out

  @immutable
  def items(self) -> frozendict_items_view[Key, Value]:
    return new(self)

  @immutable
  def keys(self) -> frozendict_keys_view[Key, Value]:
    return new(self)

  @immutable
  def values(self) -> frozendict_values_view[Key, Value]:
    return new(self)

  def init_from_dict(self, other: dict[Key, Value]) -> None:
    self._clear_entries()
    for i in range(len(other._order)):
      k: Key = other._order[i]
      self._insert_new(k, other[k])

  def init_from_frozendict(self, other: Self) -> None:
    self._clear_entries()
    for i in range(len(other._order)):
      k: Key = other._order[i]
      self._insert_new(k, other[k])


@native_name("PyDictKeyIterator")
class dict_key_iterator[Key: DictKey, Value](FrozenDictKeyIteratorMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()
    self._index: int = 0


@native_name("PyDictKeyReverseIterator")
class dict_key_reverse_iterator[Key: DictKey, Value](FrozenDictKeyReverseIteratorMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()
    self._index: int = len(self._dct) - 1


@native_name("PyDictValuesIterator")
class dict_values_iterator[Key: DictKey, Value](FrozenDictValuesIteratorMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()
    self._index: int = 0


@native_name("PyDictItemsIterator")
class dict_items_iterator[Key: DictKey, Value](FrozenDictItemsIteratorMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()
    self._index: int = 0


@native_name("PyDictKeysView")
class dict_keys_view[Key: DictKey, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()

  def __iter__(self) -> dict_key_iterator[Key, Value]:
    return new(self._dct)

  def __reversed__(self) -> dict_key_reverse_iterator[Key, Value]:
    return new(self._dct)


@native_name("PyDictValuesView")
class dict_values_view[Key: DictKey, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()

  def __iter__(self) -> dict_values_iterator[Key, Value]:
    return new(self._dct)


@native_name("PyDictItemsView")
class dict_items_view[Key: DictKey, Value](FrozenDictKeysViewMixin[Key, Value]):
  def __init__(self, dct: dict[Key, Value]):
    self._dct: dict[Key, Value] = dct.copy()

  def __iter__(self) -> dict_items_iterator[Key, Value]:
    return new(self._dct)


@native_name("PyDict")
class dict[Key: DictKey, Value](
  FrozenDictMixin[Key, Value],
  friends=(
    dict_key_iterator,
    dict_key_reverse_iterator,
    dict_values_iterator,
    dict_items_iterator,
    dict_keys_view,
    dict_values_view,
    dict_items_view,
    frozendict,
  ),
):
  __repr__ = __str__

  @staticmethod
  def fromkeys(keys: list[Key], value: Value) -> Self:
    d: Self = {}
    for k in keys:
      d[k] = value
    return d

  def __init__(self):
    self._capacity: int = 8
    self._size: int = 0
    self._order: list[Key] = []
    self._values: list[Value] = []
    self.buckets: dict_entry[Key, Value][:] = new(self._capacity)

  def __copy__(self, other: Self):
    """深拷贝条目（避免默认成员拷贝共享 ``buckets`` 链）。

    复制构造时 ``buckets`` 尚未分配（C++ 为 ``nullptr``），不可调 ``_clear_entries``。
    """
    self._ensure_active()
    self._ensure_other_active(other)
    if self._size > 0:
      self._clear_entries()
    else:
      self._order.clear()
      self._values.clear()
      self._size = 0
    self._capacity = other._capacity
    self.buckets = new(self._capacity)
    for i in range(len(other._order)):
      k: Key = other._order[i]
      self._insert_new(k, other[k])

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
  def __format__(self, format_spec: str) -> str:
    return str(self)

  def __setitem__(self, key: Key, value: Value):
    self._ensure_active()
    node: dict_entry[Key, Value] = self._find_node(key)
    if node is not None:
      node.value = value
      n: int = len(self._order)
      for i in range(n):
        if self._order[i] == key:
          self._values[i] = value
          return
      return
    idx: int = self._index(key)
    entry = dict_entry[Key, Value](key, value, self.buckets[idx])
    self.buckets[idx] = entry
    self._size += 1
    self._order.append(key)
    self._values.append(value)
    self._maybe_grow()

  def __delitem__(self, key: Key):
    self._pop_key(key)

  @immutable
  def __iter__(self) -> dict_key_iterator[Key, Value]:
    return new(self)

  def __reversed__(self) -> dict_key_reverse_iterator[Key, Value]:
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
      self.buckets = new(value)
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
    self._clear_entries()

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = {}
    out.update(self)
    return out

  @immutable
  def items(self) -> dict_items_view[Key, Value]:
    return new(self)

  @immutable
  def keys(self) -> dict_keys_view[Key, Value]:
    return new(self)

  def pop(self, key: Key) -> Value:
    if key not in self:
      raise KeyError("pop")
    return self._pop_key(key)

  def popitem(self) -> (Key, Value):
    if not self:
      raise KeyError("popitem")
    key: Key = self._order.pop()
    val: Value = self._values.pop()
    self._erase_key(key)
    return (key, val)

  def setdefault(self, key: Key, default: Value) -> Value:
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
  def values(self) -> dict_values_view[Key, Value]:
    return new(self)

  @immutable
  def _ensure_active(self) -> None:
    if self.__moved__:
      raise ValueError("dict used after move")

  @immutable
  def _ensure_other_active(self, other: Self) -> None:
    if other.__moved__:
      raise ValueError("move from moved dict")

  def _erase_key(self, key: Key):
    """从哈希链删除 ``key``（不修改 ``order``）。"""
    idx: int = self._index(key)
    prev: dict_entry[Key, Value] = None
    cur: dict_entry[Key, Value] = self.buckets[idx]
    while cur is not None:
      if cur.key == key:
        if prev is None:
          self.buckets[idx] = cur.next
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

  def _order_remove(self, key: Key):
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

  def _pop_key(self, key: Key) -> Value:
    """从哈希表与 ``order`` 同步移除 ``key`` 并返回值。"""
    val: Value = self[key]
    self._erase_key(key)
    self._order_remove(key)
    return val

  def _rehash(self, new_cap: int):
    scratch_k: list[Key] = []
    for i in range(len(self._order)):
      scratch_k.append(self._order[i])
    scratch_v: list[Value] = []
    for i in range(len(self._order)):
      scratch_v.append(self._values[i])
    self._clear_entries()
    self._capacity = new_cap
    self.buckets = new(new_cap)
    for i in range(len(scratch_k)):
      self[scratch_k[i]] = scratch_v[i]
