"""负向：``T: refcount`` 约束 — 非 ``@refcount`` 类型实参须 MSVC ``static_assert`` 失败。"""
from py2cpp import *


@dataclass
@refcount
class Node:
  x: int = 0


class Box[T: refcount]:
  item: T = new()


def main() -> None:
  b: Box[int] = new()
