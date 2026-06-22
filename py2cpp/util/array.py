"""数组类型：T[:] 一维，T[:,:] 二维；a[i,j] → __getitem__((int, int)(i,j))

``array[T, StackLength]``（``StackLength=0`` 默认堆，``StackLength>0`` SSO）内嵌 ``Allocator[T, StackLength]``。
"""
from ..builtins import *
from ..core.exceptions import IndexError
from .allocator import Allocator
from .span import span, span2d, span3d


@native_name("PyArray")
class array[T, StackLength: int = 0]:
  """T[:] — 一维定长/可 reshape 缓冲区（``_alloc`` 持有元素存储）。"""

  _alloc: Allocator[T, StackLength]
  shape: (int,)
  buf: Pointer[T] = None

  @overload
  def __init__(self):
    """空缓冲（``list`` 内部 ``data`` 等）。"""
    self._alloc = new()
    self.shape = (0,)
    self.buf = None

  @overload
  def __init__(self, size: int):
    self._alloc = new()
    self.shape = (size,)
    self.buf = None
    if size > 0:
      self.buf = self._alloc.allocate(size)

  def __del__(self):
    self._alloc.release(self.shape[0])
    self.buf = None

  def release_buffer(self, active: int) -> None:
    """释放 ``active`` 个已构造元素并清空（``list._clear`` 等）。"""
    self._alloc.release(active)
    self.buf = None
    self.shape = (0,)

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
    self._alloc.release(self.shape[0])
    n: int = len(other)
    if n <= 0:
      self.shape = (0,)
      self.buf = None
      self._alloc.clear_state()
      other.__moved__ = True
      return
    if other._alloc.is_heap():
      self.shape = other.shape
      self._alloc.steal_heap(other.buf)
      self.buf = self._alloc.ptr()
      other.buf = None
      other._alloc.reset_after_move()
      other.shape = (0,)
      other.__moved__ = True
      return
    self.shape = (n,)
    self.buf = self._alloc.move_from_inline(other._alloc, n)
    other.buf = None
    other.shape = (0,)
    other.__moved__ = True

  @immutable
  def __bool__(self) -> bool:
    return self.shape[0] > 0

  @immutable
  def __len__(self) -> int:
    return self.shape[0]

  @immutable
  def __getitem__(self, index: int) -> T:
    if index < 0 or index >= self.shape[0]:
      raise IndexError("array index out of range")
    return self.buf[index]

  def __setitem__(self, index: int, value: T):
    if index < 0 or index >= self.shape[0]:
      raise IndexError("array index out of range")
    self.buf[index] = value

  @property
  @immutable
  def view(self) -> span[T]:
    return new(self.buf, self.shape[0], 1)

  def reshape(self, new_size: int, active: int = -1):
    """扩容/缩容缓冲。``active`` 为已构造元素个数（``list`` 传 ``_length``）；默认 -1 表示整块有效。"""
    if new_size == self.shape[0]:
      return
    if active < 0:
      active = self.shape[0]
    old_size: int = self.shape[0]
    copy_n: int = old_size
    if new_size < copy_n:
      copy_n = new_size
    if active < copy_n:
      copy_n = active
    old_buf: Pointer[T] = self.buf
    self.buf = self._alloc.reallocate(new_size, active, old_size, old_buf, copy_n)
    self.shape[0] = new_size

  def reserve(self, need: int, active: int = -1) -> None:
    """容量至少扩至 ``need``；``active`` 为已构造元素个数（默认 ``len(self)``）。"""
    if active < 0:
      active = len(self)
    if need > len(self):
      self.reshape(need, active)

  def adopt_span(self, seg: span[T]) -> None:
    """接管 ``span`` 底层缓冲所有权（析构时 ``freeArray``）。"""
    self._alloc.release(self.shape[0])
    self._alloc.steal_heap(seg.at())
    self.buf = self._alloc.ptr()
    self.shape[0] = len(seg)

  def fill(self, value: T) -> None:
    if self.buf is None:
      return
    for i in range(self.shape[0]):
      self.buf[i] = value

  @immutable
  def unsafe_get(self, index: int) -> T:
    return self.buf[index]

  def unsafe_set(self, index: int, value: T) -> None:
    self.buf[index] = value


