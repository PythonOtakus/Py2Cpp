"""``PyWeakRef<T>``：对齐 CPython ``weakref.ref`` 子集（``@refcount`` 对象）。"""
from ..builtins import *


@native
class WeakRef[Element: refcount]:
  """``alive`` / ``value`` 对应 ``ref() is not None`` 与解引用强引用。"""

  def __init__(self, obj: Element):
    ...

  @property
  def alive(self) -> bool:
    ...

  @property
  def value(self) -> Element:
    ...
