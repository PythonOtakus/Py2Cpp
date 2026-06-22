"""``@dataclass(frozen=True)`` 不可 ``T @optional``（``test/fail/``）。"""
from py2cpp import *


@dataclass(frozen=True)
class FrozenBox:
  key: int
  extra: int @optional = 99


def main():
  b: FrozenBox = new(1)
  return 0
