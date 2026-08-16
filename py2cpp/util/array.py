"""数组类型：Element[:] 一维，Element[:,:] 二维；a[i,j] → __getitem__((int, int)(i, j))

``array[Element, StackLength]`` 内嵌 SSO/堆存储（``_stack`` / ``_heap`` / ``_ptr``）；``array2d`` / ``array3d`` 以 ``_data: array[Element, 0]`` 为底。
"""
from ..builtins import *
from ..core.exceptions import IndexError
from ..util.memory import copyBuf
from .span import span, span2d, span3d


class array[Element, StackLength: int = 0]:
  """Element[:] — 一维定长/可 reshape 缓冲区。"""

  _stack: Element[:StackLength]
  _heap: bool = False
  _ptr: Pointer[Element] = None
  _shape: (int,)

  @overload
  def __init__(self):
    """空缓冲（``list`` 内部 ``data`` 等）。"""
    self.clearState()
    self._shape = (0,)

  @overload
  def __init__(self, size: int):
    self.initCapacity(size)

  def initCapacity(self, size: int) -> None:
    """分配 ``size`` 个 ``Element()`` 初值（``array2d`` / ``array3d`` 构造等）。"""
    self.clearState()
    self._shape = (size,)
    if size > 0:
      self.allocate(size)

  def __del__(self):
    self.release(self._shape[0])

  @immutable
  def isHeap(self) -> bool:
    if StackLength <= 0:
      return self._ptr is not None
    return self._heap

  def clearState(self) -> None:
    self._ptr = None
    self._heap = False

  def release(self, oldCount: int) -> None:
    if self._ptr is None:
      return
    for i in range(oldCount):
      destroy(self._ptr + i)
    if self._heap or StackLength <= 0:
      freeArray(self._ptr)
    self.clearState()

  def bindInline(self) -> None:
    self._ptr = self._stack.view.at(0)
    self._heap = False

  def allocate(self, size: int) -> Pointer[Element]:
    if size <= 0:
      self.clearState()
      return None
    if StackLength > 0 and size <= StackLength:
      self._ptr = self._stack.view.at(0)
      self._heap = False
      for i in range(size):
        init(self._ptr + i, Element())
      return self._ptr
    self._ptr = allocRawArray[Element](size)
    self._heap = True
    for i in range(size):
      init(self._ptr + i, Element())
    return self._ptr

  def copyFromPtr(self, src: Pointer[Element], n: int, active: int) -> None:
    if n <= 0 or src is None:
      self.clearState()
      return
    copyN: int = n
    if active >= 0 and active < copyN:
      copyN = active
    if StackLength > 0 and n <= StackLength:
      self._ptr = self._stack.view.at(0)
      self._heap = False
      for i in range(copyN):
        init(self._ptr + i, src[i])
    else:
      self._ptr = allocRawArray[Element](n)
      self._heap = True
      for i in range(copyN):
        init(self._ptr + i, src[i])

  def adoptHeap(self, p: Pointer[Element]) -> None:
    self._ptr = p
    self._heap = True

  def resetAfterMove(self) -> None:
    self.clearState()

  def moveFromInline(self, other: Self, n: int) -> Pointer[Element]:
    otherSso: Pointer[Element] = other._stack.view.at(0)
    if StackLength > 0 and n <= StackLength:
      self._ptr = self._stack.view.at(0)
      self._heap = False
    else:
      self._ptr = allocRawArray[Element](n)
      self._heap = True
    for i in range(n):
      init(self._ptr + i, otherSso[i])
      destroy(otherSso + i)
    other.resetAfterMove()
    return self._ptr

  def reallocate(
    self,
    newSize: int,
    active: int,
    oldSize: int,
    oldBuf: Pointer[Element],
    copyN: int,
  ) -> None:
    wasHeap: bool = self.isHeap()
    if newSize <= 0:
      if oldBuf is not None:
        for j in range(copyN, oldSize):
          if j < active:
            destroy(oldBuf + j)
        for i in range(copyN):
          destroy(oldBuf + i)
        if wasHeap or StackLength <= 0:
          freeArray(oldBuf)
      self.clearState()
      return
    if StackLength > 0 and newSize <= StackLength:
      newBuf: Pointer[Element] = self._stack.view.at(0)
      for i in range(copyN):
        if oldBuf is not None:
          init(newBuf + i, oldBuf[i])
      if oldBuf is not None:
        for j in range(copyN, oldSize):
          if j < active:
            destroy(oldBuf + j)
        for i in range(copyN):
          destroy(oldBuf + i)
        if wasHeap:
          freeArray(oldBuf)
      self.bindInline()
      return
    newBuf: Pointer[Element] = allocRawArray[Element](newSize)
    for i in range(copyN):
      if oldBuf is not None:
        init(newBuf + i, oldBuf[i])
    if oldBuf is not None:
      for j in range(copyN, oldSize):
        if j < active:
          destroy(oldBuf + j)
      for i in range(copyN):
        destroy(oldBuf + i)
      if wasHeap or StackLength <= 0:
        freeArray(oldBuf)
    self.adoptHeap(newBuf)

  def releaseBuffer(self, active: int) -> None:
    """释放 ``active`` 个已构造元素并清空（``list._clear`` 等）。"""
    self.release(active)
    self._shape = (0,)

  def __copy__(self, other):
    """元素级拷贝；目标长度须与 ``other`` 相同。"""
    n: int = len(other)
    if len(self) != n:
      raise IndexError("__copy__ size mismatch")
    for i in range(n):
      self[i] = other[i]

  def __move__(self, other: Self):
    if self is other:
      return
    self.release(self._shape[0])
    n: int = len(other)
    if n <= 0:
      self._shape = (0,)
      self.clearState()
      other.__moved__ = True
      return
    if other.isHeap():
      self._shape = other._shape
      self.adoptHeap(other._ptr)
      other.resetAfterMove()
      other._shape = (0,)
      other.__moved__ = True
      return
    self._shape = (n,)
    self.moveFromInline(other, n)
    other._shape = (0,)
    other.__moved__ = True

  @immutable
  def __bool__(self) -> bool:
    return self._shape[0] > 0

  @immutable
  def __len__(self) -> int:
    return self._shape[0]

  @immutable
  def __getitem__(self, index: int) -> Element:
    if index < 0 or index >= self._shape[0]:
      raise IndexError("array index out of range")
    return self._ptr[index]

  def __setitem__(self, index: int, value: Element):
    if index < 0 or index >= self._shape[0]:
      raise IndexError("array index out of range")
    self._ptr[index] = value

  @property
  @immutable
  def view(self) -> span[Element]:
    return new(self._ptr, self._shape[0], 1)

  def initSlot(self, index: int, value: Element) -> None:
    init(self.view.at(index), value)

  def destroySlot(self, index: int) -> None:
    destroy(self.view.at(index))

  def copyPtrFrom(self, destOff: int, src: Pointer[Element], n: int) -> None:
    copyBuf(self.view.at(destOff), src, n)

  @immutable
  def copyPtrTo(self, srcOff: int, dest: Pointer[Element], n: int) -> None:
    copyBuf(dest, self.view.at(srcOff), n)

  def reshape(self, newSize: int, active: int = -1):
    """扩容/缩容缓冲。``active`` 为已构造元素个数（``list`` 传 ``_length``）；默认 -1 表示整块有效。"""
    if newSize == self._shape[0]:
      return
    if active < 0:
      active = self._shape[0]
    oldSize: int = self._shape[0]
    copyN: int = oldSize
    if newSize < copyN:
      copyN = newSize
    if active < copyN:
      copyN = active
    self.reallocate(newSize, active, oldSize, self._ptr, copyN)
    self._shape = (newSize,)

  def reserve(self, need: int, active: int = -1) -> None:
    """容量至少扩至 ``need``；``active`` 为已构造元素个数（默认 ``len(self)``）。"""
    if active < 0:
      active = len(self)
    if need > len(self):
      self.reshape(need, active)

  def adoptSpan(self, seg: span[Element]) -> None:
    """接管 ``span`` 底层缓冲所有权（析构时 ``freeArray``）。"""
    self.release(self._shape[0])
    self.adoptHeap(seg.at())
    self._shape = (len(seg),)

  def fill(self, value: Element) -> None:
    if self._ptr is None:
      return
    for i in range(self._shape[0]):
      self._ptr[i] = value

  @immutable
  def unsafeGet(self, index: int) -> Element:
    return self._ptr[index]

  def unsafeSet(self, index: int, value: Element) -> None:
    self._ptr[index] = value


