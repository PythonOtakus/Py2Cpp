from py2cpp import *
from py2cpp.numeric.protocols import IntegralType


def onlyIntegral[T: IntegralType](x: T) -> int:
  return int(x)


def main() -> int:
  items: list[str] = []
  items.append("x")
  return onlyIntegral(items[0])
