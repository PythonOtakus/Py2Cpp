"""负向：不满足 ``Appendable`` 的类型传入约束泛型函数应编译失败。"""
from py2cpp import *
from py2cpp.util.protocols import Appendable


class NotAppendable:
  n: int = 0


def need_append[T: Appendable](x: T) -> int:
  return 1


def main() -> int:
  o: NotAppendable = new()
  return need_append(o)