@native_name("PyArray2D")
class array2d[Element]:
  """Element[:,:] — 二维；a[i, j] → __getitem__((int, int)(i, j))"""

  _data: array[Element, 0]
  _shape: (int, int)

  @overload
  def __init__(self):
    """空缓冲（类成员默认构造等）。"""
    self._shape = (0, 0)

  @overload
  def __init__(self, rows: int, cols: int):
    self._shape = (rows, cols)
    n: int = rows * cols
    if n > 0:
      self._data.initCapacity(n)

  @immutable
  def _count(self) -> int:
    return self._shape[0] * self._shape[1]

  def __copy__(self, other):
    """元素级拷贝；``shape`` 不一致时先按 ``other`` 重建 ``_data``。"""
    self._shape = other._shape
    n: int = len(other._data)
    if len(self._data) != n:
      self._data.reshape(n)
    self._data.__copy__(other._data)

  @immutable
  def __bool__(self) -> bool:
    return self._shape[0] > 0 and self._shape[1] > 0

  @immutable
  def __getitem__(self, index: (int, int)) -> Element:
    row: int = index[0]
    col: int = index[1]
    if row < 0 or row >= self._shape[0] or col < 0 or col >= self._shape[1]:
      raise IndexError("array index out of range")
    return self._data[self._index(row, col)]

  def __setitem__(self, index: (int, int), value: Element):
    row: int = index[0]
    col: int = index[1]
    if row < 0 or row >= self._shape[0] or col < 0 or col >= self._shape[1]:
      raise IndexError("array index out of range")
    self._data[self._index(row, col)] = value

  @immutable
  def _index(self, row: int, col: int) -> int:
    return row * self._shape[1] + col

  @property
  @immutable
  def view(self) -> span2d[Element]:
    if not self._data:
      return new(None, (0, 0), 0)
    return new(self._data.view.at(0), self._shape, self._shape[1])

  def fill(self, value: Element) -> None:
    self._data.fill(value)

  @immutable
  def unsafeGet(self, row: int, col: int) -> Element:
    return self._data.unsafeGet(self._index(row, col))

  def unsafeSet(self, row: int, col: int, value: Element) -> None:
    self._data.unsafeSet(self._index(row, col), value)


