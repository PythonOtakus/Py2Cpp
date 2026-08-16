"""弱值字典：键强持有、值 ``WeakRef``（对齐 ``weakref.WeakValueDictionary`` 子集）。"""
from ..builtins import *
from ..core.exceptions import KeyError
from ..util.protocols import DictKeyType
from .ref import WeakRef


@copyable
class WeakValueDict[Key: DictKeyType, Value: refcount]:
  """值无外部强引用时条目自动移除（访问时惰性清理）。"""

  _keys: list[Key] = []

  _values: list[WeakRef[Value]] = []

  def __del__(self):
    self.clear()

  def __len__(self) -> int:
    self._compact()
    return len(self._keys)

  def __bool__(self) -> bool:
    self._compact()
    return len(self._keys) > 0

  def __contains__(self, key: Key) -> bool:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i] == key:
        if self._values[i].alive:
          return True
    return False

  def __getitem__(self, key: Key) -> Value:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i] == key:
        if self._values[i].alive:
          return self._values[i].value
    raise KeyError("key not found")

  def __setitem__(self, key: Key, value: Value) -> None:
    self._compact()
    for i in range(len(self._keys)):
      if self._keys[i] == key:
        self._values[i] = new(value)
        return
    self._keys.append(key)
    self._values.append(WeakRef[Value](value))

  def __delitem__(self, key: Key) -> None:
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

  def get(self, key: Key, default: Value) -> Value:
    if key in self:
      return self[key]
    return default

  def setDefault(self, key: Key, default: Value) -> Value:
    if key in self:
      return self[key]
    self[key] = default
    return default

  def pop(self, key: Key) -> Value:
    if key not in self:
      raise KeyError("pop")
    val: Value = self[key]
    del self[key]
    return val

  def popItem(self) -> (Key, Value):
    self._compact()
    if not self._keys:
      raise KeyError("popItem(): dictionary is empty")
    key: Key = self._keys.pop()
    wr: WeakRef[Value] = self._values.pop()
    val: Value = wr.value
    return (key, val)

  def keys(self) -> list[Key]:
    self._compact()
    out: list[Key] = []
    for i in range(len(self._keys)):
      if self._values[i].alive:
        out.append(self._keys[i])
    return out

  def values(self) -> list[Value]:
    self._compact()
    out: list[Value] = []
    for i in range(len(self._keys)):
      if self._values[i].alive:
        out.append(self._values[i].value)
    return out

  def items(self) -> list[tuple[Key, Value]]:
    self._compact()
    out: list[tuple[Key, Value]] = []
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

  def valuerefs(self) -> list[WeakRef[Value]]:
    self._compact()
    out: list[WeakRef[Value]] = []
    for i in range(len(self._values)):
      if self._values[i].alive:
        out.append(self._values[i])
    return out

  def _compact(self) -> None:
    outK: list[Key] = []
    outV: list[WeakRef[Value]] = []
    for i in range(len(self._keys)):
      w: WeakRef[Value] = self._values[i]
      if w.alive:
        outK.append(self._keys[i])
        outV.append(w)
    self._keys = outK
    self._values = outV
