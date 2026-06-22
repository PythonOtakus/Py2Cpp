"""``@final`` 类不可继承（``test/fail/``）。"""
from py2cpp import *


@final
class Sealed:
  pass


class Bad(Sealed):
  pass


def main():
  x: Bad = new()
  return 0
