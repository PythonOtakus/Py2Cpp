"""负向：``T: boxing`` 约束 — 非 ``@boxing`` 类型实参须 MSVC ``static_assert`` 失败。"""
from py2cpp import *


@boxing
class CellUnsafe:
  def __init__(self, n: int = 0):
    self.n: int = n


class Box[T: boxing]:
  n: int = 0


def main() -> None:
  b: Box[int] = new()
