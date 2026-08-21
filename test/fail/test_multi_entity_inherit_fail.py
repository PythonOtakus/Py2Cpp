"""S1006：多实体继承 / mixin 顺序（``test/fail/``，见 ``build_fail.bat``）。"""
from py2cpp import *


class A:
  pass


class B:
  pass


class Bad(A, B):
  pass


def main():
  x: Bad = new()
  return 0
