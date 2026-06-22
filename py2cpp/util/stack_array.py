"""栈定长数组：一维 ``PyStackArray``、二维 ``PyStackArray2D``、三维 ``PyStackArray3D``。

``T[:N]`` / ``T[:R,:C]`` / ``T[:D0,:D1,:D2]`` 为拥有存储；子区间注解为绝对下标。``buf[i:j]`` / ``grid[r0:r1,c0:c1]`` → 堆拷贝。
"""
from ..builtins import *
from ..core.exceptions import IndexError
from .span import span, span2d, span3d


@native_name("PyStackArrayIterator")
class stack_array_iterator[T, Length: int, Offset: int]:
  """C++：``PyStackArrayIterator``；``for x in buf`` 优先索引 ``for`` 内联。"""

  pass


@native
@native_name("PyStackArray")
class stack_array[T, Length: int, Offset: int]:
  """栈上 ``Length`` 个元素；``__getitem__(k)`` 为 ``Offset<=k<Offset+Length``（``T[:N]`` 时 ``Offset=0``）。"""

  @immutable
  def __bool__(self) -> bool:
    return False

  @immutable
  def __len__(self) -> int:
    return 0

  @immutable
  def __iter__(self):
    """C++：``PyStackArrayIterator``；``for x in buf`` 优先索引 ``for`` 内联。"""
    raise IndexError

  @immutable
  @overload
  def __getitem__(self, index: int) -> T:
    raise IndexError

  def __setitem__(self, index: int, value: T):
    raise IndexError

  def fill(self, value: T) -> None:
    raise IndexError

  @immutable
  def unsafe_get(self, index: int) -> T:
    raise IndexError

  def unsafe_set(self, index: int, value: T) -> None:
    raise IndexError

  @property
  @immutable
  def view(self) -> span[T]:
    return new(self.buf, len(self), 1)

  @property
  @immutable
  def buf(self) -> Pointer[T]:
    raise IndexError


@native_name("PyStackArray2D")
class stack_array2d[T, Rows: int, Cols: int, RowOff: int, ColOff: int]:
  """栈上 ``Rows×Cols`` 行主序矩阵；``T[:R, :C]`` / ``T[r0:r1, c0:c1]``。"""

  @immutable
  def __bool__(self) -> bool:
    return False

  @immutable
  @overload
  def __getitem__(self, index: (int, int)) -> T:
    raise IndexError

  def __setitem__(self, index: (int, int), value: T):
    raise IndexError

  def fill(self, value: T) -> None:
    raise IndexError

  @immutable
  def unsafe_get(self, row: int, col: int) -> T:
    raise IndexError

  def unsafe_set(self, row: int, col: int, value: T) -> None:
    raise IndexError

  @property
  @immutable
  def view(self) -> span2d[T]:
    return new(self.buf, (Rows, Cols), Cols)

  @property
  @immutable
  def buf(self) -> Pointer[T]:
    raise IndexError


@native_name("PyStackArray3D")
class stack_array3d[T, D0: int, D1: int, D2: int, O0: int, O1: int, O2: int]:
  """栈上 ``D0×D1×D2`` 行主序块；``T[:D0, :D1, :D2]`` / 子块注解。"""

  @immutable
  def __bool__(self) -> bool:
    return False

  @immutable
  @overload
  def __getitem__(self, index: (int, int, int)) -> T:
    raise IndexError

  def __setitem__(self, index: (int, int, int), value: T):
    raise IndexError

  def fill(self, value: T) -> None:
    raise IndexError

  @immutable
  def unsafe_get(self, i: int, j: int, k: int) -> T:
    raise IndexError

  def unsafe_set(self, i: int, j: int, k: int, value: T) -> None:
    raise IndexError

  @property
  @immutable
  def view(self) -> span3d[T]:
    return new(self.buf, (D0, D1, D2), (D1 * D2, D2))

  @property
  @immutable
  def buf(self) -> Pointer[T]:
    raise IndexError
