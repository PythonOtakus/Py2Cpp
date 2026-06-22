"""负向：``@staticproperty`` 不得写 ``Cls.prop()``，须 ``Cls.prop``。"""
from py2cpp import *


@copyable
class Counter:
  @staticproperty
  def value() -> int:
    return 0


def read_wrong() -> int:
  return Counter.value()
  # expect NotImplementedError at translate


def main() -> int:
  return read_wrong()
