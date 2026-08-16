"""内存视图：``span[T]`` / ``span2d[T]`` / ``span3d[T]`` → ``PySpan`` / ``PySpan2D`` / ``PySpan3D``。

一维 ``s[k]`` 下标相对 span 起点；多维 ``v[r,c]`` / ``v[i,j,k]`` 相对局部坐标；再切片仍为共享视图而非拷贝。``__setitem__`` 为 ``@immutable``：只写 ``*_ptr`` 指向的底层槽位，``const`` 形参仍可赋值。
"""
from ..builtins import *
from ..core.exceptions import IndexError
from .slice import slice


@copyable
class span[Element]:
  """绑定 ``StackArray`` / ``array`` / ``list`` 的连续区间。"""

  @overload
  def __init__(self):
    self._ptr: Pointer[Element] = None
    self._length: int = 0
    self._step: int = 1

  @overload
  def __init__(self, ptr: Pointer[Element], length: int, step: int = 1):
    """``length`` 为自 ``ptr`` 起的底层槽位跨度（``step==1`` 时即元素个数）。"""
    self._ptr: Pointer[Element] = ptr
    self._length: int = length
    self._step: int = step

  def __copy__(self, other: Self):
    self._ptr = other._ptr
    self._length = other._length
    self._step = other._step

  @immutable
  def __bool__(self) -> bool:
    return (self._length > 0) and (self._ptr is not None)

  @immutable
  def __len__(self) -> int:
    if self._step == 1:
      return self._length
    return self._sliceCount(0, self._length, self._step)

  @immutable
  def at(self, i: int = 0) -> Pointer[Element]:
    """逻辑下标 ``i`` 处元素地址（默认 ``0``；``step==1`` 时常用于 ``memcpy``）。"""
    return self._ptr + (i * self._step)

  @property
  @immutable
  def step(self) -> int:
    return self._step

  @immutable
  @overload
  def __getitem__(self, index: int) -> Element:
    index = self._normIndex(index)
    if not self._indexInRange(index):
      raise IndexError("span index out of range")
    return self._ptr[index * self._step]

  @immutable
  @overload
  def __getitem__(self, index: slice[int, int]) -> Self:
    trip: (int, int, int) = index.indices(len(self))
    cnt: int = self._sliceCount(trip[0], trip[1], trip[2])
    ptr: Pointer[Element] = self._ptr + (trip[0] * self._step)
    newStep: int = self._step * trip[2]
    phys: int = self._extentFromLogical(cnt, newStep)
    return new(ptr, phys, newStep)

  @immutable
  def __setitem__(self, index: int, value: Element):
    index = self._normIndex(index)
    if not self._indexInRange(index):
      raise IndexError("span index out of range")
    self._ptr[index * self._step] = value

  def fill(self, value: Element) -> None:
    if self._ptr is None:
      return
    n: int = len(self)
    step: int = self._step
    for i in range(n):
      self._ptr[i * step] = value

  @immutable
  def _extentFromLogical(self, logicalCount: int, step: int) -> int:
    if logicalCount == 0:
      return 0
    return (logicalCount - 1) * abs(step) + 1

  @immutable
  def _indexInRange(self, index: int) -> bool:
    n: int = len(self)
    return (index >= 0) and (index < n) and (self._ptr is not None)

  @immutable
  def _normIndex(self, index: int) -> int:
    if index < 0:
      index = len(self) + index
    return index

  @immutable
  def _sliceCount(self, start: int, stop: int, step: int) -> int:
    """切片元素个数（对齐 CPython / ``str`` 切片公式）。"""
    if step > 0:
      if start >= stop:
        return 0
      return (stop - start + step - 1) // step
    if start <= stop:
      return 0
    return (start - stop - step - 1) // (-step)


