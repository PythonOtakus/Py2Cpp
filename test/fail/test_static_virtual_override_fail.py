"""``@protocol`` 静态虚实现缺 ``@override``（``test/fail/``，译期 S18）。"""
from py2cpp import *


@protocol
class IParsableType:
  @staticmethod
  @abstract
  def parse(s: str) -> Self: ...


class Widget:
  value: int

  def __init__(self, v: int = 0):
    self.value = v

  @staticmethod
  def parse(s: str) -> Self:
    return new(int(s))


def tryParse[T: IParsableType](s: str) -> T:
  return T.parse(s)


def main():
  w: Widget = tryParse[Widget]("1")
  return w.value
