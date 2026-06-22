"""``@protocol`` 静态虚实现缺 ``@override``（``test/fail/``，译期 S18）。"""
from py2cpp import *


@protocol
class IParsable:
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


def try_parse[T: IParsable](s: str) -> T:
  return T.parse(s)


def main():
  w: Widget = try_parse[Widget]("1")
  return w.value
