"""RefCount[T]：引用计数智能指针（类似 std::shared_ptr，自实现，无 STL）。

``@refcount`` 装饰器见 ``py2cpp`` 包根 ``__init__.py``。
"""
from ..builtins import *


class _RefCountControl:
  count: int


@native
class RefCount[Element]:
  """持有 T* 与控制块；通过 operator-> 访问 T。"""

  def __init__(self):
    ...


def makeRefCount[Element](*args) -> RefCount[Element]:
  """C++ ``makeRefCount<T>(...)``：控制块与对象同块分配。"""
  return new()
