"""``alg`` 容器共享：赋值 ``dst = src`` 为移动语义时的 ``__moved__`` 守卫。"""
from ..builtins import *


@mixin
class AlgContainerMixin:
  @immutable
  def _ensure_active(self) -> None:
    if self.__moved__:
      raise ValueError("container used after move")

  @immutable
  def _ensure_other_active(self, other_moved: bool) -> None:
    if other_moved:
      raise ValueError("move from moved container")
