"""负向：S1101 — ``@refcount`` 类或 ``T: refcount`` 形参勿写 ``RefCount[T]``。"""
from py2cpp import *


@dataclass
@refcount
class Node:
  x: int = 0


def main() -> None:
  n: RefCount[Node] = new()
