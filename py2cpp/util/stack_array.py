"""栈定长数组：一维 ``PyStackArray``、二维 ``PyStackArray2D``、三维 ``PyStackArray3D``。

``Element[:N]`` / ``Element[:R,:C]`` / ``Element[:D0,:D1,:D2]`` 为拥有存储；子区间注解为绝对下标。``buf[i:j]`` / ``grid[r0:r1,c0:c1]`` → 堆拷贝。
"""
from ..builtins import *
from ..core.exceptions import IndexError
from .span import span, span2d, span3d


class StackArrayIterator[Element, Length: int, Offset: int]:
  """C++：``PyStackArrayIterator``；``for x in buf`` 优先索引 ``for`` 内联。"""

  pass


@native
class StackArray[Element, Length: int, Offset: int]:
  """栈上 ``Length`` 个元素；``__getitem__(k)`` 为 ``Offset<=k<Offset+Length``（``Element[:N]`` 时 ``Offset=0``）。"""

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
  def __getitem__(self, index: int) -> Element:
    raise IndexError

  def __setitem__(self, index: int, value: Element):
    raise IndexError

  def fill(self, value: Element) -> None:
    raise IndexError

  @immutable
  def unsafeGet(self, index: int) -> Element:
    raise IndexError

  def unsafeSet(self, index: int, value: Element) -> None:
    raise IndexError

  @property
  @immutable
  def view(self) -> span[Element]:
    raise IndexError


@native_name("PyStackArray2D")
class StackArray2d[Element, Rows: int, Cols: int, RowOff: int, ColOff: int]:
  """栈上 ``Rows×Cols`` 行主序矩阵；``Element[:R, :C]`` / ``Element[r0:r1, c0:c1]``。"""

  @immutable
  def __bool__(self) -> bool:
    return False

  @immutable
  @overload
  def __getitem__(self, index: (int, int)) -> Element:
    raise IndexError

  def __setitem__(self, index: (int, int), value: Element):
    raise IndexError

  def fill(self, value: Element) -> None:
    raise IndexError

  @immutable
  def unsafeGet(self, row: int, col: int) -> Element:
    raise IndexError

  def unsafeSet(self, row: int, col: int, value: Element) -> None:
    raise IndexError

  @property
  @immutable
  def view(self) -> span2d[Element]:
    raise IndexError


@native_name("PyStackArray3D")
class StackArray3d[Element, Dim0: int, Dim1: int, Dim2: int, Off0: int, Off1: int, Off2: int]:
  """栈上 ``D0×D1×D2`` 行主序块；``Element[:D0, :D1, :D2]`` / 子块注解。"""

  @immutable
  def __bool__(self) -> bool:
    return False

  @immutable
  @overload
  def __getitem__(self, index: (int, int, int)) -> Element:
    raise IndexError

  def __setitem__(self, index: (int, int, int), value: Element):
    raise IndexError

  def fill(self, value: Element) -> None:
    raise IndexError

  @immutable
  def unsafeGet(self, i: int, j: int, k: int) -> Element:
    raise IndexError

  def unsafeSet(self, i: int, j: int, k: int, value: Element) -> None:
    raise IndexError

  @property
  @immutable
  def view(self) -> span3d[Element]:
    raise IndexError
