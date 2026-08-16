"""单调队列（滑动窗口最值）。

公开 API：

| 方法 | 说明 |
|------|------|
| ``push(x)`` | 窗口右端入队 |
| ``pop()`` | 窗口左端滑出 |
| ``min()`` / ``max()`` | 当前窗口极值（构造时 ``isMin`` 指定其一） |
| ``__len__`` / ``__bool__`` | 窗口内元素个数 |
"""
from ..builtins import *
from ..core.exceptions import IndexError, ValueError
from ..util.protocols import ComparableType
from ..util.list import list
from ..util.mixins import ContainerMixin


class MonoQueue[Element: ComparableType](ContainerMixin):
  """双端单调队列；队头为当前窗口 min 或 max（由 ``isMin`` 决定）。"""

  def __init__(self, isMin: bool = True):
    self._isMin: bool = isMin
    self._window: list[Element] = []
    self._mono: list[Element] = []

  def __copy__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._isMin = other._isMin
    window: list[Element] = []
    mono: list[Element] = []
    self._window = window
    self._mono = mono
    for i in range(len(other._window)):
      self._window.append(other._window[i])
    for i in range(len(other._mono)):
      self._mono.append(other._mono[i])

  def __move__(self, other: Self):
    self._ensureActive()
    if other.__moved__:
      raise ValueError("move from moved container")
    self._isMin = other._isMin
    self._window = other._window
    self._mono = other._mono
    window: list[Element] = []
    mono: list[Element] = []
    other._window = window
    other._mono = mono

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = new(self._isMin)
    out.__copy__(self)
    return out

  def push(self, x: Element) -> None:
    if self._isMin:
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
  def min(self) -> Element:
    if not self._isMin:
      raise ValueError("min() requires isMin=True")
    if not self._mono:
      raise IndexError("min on empty mono queue")
    return self._mono[0]

  @immutable
  def max(self) -> Element:
    if self._isMin:
      raise ValueError("max() requires isMin=False")
    if not self._mono:
      raise IndexError("max on empty mono queue")
    return self._mono[0]

  @immutable
  def __len__(self) -> int:
    return len(self._window)

  @immutable
  def __bool__(self) -> bool:
    return bool(self._window)
