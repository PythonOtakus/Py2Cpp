"""负向：不满足 ``AppendableType`` 的类型传入约束泛型函数应编译失败。"""
from py2cpp import *
from py2cpp.util.protocols import AppendableType


class NotAppendable:
  n: int = 0


def needAppend[T: AppendableType[int]](x: T) -> int:
  return 1


def main() -> int:
  o: NotAppendable = new()
  return needAppend(o)
