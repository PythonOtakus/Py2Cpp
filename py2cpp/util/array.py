"""数组类型：Element[:] 一维，Element[:,:] 二维；a[i,j] → __getitem__((int, int)(i, j))

``array[Element, StackLength]`` 内嵌 SSO/堆存储（``_stack`` / ``_heap`` / ``_ptr``）；``array2d`` / ``array3d`` 以 ``_data: array[Element, 0]`` 为底。
"""
from ..builtins import *
from ..core.exceptions import IndexError
from ..util.memory import copy_buf
from .span import span, span2d, span3d


@native_name("PyArray")
class array[Element, StackLength: int = 0]:
  """Element[:] — 一维定长/可 reshape 缓冲区。"""

  _stack: Element[:StackLength]
  _heap: bool = False
  _ptr: Pointer[Element] = None
  _shape: (int,)

  @overload
  def __init__(self):
    """空缓冲（``list`` 内部 ``data`` 等）。"""
    self.clear_state()
    self._shape = (0,)

  @overload
  def __init__(self, size: int):
    self.init_capacity(size)

  def init_capacity(self, size: int) -> None:
    """分配 ``size`` 个 ``Element()`` 初值（``array2d`` / ``array3d`` 构造等）。"""
    self.clear_state()
    self._shape = (size,)
    if size > 0:
      self.allocate(size)

  def __del__(self):
    self.release(self._shape[0])

  @immutable
  def is_heap(self) -> bool:
    if StackLength <= 0:
      return self._ptr is not None
    return self._heap

  def clear_state(self) -> None:
    self._ptr = None
    self._heap = False

  def release(self, old_count: int) -> None:
    if self._ptr is None:
      return
    for i in range(old_count):
      destroy(self._ptr + i)
    if self._heap or StackLength <= 0:
      freeArray(self._ptr)
    self.clear_state()

  def bind_inline(self) -> None:
    self._ptr = self._stack.view.at(0)
    self._heap = False

  def allocate(self, size: int) -> Pointer[Element]:
    if size <= 0:
      self.clear_state()
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

  def copy_from_ptr(self, src: Pointer[Element], n: int, active: int) -> None:
    if n <= 0 or src is None:
      self.clear_state()
      return
    copy_n: int = n
    if active >= 0 and active < copy_n:
      copy_n = active
    if StackLength > 0 and n <= StackLength:
      self._ptr = self._stack.view.at(0)
      self._heap = False
      for i in range(copy_n):
        init(self._ptr + i, src[i])
    else:
      self._ptr = allocRawArray[Element](n)
      self._heap = True
      for i in range(copy_n):
        init(self._ptr + i, src[i])

  def adopt_heap(self, p: Pointer[Element]) -> None:
    self._ptr = p
    self._heap = True

  def reset_after_move(self) -> None:
    self.clear_state()

  def move_from_inline(self, other: Self, n: int) -> Pointer[Element]:
    other_sso: Pointer[Element] = other._stack.view.at(0)
    if StackLength > 0 and n <= StackLength:
      self._ptr = self._stack.view.at(0)
      self._heap = False
    else:
      self._ptr = allocRawArray[Element](n)
      self._heap = True
    for i in range(n):
      init(self._ptr + i, other_sso[i])
      destroy(other_sso + i)
    other.reset_after_move()
    return self._ptr

  def reallocate(
    self,
    new_size: int,
    active: int,
    old_size: int,
    old_buf: Pointer[Element],
    copy_n: int,
  ) -> None:
    was_heap: bool = self.is_heap()
    if new_size <= 0:
      if old_buf is not None:
        for j in range(copy_n, old_size):
          if j < active:
            destroy(old_buf + j)
        for i in range(copy_n):
          destroy(old_buf + i)
        if was_heap or StackLength <= 0:
          freeArray(old_buf)
      self.clear_state()
      return
    if StackLength > 0 and new_size <= StackLength:
      new_buf: Pointer[Element] = self._stack.view.at(0)
      for i in range(copy_n):
        if old_buf is not None:
          init(new_buf + i, old_buf[i])
      if old_buf is not None:
        for j in range(copy_n, old_size):
          if j < active:
            destroy(old_buf + j)
        for i in range(copy_n):
          destroy(old_buf + i)
        if was_heap:
          freeArray(old_buf)
      self.bind_inline()
      return
    new_buf: Pointer[Element] = allocRawArray[Element](new_size)
    for i in range(copy_n):
      if old_buf is not None:
        init(new_buf + i, old_buf[i])
    if old_buf is not None:
      for j in range(copy_n, old_size):
        if j < active:
          destroy(old_buf + j)
      for i in range(copy_n):
        destroy(old_buf + i)
      if was_heap or StackLength <= 0:
        freeArray(old_buf)
    self.adopt_heap(new_buf)

  def release_buffer(self, active: int) -> None:
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
      self.clear_state()
      other.__moved__ = True
      return
    if other.is_heap():
      self._shape = other._shape
      self.adopt_heap(other._ptr)
      other.reset_after_move()
      other._shape = (0,)
      other.__moved__ = True
      return
    self._shape = (n,)
    self.move_from_inline(other, n)
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

  def init_slot(self, index: int, value: Element) -> None:
    init(self.view.at(index), value)

  def destroy_slot(self, index: int) -> None:
    destroy(self.view.at(index))

  def copy_ptr_from(self, dest_off: int, src: Pointer[Element], n: int) -> None:
    copy_buf(self.view.at(dest_off), src, n)

  @immutable
  def copy_ptr_to(self, src_off: int, dest: Pointer[Element], n: int) -> None:
    copy_buf(dest, self.view.at(src_off), n)

  def reshape(self, new_size: int, active: int = -1):
    """扩容/缩容缓冲。``active`` 为已构造元素个数（``list`` 传 ``_length``）；默认 -1 表示整块有效。"""
    if new_size == self._shape[0]:
      return
    if active < 0:
      active = self._shape[0]
    old_size: int = self._shape[0]
    copy_n: int = old_size
    if new_size < copy_n:
      copy_n = new_size
    if active < copy_n:
      copy_n = active
    self.reallocate(new_size, active, old_size, self._ptr, copy_n)
    self._shape = (new_size,)

  def reserve(self, need: int, active: int = -1) -> None:
    """容量至少扩至 ``need``；``active`` 为已构造元素个数（默认 ``len(self)``）。"""
    if active < 0:
      active = len(self)
    if need > len(self):
      self.reshape(need, active)

  def adopt_span(self, seg: span[Element]) -> None:
    """接管 ``span`` 底层缓冲所有权（析构时 ``freeArray``）。"""
    self.release(self._shape[0])
    self.adopt_heap(seg.at())
    self._shape = (len(seg),)

  def fill(self, value: Element) -> None:
    if self._ptr is None:
      return
    for i in range(self._shape[0]):
      self._ptr[i] = value

  @immutable
  def unsafe_get(self, index: int) -> Element:
    return self._ptr[index]

  def unsafe_set(self, index: int, value: Element) -> None:
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
      self._data.init_capacity(n)

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
  def unsafe_get(self, row: int, col: int) -> Element:
    return self._data.unsafe_get(self._index(row, col))

  def unsafe_set(self, row: int, col: int, value: Element) -> None:
    self._data.unsafe_set(self._index(row, col), value)


@native_name("PyArray3D")
class array3d[Element]:
  """Element[:,:,:] — 三维；a[i, j, k] → __getitem__((int, int, int)(i, j, k))"""

  _data: array[Element, 0]
  _shape: (int, int, int)

  def __init__(self, d0: int, d1: int, d2: int):
    self._shape = (d0, d1, d2)
    n: int = d0 * d1 * d2
    if n > 0:
      self._data.init_capacity(n)

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
  def unsafe_get(self, i: int, j: int, k: int) -> Element:
    return self._data.unsafe_get(self._index(i, j, k))

  def unsafe_set(self, i: int, j: int, k: int, value: Element) -> None:
    self._data.unsafe_set(self._index(i, j, k), value)
