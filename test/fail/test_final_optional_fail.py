"""``T @final @optional`` 不可同字段（``test/fail/``）。"""
from py2cpp import *


class Box:
  v: int @final @optional = 0


def main():
  b: Box = new()
  return 0
