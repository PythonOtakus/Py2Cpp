"""不可覆盖 ``@final`` 方法（``test/fail/``）。"""
from py2cpp import *


class Base:
  @final
  def hook(self) -> int:
    return 1


class Child(Base):
  @override
  def hook(self) -> int:
    return 2


def main():
  c: Child = new()
  return c.hook()
