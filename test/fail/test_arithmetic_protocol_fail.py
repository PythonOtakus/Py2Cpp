"""负向：不满足 ``IntegralType`` 的类型传入 ``half`` 应编译失败。"""
from py2cpp import *
from py2cpp.numeric.protocols import IntegralType


def half[T: IntegralType](x: T) -> float:
  return x / 2


def main() -> int:
  items: list[str] = []
  items.append("x")
  return half(items[0])
