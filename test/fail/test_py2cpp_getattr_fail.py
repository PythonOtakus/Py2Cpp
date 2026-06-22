"""负向：``PY2CPP_GETATTR`` 在不存在成员上应 ``static_assert`` 失败。"""
from py2cpp import *


@dataclass
@copyable
class Box:
  x: int = 0


def read_missing(box) -> int:
  return box.missing


def main() -> int:
  b: Box = new()
  return read_missing(b)
