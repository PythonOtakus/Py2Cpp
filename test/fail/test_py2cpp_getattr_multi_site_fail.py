"""负向：同一函数两处 ``PY2CPP_GETATTR`` 应各自带语句行号的 ``static_assert``。"""
from py2cpp import *


@dataclass
@copyable
class Box:
  x: int = 0


def read_two(box) -> int:
  a: int = box.missing_a
  return box.missing_b


def main() -> int:
  b: Box = new()
  return read_two(b)
