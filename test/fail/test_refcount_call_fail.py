"""负向：S31 — 勿 ``RefCount()`` 清空强引用，须 ``new()``。"""
from py2cpp import *


@dataclass
@refcount
class Node:
  x: int = 0


def main() -> None:
  n: Node = new()
  n = RefCount()
