"""util 容器共享：赋值 ``dst = src`` 为移动语义时的 ``__moved__`` 守卫。"""
from ..builtins import *
from ..core.exceptions import ValueError


@mixin
class ContainerMixin:
  @immutable
  def _ensureActive(self) -> None:
    if self.__moved__:
      raise ValueError("container used after move")

  @immutable
  def _ensureOtherActive(self, other: Self) -> None:
    if other.__moved__:
      raise ValueError("move from moved container")
