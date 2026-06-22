"""单调队列（滑动窗口最值）。

公开 API：

| 方法 | 说明 |
|------|------|
| ``push(x)`` | 窗口右端入队 |
| ``pop()`` | 窗口左端滑出 |
| ``min()`` / ``max()`` | 当前窗口极值（构造时 ``is_min`` 指定其一） |
| ``__len__`` / ``__bool__`` | 窗口内元素个数 |
"""
from ..builtins import *
from ..core.exceptions import IndexError, ValueError
from ..core.protocols import Comparable
from ..util.list import list
from .container_mixin import AlgContainerMixin


class MonoQueue[T: Comparable](AlgContainerMixin):
  """双端单调队列；队头为当前窗口 min 或 max（由 ``is_min`` 决定）。"""

  def __init__(self, is_min: bool = True):
    self._is_min: bool = is_min
    self._window: list[T] = []
    self._mono: list[T] = []

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    self._is_min = other._is_min
    window: list[T] = []
    mono: list[T] = []
    self._window = window
    self._mono = mono
    for i in range(len(other._window)):
      self._window.append(other._window[i])
    for i in range(len(other._mono)):
      self._mono.append(other._mono[i])

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    self._is_min = other._is_min
    self._window = other._window
    self._mono = other._mono
    window: list[T] = []
    mono: list[T] = []
    other._window = window
    other._mono = mono

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
    out: Self = new(self._is_min)
    out.__copy__(self)
    return out

  def push(self, x: T) -> None:
    if self._is_min:
      while self._mono and self._mono[-1] > x:
        self._mono.pop()
    else:
      while self._mono and self._mono[-1] < x:
        self._mono.pop()
    self._mono.append(x)
    self._window.append(x)

  def pop(self) -> None:
    if not self._window:
      raise IndexError("pop from empty mono queue")
    if self._mono and self._mono[0] == self._window[0]:
      self._mono.pop(0)
    self._window.pop(0)

  @immutable
  def min(self) -> T:
    if not self._is_min:
      raise ValueError("min() requires is_min=True")
    if not self._mono:
      raise IndexError("min on empty mono queue")
    return self._mono[0]

  @immutable
  def max(self) -> T:
    if self._is_min:
      raise ValueError("max() requires is_min=False")
    if not self._mono:
      raise IndexError("max on empty mono queue")
    return self._mono[0]

  @immutable
  def __len__(self) -> int:
    return len(self._window)

  @immutable
  def __bool__(self) -> bool:
    return bool(self._window)
