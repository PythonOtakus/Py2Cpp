"""负向：``PY2CPP_CALL`` 在不存在方法上应 ``static_assert`` 失败。"""
from py2cpp import *


@dataclass
@copyable
class Box:
  x: int = 0


def call_missing(box) -> int:
  return box.bump()


def main() -> int:
  b: Box = new()
  return call_missing(b)
