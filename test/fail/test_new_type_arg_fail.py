"""负向：``new(类型/类名)`` 须在翻译期失败。"""
from py2cpp import *


def main() -> None:
  xs: list[int] = new(list[int])
