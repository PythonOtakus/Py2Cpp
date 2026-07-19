"""util 容器共享：赋值 ``dst = src`` 为移动语义时的 ``__moved__`` 守卫。"""
from ..builtins import *
from ..core.exceptions import ValueError


@mixin
class ContainerMixin:
  @immutable
  def _ensure_active(self) -> None:
    if self.__moved__:
      raise ValueError("container used after move")

  @immutable
  def _ensure_other_active(self, other: Self) -> None:
    if other.__moved__:
      raise ValueError("move from moved container")