@native_name("PyArray2D")
class array2d[T]:
  """T[:,:] — 二维；a[i, j] → __getitem__((int, int)(i, j))"""

  @overload
  def __init__(self):
    """空缓冲（类成员默认构造等）。"""
    self.shape: (int, int) = (0, 0)
    self.buf: Pointer[T] = None

  @overload
  def __init__(self, rows: int, cols: int):
    self.shape: (int, int) = (rows, cols)
    self.buf: Pointer[T] = None
    n: int = rows * cols
    if n > 0:
      self.buf = allocArray[T](n)

  def __del__(self):
    if self.buf is None:
      return
    n: int = self.shape[0] * self.shape[1]
    for i in range(n):
      destroy(self.buf + i)
    freeArray(self.buf)
    self.buf = None

  def __copy__(self, other):
    """元素级拷贝；目标 ``shape`` 须与 ``other`` 相同。"""
    if self.shape[0] != other.shape[0] or self.shape[1] != other.shape[1]:
      raise IndexError("__copy__ size mismatch")
    rows: int = self.shape[0]
    cols: int = self.shape[1]
    for r in range(rows):
      for c in range(cols):
        self[r, c] = other[r, c]

  @immutable
  def __bool__(self) -> bool:
    return self.shape[0] > 0 and self.shape[1] > 0

  @immutable
  def __getitem__(self, index: (int, int)) -> T:
    row: int = index[0]
    col: int = index[1]
    if row < 0 or row >= self.shape[0] or col < 0 or col >= self.shape[1]:
      raise IndexError("array index out of range")
    return self.buf[self._index(row, col)]

  def __setitem__(self, index: (int, int), value: T):
    row: int = index[0]
    col: int = index[1]
    if row < 0 or row >= self.shape[0] or col < 0 or col >= self.shape[1]:
      raise IndexError("array index out of range")
    self.buf[self._index(row, col)] = value

  @immutable
  def _index(self, row: int, col: int) -> int:
    return row * self.shape[1] + col

  @property
  @immutable
  def view(self) -> span2d[T]:
    if self.buf is None:
      return new(None, (0, 0), 0)
    return new(self.buf, self.shape, self.shape[1])

  def fill(self, value: T) -> None:
    if self.buf is None:
      return
    n: int = self.shape[0] * self.shape[1]
    for i in range(n):
      self.buf[i] = value

  @immutable
  def unsafe_get(self, row: int, col: int) -> T:
    return self.buf[self._index(row, col)]

  def unsafe_set(self, row: int, col: int, value: T) -> None:
    self.buf[self._index(row, col)] = value


@native_name("PyArray3D")
class array3d[T]:
  """T[:,:,:] — 三维；a[i, j, k] → __getitem__((int, int, int)(i, j, k))"""

  def __init__(self, d0: int, d1: int, d2: int):
    self.shape: (int, int, int) = (d0, d1, d2)
    self.buf: Pointer[T] = None
    n: int = d0 * d1 * d2
    if n > 0:
      self.buf = allocArray[T](n)

  def __del__(self):
    if self.buf is None:
      return
    n: int = self.shape[0] * self.shape[1] * self.shape[2]
    for i in range(n):
      destroy(self.buf + i)
    freeArray(self.buf)
    self.buf = None

  def __getitem__(self, index: (int, int, int)) -> T:
    i: int = index[0]
    j: int = index[1]
    k: int = index[2]
    if i < 0 or i >= self.shape[0] or j < 0 or j >= self.shape[1] or k < 0 or k >= self.shape[2]:
      raise IndexError("array index out of range")
    return self.buf[self._index(i, j, k)]

  def __setitem__(self, index: (int, int, int), value: T):
    i: int = index[0]
    j: int = index[1]
    k: int = index[2]
    if i < 0 or i >= self.shape[0] or j < 0 or j >= self.shape[1] or k < 0 or k >= self.shape[2]:
      raise IndexError("array index out of range")
    self.buf[self._index(i, j, k)] = value

  def _index(self, i: int, j: int, k: int) -> int:
    return (i * self.shape[1] + j) * self.shape[2] + k

  @property
  @immutable
  def view(self) -> span3d[T]:
    if self.buf is None:
      return new(None, (0, 0, 0), (0, 0))
    plane: int = self.shape[1] * self.shape[2]
    return new(self.buf, self.shape, (plane, self.shape[2]))

  def fill(self, value: T) -> None:
    if self.buf is None:
      return
    n: int = self.shape[0] * self.shape[1] * self.shape[2]
    for i in range(n):
      self.buf[i] = value

  @immutable
  def unsafe_get(self, i: int, j: int, k: int) -> T:
    return self.buf[self._index(i, j, k)]

  def unsafe_set(self, i: int, j: int, k: int, value: T) -> None:
    self.buf[self._index(i, j, k)] = value
