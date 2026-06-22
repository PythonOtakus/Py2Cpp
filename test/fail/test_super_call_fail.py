"""负向：``super()`` 要求基类 ``__call__``。"""
from py2cpp import *


class Base:
  n: int = 0

  @virtual
  def inc(self) -> int:
    return self.n


class Derived(Base):
  @override
  def inc(self) -> int:
    return super().inc() + 1
