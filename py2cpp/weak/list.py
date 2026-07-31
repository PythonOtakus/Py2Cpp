"""弱引用有序列表（Py2Cpp 扩展，API 风格对齐 ``WeakSet``）。"""
from ..builtins import *
from ..core.exceptions import IndexError
from .ref import WeakRef


@copyable
class WeakList[T: refcount]:
  """``__getitem__(i)`` 按第 i 个**存活**元素计；死引用在访问时剔除。"""

  _refs: list[WeakRef[T]] = []

  def __del__(self):
    self.clear()

  def __len__(self) -> int:
    self._compact()
    return len(self._refs)

  def __bool__(self) -> bool:
    self._compact()
    return len(self._refs) > 0

  def __contains__(self, obj: T) -> bool:
    self._compact()
    for w in self._refs:
      if w.alive and w.value is obj:
        return True
    return False

  def append(self, obj: T) -> None:
    self._refs.append(WeakRef[T](obj))

  def __getitem__(self, index: int) -> T:
    self._compact()
    if index < 0 or index >= len(self._refs):
      raise IndexError("weak list index out of range")
    if not self._refs[index].alive:
      raise IndexError("weak list element expired")
    return self._refs[index].value

  def copy(self) -> Self:
    out: Self = new()
    self._compact()
    for i in range(len(self._refs)):
      if self._refs[i].alive:
        out.append(self._refs[i].value)
    return out

  def extend(self, other: Self) -> None:
    other._compact()
    for i in range(len(other._refs)):
      if other._refs[i].alive:
        self.append(other._refs[i].value)

  def __repr__(self) -> str:
    self._compact()
    parts: list[str] = []
    for i in range(len(self._refs)):
      if self._refs[i].alive:
        parts.append(format(self._refs[i].value, ""))
    return "WeakList([" + ", ".join(parts) + "])"

  def discard(self, obj: T) -> None:
    self._compact()
    out: list[WeakRef[T]] = []
    for w in self._refs:
      if not (w.alive and w.value is obj):
        out.append(w)
    self._refs = out

  def remove(self, obj: T) -> None:
    if obj not in self:
      raise IndexError("weak list element not found")
    self.discard(obj)

  def pop(self, index: int = -1) -> T:
    self._compact()
    if not self._refs:
      raise IndexError("pop from empty WeakList")
    if index < 0:
      index += len(self._refs)
    if index < 0 or index >= len(self._refs):
      raise IndexError("weak list pop index out of range")
    w: WeakRef[T] = self._refs.pop(index)
    if not w.alive:
      return self.pop(index)
    return w.value

  def clear(self) -> None:
    self._refs.clear()

  def _compact(self) -> None:
    out: list[WeakRef[T]] = []
    for w in self._refs:
      if w.alive:
        out.append(w)
    self._refs = out
