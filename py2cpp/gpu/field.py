"""GPU 设备端缓冲区 ``Field[T]``（Host 侧包装 ``array[Element, 0]``）。"""
from ..builtins import *
from ..util.array import array


class Field[Element]:
  """一维 GPU 字段；P1 Host 侧以堆 ``array`` 为 backing store。"""

  _data: array[Element, 0]
  _size: int = 0

  def __init__(self):
    self._data = new()

  @immutable
  def __len__(self) -> int:
    return self._size

  @staticmethod
  def zeros(n: int) -> Self:
    f: Self = new()
    f._size = n
    if n > 0:
      f._data.initCapacity(n)
      f._data.fill(Element())
    return f

  @staticmethod
  def ones(n: int) -> Self:
    f: Self = new()
    f._size = n
    if n > 0:
      f._data.initCapacity(n)
      for i in range(n):
        f._data[i] = 1.0
    return f

  @staticmethod
  def fromHost(src: list[Element]) -> Self:
    f: Self = new()
    n: int = len(src)
    f._size = n
    if n > 0:
      f._data.initCapacity(n)
      for i in range(n):
        f._data[i] = src[i]
    return f

  def copyFromHost(self, src: list[Element]) -> None:
    n: int = len(src)
    if n != self._size:
      self._size = n
      if n > 0:
        self._data.initCapacity(n)
      else:
        self._data = new()
    for i in range(n):
      self._data[i] = src[i]

  def toHost(self) -> list[Element]:
    out: list[Element] = []
    for i in range(self._size):
      out.append(self._data[i])
    return out

  def unsafePtr(self) -> Pointer[Element]:
    """Host 连续缓冲首址；CUDA ``.map`` 用于 H↔D 拷贝。"""
    return self._data.unsafePtr()

  def unsafeGet(self, index: int) -> Element:
    return self._data.unsafeGet(index)

  def unsafeSet(self, index: int, value: Element) -> None:
    self._data.unsafeSet(index, value)
