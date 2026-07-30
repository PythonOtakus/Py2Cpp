"""``@optional`` 仅允许用于 ``@dataclass`` 字段（``test/fail/``）。"""
from py2cpp import *


@copyable
class Box:
  items: list[int] @optional = []


def main() -> int:
  b: Box = new()
  return len(b.items)