@native_name("PyArray3D")
class array3d[Element]:
  """Element[:,:,:] — 三维；a[i, j, k] → __getitem__((int, int, int)(i, j, k))"""

  _data: array[Element, 0]
  _shape: (int, int, int)

  def __init__(self, d0: int, d1: int, d2: int):
    self._shape = (d0, d1, d2)
    n: int = d0 * d1 * d2
    if n > 0:
      self._data.initCapacity(n)

  @immutable
  def _count(self) -> int:
    return self._shape[0] * self._shape[1] * self._shape[2]

  def __getitem__(self, index: (int, int, int)) -> Element:
    i: int = index[0]
    j: int = index[1]
    k: int = index[2]
    if i < 0 or i >= self._shape[0] or j < 0 or j >= self._shape[1] or k < 0 or k >= self._shape[2]:
      raise IndexError("array index out of range")
    return self._data[self._index(i, j, k)]

  def __setitem__(self, index: (int, int, int), value: Element):
    i: int = index[0]
    j: int = index[1]
    k: int = index[2]
    if i < 0 or i >= self._shape[0] or j < 0 or j >= self._shape[1] or k < 0 or k >= self._shape[2]:
      raise IndexError("array index out of range")
    self._data[self._index(i, j, k)] = value

  def _index(self, i: int, j: int, k: int) -> int:
    return (i * self._shape[1] + j) * self._shape[2] + k

  @property
  @immutable
  def view(self) -> span3d[Element]:
    if not self._data:
      return new(None, (0, 0, 0), (0, 0))
    plane: int = self._shape[1] * self._shape[2]
    return new(self._data.view.at(0), self._shape, (plane, self._shape[2]))

  def fill(self, value: Element) -> None:
    self._data.fill(value)

  @immutable
  def unsafeGet(self, i: int, j: int, k: int) -> Element:
    return self._data.unsafeGet(self._index(i, j, k))

  def unsafeSet(self, i: int, j: int, k: int, value: Element) -> None:
    self._data.unsafeSet(self._index(i, j, k), value)
