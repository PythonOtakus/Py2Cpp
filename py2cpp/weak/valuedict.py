"""弱值字典：键强持有、值 ``WeakRef``（对齐 ``weakref.WeakValueDictionary`` 子集）。"""
from ..builtins import *
from ..core.exceptions import KeyError
from ..util.protocols import DictKey
from .ref import WeakRef


@copyable
class WeakValueDict[K: DictKey, V: refcount]:
  """值无外部强引用时条目自动移除（访问时惰性清理）。"""

  _keys: list[K] = []

  _values: list[WeakRef[V]] = []

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
      if self._keys[i] == key:
        if self._values[i].alive:
          return True
    return False

  def __getitem__(self, key: K) -> V:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i] == key:
        if self._values[i].alive:
          return self._values[i].value
    raise KeyError("key not found")

  def __setitem__(self, key: K, value: V) -> None:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i] == key:
        self._values[i] = new(value)
        return
    self._keys.append(key)
    wv: WeakRef[V] = new(value)
    self._values.append(wv)

  def __delitem__(self, key: K) -> None:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i] == key:
        self._keys.pop(i)
        self._values.pop(i)
        return
    raise KeyError("key not found")

  def update(self, other: Self) -> None:
    other._compact()
    for i in range(len(other._keys)):
      if other._values[i].alive:
        self[other._keys[i]] = other._values[i].value

  def __repr__(self) -> str:
    self._compact()
    parts: list[str] = []
    for i in range(len(self._keys)):
      if self._values[i].alive:
        parts.append(
          format(self._keys[i], "") + ": " + format(self._values[i].value, "")
        )
    return "WeakValueDict({" + ", ".join(parts) + "})"

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
    key: K = self._keys.pop()
    wr: WeakRef[V] = self._values.pop()
    val: V = wr.value
    return (key, val)

  def keys(self) -> list[K]:
    self._compact()
    out: list[K] = []
    for i in range(len(self._keys)):
      if self._values[i].alive:
        out.append(self._keys[i])
    return out

  def values(self) -> list[V]:
    self._compact()
    out: list[V] = []
    for i in range(len(self._keys)):
      if self._values[i].alive:
        out.append(self._values[i].value)
    return out

  def items(self) -> list[tuple[K, V]]:
    self._compact()
    out: list[tuple[K, V]] = []
    for i in range(len(self._keys)):
      if self._values[i].alive:
        out.append((self._keys[i], self._values[i].value))
    return out

  def copy(self) -> Self:
    out: Self = new()
    out.update(self)
    return out

  def clear(self) -> None:
    self._keys.clear()
    self._values.clear()

  def valuerefs(self) -> list[WeakRef[V]]:
    self._compact()
    out: list[WeakRef[V]] = []
    for i in range(len(self._values)):
      if self._values[i].alive:
        out.append(self._values[i])
    return out

  def _compact(self) -> None:
    out_k: list[K] = []
    out_v: list[WeakRef[V]] = []
    for i in range(len(self._keys)):
      w: WeakRef[V] = self._values[i]
      if w.alive:
        out_k.append(self._keys[i])
        out_v.append(w)
    self._keys = out_k
    self._values = out_v
