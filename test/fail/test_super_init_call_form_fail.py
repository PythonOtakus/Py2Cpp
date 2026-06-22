"""负向：``super().__init__(...)`` 须写 ``super.__init__(...)``。"""
from py2cpp import *


class Base:
  def __call__(self) -> Self:
    return self

  def __init__(self, n: int = 0):
    self.n = n


class Derived(Base):
  def __init__(self, n: int = 0):
    super().__init__(n)
