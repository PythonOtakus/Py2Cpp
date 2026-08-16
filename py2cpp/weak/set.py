"""弱引用集合（对齐 ``weakref.WeakSet`` 子集）。"""
from ..builtins import *
from ..core.exceptions import KeyError
from ..util.protocols import DictKeyType
from .ref import WeakRef


@copyable
class WeakSet[Element: DictKeyType & refcount]:
  """元素无外部强引用时自动移除（访问时惰性清理）。"""

  _refs: list[WeakRef[Element]] = []

  def __del__(self):
    self.clear()

  def __len__(self) -> int:
    self._compact()
    return len(self._refs)

  def __bool__(self) -> bool:
    self._compact()
    return len(self._refs) > 0

  def __contains__(self, obj: Element) -> bool:
    self._compact()
    for w in self._refs:
      if w.alive and w.value is obj:
        return True
    return False

  def add(self, obj: Element) -> None:
    self._compact()
    if obj in self:
      return
    self._refs.append(WeakRef[Element](obj))

  def discard(self, obj: Element) -> None:
    self._compact()
    out: list[WeakRef[Element]] = []
    for w in self._refs:
      if not (w.alive and w.value is obj):
        out.append(w)
    self._refs = out

  def remove(self, obj: Element) -> None:
    if obj not in self:
      raise KeyError("element not in weak set")
    self.discard(obj)

  def pop(self) -> Element:
    self._compact()
    if not self._refs:
      raise KeyError("pop from empty WeakSet")
    w: WeakRef[Element] = self._refs.pop()
    if not w.alive:
      return self.pop()
    return w.value

  def clear(self) -> None:
    self._refs.clear()

  def copy(self) -> Self:
    out: Self = new()
    self._compact()
    for i in range(len(self._refs)):
      if self._refs[i].alive:
        out.add(self._refs[i].value)
    return out

  def __repr__(self) -> str:
    self._compact()
    parts: list[str] = []
    for i in range(len(self._refs)):
      if self._refs[i].alive:
        parts.append(format(self._refs[i].value, ""))
    return "WeakSet({" + ", ".join(parts) + "})"

  def isDisjoint(self, other: Self) -> bool:
    self._compact()
    for i in range(len(self._refs)):
      if self._refs[i].alive:
        if self._refs[i].value in other:
          return False
    return True

  def isSubset(self, other: Self) -> bool:
    self._compact()
    for i in range(len(self._refs)):
      if self._refs[i].alive:
        if self._refs[i].value not in other:
          return False
    return True

  def isSuperset(self, other: Self) -> bool:
    return other.isSubset(self)

  def __or__(self, other: Self) -> Self:
    out: Self = self.copy()
    other._compact()
    for i in range(len(other._refs)):
      if other._refs[i].alive:
        out.add(other._refs[i].value)
    return out

  def __ior__(self, other: Self) -> Self:
    other._compact()
    for i in range(len(other._refs)):
      if other._refs[i].alive:
        self.add(other._refs[i].value)
    return self

  def _compact(self) -> None:
    out: list[WeakRef[Element]] = []
    for w in self._refs:
      if w.alive:
        out.append(w)
    self._refs = out
