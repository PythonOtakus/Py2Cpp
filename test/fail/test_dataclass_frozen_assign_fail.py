"""``@dataclass(frozen=True)`` 字段不可 ``assign``（``test/fail/``）。"""
from py2cpp import *


@dataclass(frozen=True)
class FrozenBox:
  v: int


def main():
  b: FrozenBox = new(1)
  b.assign(v=2)
  return 0
