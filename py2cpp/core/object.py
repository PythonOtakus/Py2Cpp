"""非泛型对象协议（可选动态多态；泛型容器不继承此类）"""

from ..builtins import *
from .exceptions import TypeError


class object:
  def __bool__(self) -> bool:
    return True

  def __len__(self) -> int:
    raise TypeError("object has no len()")

  def __iter__(self):
    raise TypeError("object is not iterable")
