"""tuple[*Args]：零成本可变参数元组（C++：PyTuple<Args...>，由 templates/util/tuple 镜像生成）"""
from ..builtins import *
from ..core.exceptions import IndexError


@native_name("PyTupleIterator")
class tuple_iterator[*Args]:
  """C++ 迭代器类型名；``for x in t`` 在常量下标路径上内联， seldom 显式构造。"""

  pass


@native
@native_name("PyTuple")
class tuple[*Args]:
  """元素由 PyTuple<T...>(a, b, ...) 构造；下标 t[i] 在编译期常量 i 时映射为 get<i>()。"""

  __repr__ = __str__

  @immutable
  def __bool__(self) -> bool:
    return False

  @immutable
  def __str__(self) -> str:
    return "()"

  @immutable
  def __len__(self) -> int:
    return 0

  @immutable
  def __getitem__(self, index: int):
    raise IndexError
