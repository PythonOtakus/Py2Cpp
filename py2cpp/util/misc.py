"""``Counter``：对齐 Python 3.13 ``collections.Counter``（``dict`` 子类）。

文档：https://docs.python.org/3.13/library/collections.html#collections.Counter
参考：``Lib/collections/__init__.py`` 中 ``Counter``。

计数可为任意整数（含 0 与负数）；缺失键 ``__getitem__`` 返回 ``0`` 且不插入。
``update`` / ``subtract`` 为**加计数**（非 ``dict.update`` 的覆盖语义）。
"""
from ..builtins import *
from .dict import dict
from .list import list
from ..core.exceptions import KeyError, StopIteration, TypeError, ValueError
from .protocols import DictKeyType
from ..numeric.protocols import IntegralType


@copyable
class Counter[Key: DictKeyType, Count: IntegralType = int](dict[Key, Count]):
  """多重集合计数器；继承 ``dict[K, C]`` 存储 ``key → count``。"""

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self.clear()
    for i in range(len(other)):
      k: Key = other.keyAt(i)
      self[k] = other.valueAt(i)

  @overload
  def __init__(self):
    pass

  @overload
  def __init__(self, items: list[Key]):
    for i in range(len(items)):
      self._inc(items[i], Self._one())

  @overload
  def __init__(self, mapping: dict[Key, Count]):
    self._updateMapping(mapping)

  @immutable
  def __getitem__(self, key: Key) -> Count:
    if key in self:
      return self.valueAt(self._indexOfKey(key))
    return Self._zero()

  @immutable
  def _indexOfKey(self, key: Key) -> int:
    for i in range(len(self)):
      if self.keyAt(i) == key:
        return i
    raise KeyError("key not found")

  @immutable
  @staticmethod
  def _zero() -> Count:
    z: int = 0
    return z

  @immutable
  @staticmethod
  def _one() -> Count:
    o: int = 1
    return o

  @immutable
  @staticmethod
  def _neg(v: Count) -> Count:
    return Self._zero() - v

  def _inc(self, key: Key, delta: Count):
    self[key] += delta

  def _updateMapping(self, mapping: dict[Key, Count]):
    for i in range(len(mapping)):
      self._inc(mapping.keyAt(i), mapping.valueAt(i))

  @overload
  @override
  def update(self, other: Self):
    self._updateMapping(other)

  @overload
  @override
  def update(self, mapping: dict[Key, Count]):
    self._updateMapping(mapping)

  @overload
  @override
  def update(self, items: list[Key]):
    for i in range(len(items)):
      self._inc(items[i], Self._one())

  @overload
  def subtract(self, other: Self):
    for i in range(len(other)):
      self._inc(other.keyAt(i), Self._neg(other.valueAt(i)))

  @overload
  def subtract(self, mapping: dict[Key, Count]):
    for i in range(len(mapping)):
      self._inc(mapping.keyAt(i), Self._neg(mapping.valueAt(i)))

  @overload
  def subtract(self, items: list[Key]):
    for i in range(len(items)):
      self._inc(items[i], Self._neg(Self._one()))

  @immutable
  @override
  def copy(self) -> Self:
    out: Self = {}
    for i in range(len(self)):
      k: Key = self.keyAt(i)
      out[k] = self.valueAt(i)
    return out

  @immutable
  def total(self) -> Count:
    s: Count = Self._zero()
    for i in range(len(self)):
      s += self.valueAt(i)
    return s

  @immutable
  def elements(self) -> CounterElementsIterator[Key, Count]:
    return new(self)

  @immutable
  def mostCommon(self, n: int) -> list[tuple[Key, Count]]:
    keys: list[Key] = []
    counts: list[Count] = []
    for i in range(len(self)):
      keys.append(self.keyAt(i))
      counts.append(self.valueAt(i))
    np: int = len(keys)
    for i in range(np):
      best: int = i
      for j in range(i + 1, np):
        if counts[j] > counts[best]:
          best = j
      if best != i:
        tk: Key = keys[i]
        keys[i] = keys[best]
        keys[best] = tk
        tc: Count = counts[i]
        counts[i] = counts[best]
        counts[best] = tc
    limit: int = np
    if n < limit:
      limit = n
    if limit <= 0:
      empty: list[tuple[Key, Count]] = []
      return empty
    out: list[tuple[Key, Count]] = []
    for i in range(limit):
      row: (Key, Count) = (keys[i], counts[i])
      out.append(row)
    return out

  @staticmethod
  def fromKeys(keys: list[Key], value: Count) -> Self:
    raise TypeError("Counter.fromKeys() is not defined. Use Counter(iterable) instead.")

  @staticmethod
  def _fromMapping(m: dict[Key, Count]) -> Self:
    out: Self = {}
    out._updateMapping(m)
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
    return out._dropNonpositive()

  @immutable
  def __or__(self, other: Self) -> Self:
    m: dict[Key, Count] = {}
    for i in range(len(self)):
      k: Key = self.keyAt(i)
      va: Count = self.valueAt(i)
      vb: Count = other[k]
      m[k] = va if va >= vb else vb
    for i in range(len(other)):
      k: Key = other.keyAt(i)
      if k not in m:
        m[k] = other.valueAt(i)
    return Self._fromMapping(m)

  @immutable
  def __and__(self, other: Self) -> Self:
    m: dict[Key, Count] = {}
    for i in range(len(self)):
      k: Key = self.keyAt(i)
      if k in other:
        va: Count = self.valueAt(i)
        vb: Count = other[k]
        cnt: Count = va if va < vb else vb
        if cnt > 0:
          m[k] = cnt
    return Self._fromMapping(m)

  @immutable
  def __pos__(self) -> Self:
    return self._dropNonpositive()

  @immutable
  def __neg__(self) -> Self:
    m: dict[Key, Count] = {}
    for i in range(len(self)):
      k: Key = self.keyAt(i)
      v: Count = self.valueAt(i)
      if v < 0:
        m[k] = Self._neg(v)
    return Self._fromMapping(m)

  @immutable
  def _dropNonpositive(self) -> Self:
    m: dict[Key, Count] = {}
    for i in range(len(self)):
      k: Key = self.keyAt(i)
      v: Count = self.valueAt(i)
      if v > 0:
        m[k] = v
    return Self._fromMapping(m)

  @immutable
  def __eq__(self, other: Self) -> bool:
    for i in range(len(self)):
      k: Key = self.keyAt(i)
      if self.valueAt(i) != other[k]:
        return False
    for i in range(len(other)):
      k: Key = other.keyAt(i)
      if other.valueAt(i) != self[k]:
        return False
    return True


class CounterElementsIterator[Key: DictKeyType, Count: IntegralType]:
  """``Counter.elements()``：按插入序展开，``count <= 0`` 的键跳过。"""

  def __init__(self, ctr: Counter[Key, Count]):
    self._ctr: Counter[Key, Count] = ctr
    self._keyI: int = 0
    z: int = 0
    self._left: Count = z
    self._cur: Key = new()

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> Key:
    z: int = 0
    o: int = 1
    zero: Count = z
    one: Count = o
    while self._keyI < len(self._ctr):
      if self._left <= zero:
        k: Key = self._ctr.keyAt(self._keyI)
        c: Count = self._ctr.valueAt(self._keyI)
        self._keyI += 1
        if c <= zero:
          continue
        self._cur = k
        self._left = c
      self._left -= one
      return self._cur
    raise StopIteration
