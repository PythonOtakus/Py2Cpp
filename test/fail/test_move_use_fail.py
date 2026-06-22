"""负向：移动后使用应在翻译期失败（``test/fail/``，见 ``build_fail.bat``）。"""
from py2cpp import *


def main():
  a: list[int] = [1, 2]
  b: list[int] = a
  return len(a)
