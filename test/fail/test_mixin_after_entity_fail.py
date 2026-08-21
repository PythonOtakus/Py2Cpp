"""S1006：mixin 须在实体基类之前（``test/fail/``）。"""
from py2cpp import *


class Base:
  pass


@mixin
class IncMixin:
  n: int = 0


class Bad(Base, IncMixin):
  pass


def main():
  h: Bad = new()
  return h.n
