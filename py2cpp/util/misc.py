"""``Counter``：对齐 Python 3.13 ``collections.Counter``（``dict`` 子类）。

文档：https://docs.python.org/3.13/library/collections.html#collections.Counter
参考：``Lib/collections/__init__.py`` 中 ``Counter``。

计数可为任意整数（含 0 与负数）；缺失键 ``__getitem__`` 返回 ``0`` 且不插入。
``update`` / ``subtract`` 为**加计数**（非 ``dict.update`` 的覆盖语义）。
"""
from ..builtins import *
from .dict import dict
from .list import list
from ..core.exceptions import KeyError, StopIteration, TypeError
from ..core.protocols import DictKey, Integral


@copyable
class Counter[K: DictKey, C: Integral = int](dict[K, C]):
  """多重集合计数器；继承 ``dict[K, C]`` 存储 ``key → count``。"""

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other)
    self.clear()
    for i in range(len(other)):
      k: K = other.key_at(i)
      self[k] = other.value_at(i)

  @overload
  def __init__(self):
    pass

  @overload
  def __init__(self, items: list[K]):
    for i in range(len(items)):
      self._inc(items[i], Self._one())

  @overload
  def __init__(self, mapping: dict[K, C]):
    self._update_mapping(mapping)

  @immutable
  def __getitem__(self, key: K) -> C:
    if key in self:
      return self.value_at(self._index_of_key(key))
    return Self._zero()

  @immutable
  def _index_of_key(self, key: K) -> int:
    for i in range(len(self)):
      if self.key_at(i) == key:
        return i
    raise KeyError("key not found")

  @immutable
  @staticmethod
  def _zero() -> C:
    z: int = 0
    return z

  @immutable
  @staticmethod
  def _one() -> C:
    o: int = 1
    return o

  @immutable
  @staticmethod
  def _neg(v: C) -> C:
    return Self._zero() - v

  def _inc(self, key: K, delta: C):
    self[key] += delta

  def _update_mapping(self, mapping: dict[K, C]):
    for i in range(len(mapping)):
      self._inc(mapping.key_at(i), mapping.value_at(i))

  @overload
  @override
  def update(self, other: Self):
    self._update_mapping(other)

  @overload
  @override
  def update(self, mapping: dict[K, C]):
    self._update_mapping(mapping)

  @overload
  @override
  def update(self, items: list[K]):
    for i in range(len(items)):
      self._inc(items[i], Self._one())

  @overload
  def subtract(self, other: Self):
    for i in range(len(other)):
      self._inc(other.key_at(i), Self._neg(other.value_at(i)))

  @overload
  def subtract(self, mapping: dict[K, C]):
    for i in range(len(mapping)):
      self._inc(mapping.key_at(i), Self._neg(mapping.value_at(i)))

  @overload
  def subtract(self, items: list[K]):
    for i in range(len(items)):
      self._inc(items[i], Self._neg(Self._one()))

  @immutable
  @override
  def copy(self) -> Self:
    out: Self = {}
    for i in range(len(self)):
      k: K = self.key_at(i)
      out[k] = self.value_at(i)
    return out

  @immutable
  def total(self) -> C:
    s: C = Self._zero()
    for i in range(len(self)):
      s += self.value_at(i)
    return s

  @immutable
  def elements(self) -> CounterElementsIterator[K, C]:
    return new(self)

  @immutable
  def most_common(self, n: int) -> list[tuple[K, C]]:
    keys: list[K] = []
    counts: list[C] = []
    for i in range(len(self)):
      keys.append(self.key_at(i))
      counts.append(self.value_at(i))
    np: int = len(keys)
    for i in range(np):
      best: int = i
      for j in range(i + 1, np):
        if counts[j] > counts[best]:
          best = j
      if best != i:
        tk: K = keys[i]
        keys[i] = keys[best]
        keys[best] = tk
        tc: C = counts[i]
        counts[i] = counts[best]
        counts[best] = tc
    limit: int = np
    if n < limit:
      limit = n
    if limit <= 0:
      empty: list[tuple[K, C]] = []
      return empty
    out: list[tuple[K, C]] = []
    for i in range(limit):
      row: (K, C) = (keys[i], counts[i])
      out.append(row)
    return out

  @staticmethod
  def fromkeys(keys: list[K], value: C) -> Self:
    raise TypeError("Counter.fromkeys() is not defined. Use Counter(iterable) instead.")

  @staticmethod
  def _from_mapping(m: dict[K, C]) -> Self:
    out: Self = {}
    out._update_mapping(m)
    return out

  @immutable
  def __add__(self, other: Self) -> Self:
    out: Self = self.copy()
    out.update(other)
    return out

  @immutable
  def __sub__(self, other: Self) -> Self:
    out: Self = self.copy()
    out.subtract(other)
    return out._drop_nonpositive()

  @immutable
  def __or__(self, other: Self) -> Self:
    m: dict[K, C] = {}
    for i in range(len(self)):
      k: K = self.key_at(i)
      va: C = self.value_at(i)
      vb: C = other[k]
      m[k] = va if va >= vb else vb
    for i in range(len(other)):
      k: K = other.key_at(i)
      if k not in m:
        m[k] = other.value_at(i)
    return Self._from_mapping(m)

  @immutable
  def __and__(self, other: Self) -> Self:
    m: dict[K, C] = {}
    for i in range(len(self)):
      k: K = self.key_at(i)
      if k in other:
        va: C = self.value_at(i)
        vb: C = other[k]
        cnt: C = va if va < vb else vb
        if cnt > 0:
          m[k] = cnt
    return Self._from_mapping(m)

  @immutable
  def __pos__(self) -> Self:
    return self._drop_nonpositive()

  @immutable
  def __neg__(self) -> Self:
    m: dict[K, C] = {}
    for i in range(len(self)):
      k: K = self.key_at(i)
      v: C = self.value_at(i)
      if v < 0:
        m[k] = Self._neg(v)
    return Self._from_mapping(m)

  @immutable
  def _drop_nonpositive(self) -> Self:
    m: dict[K, C] = {}
    for i in range(len(self)):
      k: K = self.key_at(i)
      v: C = self.value_at(i)
      if v > 0:
        m[k] = v
    return Self._from_mapping(m)

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in range(len(self)):
      k: K = self.key_at(i)
      if self.value_at(i) != other[k]:
        return False
    for i in range(len(other)):
      k: K = other.key_at(i)
      if other.value_at(i) != self[k]:
        return False
    return True


class CounterElementsIterator[K: DictKey, C: Integral]:
  """``Counter.elements()``：按插入序展开，``count <= 0`` 的键跳过。"""

  def __init__(self, ctr: Counter[K, C]):
    self._ctr: Counter[K, C] = ctr
    self._key_i: int = 0
    z: int = 0
    self._left: C = z
    self._cur: K = new()

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> K:
    z: int = 0
    o: int = 1
    zero: C = z
    one: C = o
    while self._key_i < len(self._ctr):
      if self._left <= zero:
        k: K = self._ctr.key_at(self._key_i)
        c: C = self._ctr.value_at(self._key_i)
        self._key_i += 1
        if c <= zero:
          continue
        self._cur = k
        self._left = c
      self._left -= one
      return self._cur
    raise StopIteration
