"""负向：``repeatable=False`` 时同一目标不得重复同一注解类（``build_fail.bat``）。"""
from py2cpp import *


@annotation
class DupMeta:
  pass


class Box:
  x: int @DupMeta @DupMeta = 0


def main():
  b: Box = new()
  return b.x
