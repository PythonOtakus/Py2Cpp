from py2cpp import *
from py2cpp.core.protocols import Integral


def only_integral[T: Integral](x: T) -> int:
  return int(x)


def main() -> int:
  items: list[str] = []
  items.append("x")
  return only_integral(items[0])
