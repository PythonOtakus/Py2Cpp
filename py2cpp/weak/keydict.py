"""弱键字典：键 ``WeakRef``、值强持有（对齐 ``weakref.WeakKeyDictionary`` 子集）。"""
from ..builtins import *
from ..core.exceptions import KeyError
from ..util.protocols import DictKey
from .ref import WeakRef


@copyable
class WeakKeyDict[K: DictKey & refcount, V]:
  """键无外部强引用时条目自动移除（访问时惰性清理）。"""

  _keys: list[WeakRef[K]] = []

  _values: list[V] = []

  def __del__(self):
    self.clear()

  def __len__(self) -> int:
    self._compact()
    return len(self._keys)

  def __bool__(self) -> bool:
    self._compact()
    return len(self._keys) > 0

  def __contains__(self, key: K) -> bool:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i].alive:
        k: K = self._keys[i].value
        if k is key:
          return True
    return False

  def __getitem__(self, key: K) -> V:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i].alive:
        k: K = self._keys[i].value
        if k is key:
          return self._values[i]
    raise KeyError("key not found")

  def __setitem__(self, key: K, value: V) -> None:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i].alive:
        k: K = self._keys[i].value
        if k is key:
          self._values[i] = value
          return
    wk: WeakRef[K] = new(key)
    self._keys.append(wk)
    self._values.append(value)

  def __delitem__(self, key: K) -> None:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i].alive:
        k: K = self._keys[i].value
        if k is key:
          self._keys.pop(i)
          self._values.pop(i)
          return
    raise KeyError("key not found")

  def update(self, other: Self) -> None:
    other._compact()
    for i in range(len(other._keys)):
      if other._keys[i].alive:
        self[other._keys[i].value] = other._values[i]

  def __repr__(self) -> str:
    self._compact()
    parts: list[str] = []
    for i in range(len(self._keys)):
      if self._keys[i].alive:
        parts.append(
          format(self._keys[i].value, "") + ": " + format(self._values[i], "")
        )
    return "WeakKeyDict({" + ", ".join(parts) + "})"

  def get(self, key: K, default: V) -> V:
    if key in self:
      return self[key]
    return default

  def setdefault(self, key: K, default: V) -> V:
    if key in self:
      return self[key]
    self[key] = default
    return default

  def pop(self, key: K) -> V:
    if key not in self:
      raise KeyError("pop")
    val: V = self[key]
    del self[key]
    return val

  def popitem(self) -> (K, V):
    self._compact()
    if not self._keys:
      raise KeyError("popitem(): dictionary is empty")
    wk: WeakRef[K] = self._keys.pop()
    val: V = self._values.pop()
    key: K = wk.value
    return (key, val)

  def keys(self) -> list[K]:
    self._compact()
    out: list[K] = []
    for i in range(len(self._keys)):
      if self._keys[i].alive:
        out.append(self._keys[i].value)
    return out

  def values(self) -> list[V]:
    self._compact()
    out: list[V] = []
    for i in range(len(self._keys)):
      if self._keys[i].alive:
        out.append(self._values[i])
    return out

  def items(self) -> list[tuple[K, V]]:
    self._compact()
    out: list[tuple[K, V]] = []
    for i in range(len(self._keys)):
      if self._keys[i].alive:
        out.append((self._keys[i].value, self._values[i]))
    return out

  def copy(self) -> Self:
    out: Self = new()
    out.update(self)
    return out

  def clear(self) -> None:
    self._keys.clear()
    self._values.clear()

  def keyrefs(self) -> list[WeakRef[K]]:
    self._compact()
    out: list[WeakRef[K]] = []
    for i in range(len(self._keys)):
      if self._keys[i].alive:
        out.append(self._keys[i])
    return out

  def _compact(self) -> None:
    out_k: list[WeakRef[K]] = []
    out_v: list[V] = []
    for i in range(len(self._keys)):
      w: WeakRef[K] = self._keys[i]
      if w.alive:
        out_k.append(w)
        out_v.append(self._values[i])
    self._keys = out_k
    self._values = out_v
