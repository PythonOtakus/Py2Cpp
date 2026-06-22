"""``@final`` 字段类体默认与 ``__init__`` 赋值不可重复（``test/fail/``）。"""
from py2cpp import *


class Bad:
  key: int @final = 1

  def __init__(self):
    self.key = 2


def main():
  x: Bad = new()
  return 0
