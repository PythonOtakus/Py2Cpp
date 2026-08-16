"""负向：``@staticproperty`` 不得写 ``Cls.prop()``，须 ``Cls.prop``。"""
from py2cpp import *


@copyable
class Counter:
  @staticproperty
  def value() -> int:
    return 0


def readWrong() -> int:
  return Counter.value()
  # expect NotImplementedError at translate


def main() -> int:
  return readWrong()
