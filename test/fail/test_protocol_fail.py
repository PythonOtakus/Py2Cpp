
from py2cpp import *
from py2cpp.core.protocols import Comparable


def sorted[T: Comparable](s: list[T]) -> list[T]:
  out: list[T] = []
  out.extend(s)
  out.sort()
  return out


class NoCompare:
  value: int

  def __init__(self, value: int = 0):
    self.value = value


def main() -> int:
  items: list[NoCompare] = []
  items.append(NoCompare(1))
  ys: list[NoCompare] = sorted(items)
  return len(ys)