@copyable
@native_name("PySpan2D")
class span2d[Element]:
  """绑定 ``StackArray2d`` / ``array2d`` 的连续子矩形。"""

  def __init__(
    self,
    ptr: Pointer[Element],
    shape: (int, int),
    stride: int,
  ):
    self._ptr: Pointer[Element] = ptr
    self.shape: (int, int) = shape
    self.stride: int = stride

  def __copy__(self, other: Self):
    self._ptr = other._ptr
    self.shape = other.shape
    self.stride = other.stride

  @immutable
  def __bool__(self) -> bool:
    return (self.shape[0] > 0) and (self.shape[1] > 0) and (self._ptr is not None)

  @immutable
  def _linear(self, row: int, col: int) -> int:
    return row * self.stride + col

  @immutable
  def _rowInRange(self, row: int) -> bool:
    return (row >= 0) and (row < self.shape[0])

  @immutable
  def _colInRange(self, col: int) -> bool:
    return (col >= 0) and (col < self.shape[1])

  @immutable
  @overload
  def __getitem__(self, index: (int, int)) -> Element:
    row: int = index[0]
    col: int = index[1]
    if not self._rowInRange(row) or not self._colInRange(col):
      raise IndexError("span2d index out of range")
    return self._ptr[self._linear(row, col)]

  @immutable
  @overload
  def __getitem__(self, index: (slice[int, int], slice[int, int])) -> Self:
    rowSl: slice[int, int] = index[0]
    colSl: slice[int, int] = index[1]
    row: (int, int, int) = rowSl.indices(self.shape[0])
    col: (int, int, int) = colSl.indices(self.shape[1])
    if row[2] != 1 or col[2] != 1:
      raise IndexError("span2d slice step must be 1")
    outRows: int = row[1] - row[0]
    outCols: int = col[1] - col[0]
    if outRows < 0:
      outRows = 0
    if outCols < 0:
      outCols = 0
    ptr: Pointer[Element] = self._ptr + self._linear(row[0], col[0])
    return new(ptr, (outRows, outCols), self.stride)

  @immutable
  def __setitem__(self, index: (int, int), value: Element):
    row: int = index[0]
    col: int = index[1]
    if not self._rowInRange(row) or not self._colInRange(col):
      raise IndexError("span2d index out of range")
    self._ptr[self._linear(row, col)] = value

  def fill(self, value: Element) -> None:
    if self._ptr is None:
      return
    rows: int = self.shape[0]
    cols: int = self.shape[1]
    stride: int = self.stride
    if stride == cols:
      n: int = rows * cols
      for i in range(n):
        self._ptr[i] = value
    else:
      for r in range(rows):
        base: int = r * stride
        for c in range(cols):
          self._ptr[base + c] = value


@copyable
@native_name("PySpan3D")
class span3d[Element]:
  """绑定 ``StackArray3d`` / ``array3d`` 的连续子块。"""

  def __init__(
    self,
    ptr: Pointer[Element],
    shape: (int, int, int),
    strides: (int, int),
  ):
    self._ptr: Pointer[Element] = ptr
    self.shape: (int, int, int) = shape
    self.strides: (int, int) = strides

  def __copy__(self, other: Self):
    self._ptr = other._ptr
    self.shape = other.shape
    self.strides = other.strides

  @immutable
  def __bool__(self) -> bool:
    return (
      (self.shape[0] > 0)
      and (self.shape[1] > 0)
      and (self.shape[2] > 0)
      and (self._ptr is not None)
    )

  @immutable
  def _linear(self, i: int, j: int, k: int) -> int:
    return i * self.strides[0] + j * self.strides[1] + k

  @immutable
  def _inRange(self, idx: int, dim: int) -> bool:
    return (idx >= 0) and (idx < dim)

  @immutable
  @overload
  def __getitem__(self, index: (int, int, int)) -> Element:
    i: int = index[0]
    j: int = index[1]
    k: int = index[2]
    if (
      not self._inRange(i, self.shape[0])
      or not self._inRange(j, self.shape[1])
      or not self._inRange(k, self.shape[2])
    ):
      raise IndexError("span3d index out of range")
    return self._ptr[self._linear(i, j, k)]

  @immutable
  @overload
  def __getitem__(
    self,
    index: (slice[int, int], slice[int, int], slice[int, int]),
  ) -> Self:
    sl0: slice[int, int] = index[0]
    sl1: slice[int, int] = index[1]
    sl2: slice[int, int] = index[2]
    d0: (int, int, int) = sl0.indices(self.shape[0])
    d1: (int, int, int) = sl1.indices(self.shape[1])
    d2: (int, int, int) = sl2.indices(self.shape[2])
    if d0[2] != 1 or d1[2] != 1 or d2[2] != 1:
      raise IndexError("span3d slice step must be 1")
    n0: int = d0[1] - d0[0]
    n1: int = d1[1] - d1[0]
    n2: int = d2[1] - d2[0]
    if n0 < 0:
      n0 = 0
    if n1 < 0:
      n1 = 0
    if n2 < 0:
      n2 = 0
    ptr: Pointer[Element] = self._ptr + self._linear(d0[0], d1[0], d2[0])
    return new(ptr, (n0, n1, n2), self.strides)

  @immutable
  def __setitem__(self, index: (int, int, int), value: Element):
    i: int = index[0]
    j: int = index[1]
    k: int = index[2]
    if (
      not self._inRange(i, self.shape[0])
      or not self._inRange(j, self.shape[1])
      or not self._inRange(k, self.shape[2])
    ):
      raise IndexError("span3d index out of range")
    self._ptr[self._linear(i, j, k)] = value

  def fill(self, value: Element) -> None:
    if self._ptr is None:
      return
    d0: int = self.shape[0]
    d1: int = self.shape[1]
    d2: int = self.shape[2]
    s0: int = self.strides[0]
    s1: int = self.strides[1]
    if s0 == d1 * d2 and s1 == d2:
      n: int = d0 * d1 * d2
      for i in range(n):
        self._ptr[i] = value
    else:
      for i in range(d0):
        for j in range(d1):
          base: int = i * s0 + j * s1
          for k in range(d2):
            self._ptr[base + k] = value
