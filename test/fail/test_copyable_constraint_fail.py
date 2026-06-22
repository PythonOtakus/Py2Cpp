"""负向：``T: copyable`` 约束 — 非 ``@copyable`` 类型实参须 MSVC ``static_assert`` 失败。"""
from py2cpp import *


class Node:
  v: int = 0


class Box[T: copyable]:
  n: int = 0


def main() -> None:
  b: Box[Node] = new()
