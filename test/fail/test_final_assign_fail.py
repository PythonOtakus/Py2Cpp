"""``assign`` / ``new(kw=…)`` 不可写 ``@final`` 字段（``test/fail/``）。"""
from py2cpp import *


class Box:
  v: int @final

  def __init__(self, v: int):
    self.v = v


def main():
  b: Box = new(1)
  b.assign(v=2)
  return 0
