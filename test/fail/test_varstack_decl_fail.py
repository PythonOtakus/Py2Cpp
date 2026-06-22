"""负向：``VarStack`` 须 ``s: VarStack = new()``（``build_fail.bat``）。"""
from py2cpp import *


@mixin
class BadMixin:
  @immutable
  def bad(self) -> Self:
    vs: VarStack
    vs.push(0.0)
    return new(*vs)


@copyable
@dataclass(eq=False, repr=False)
class BadVec(BadMixin):
  x: float64 = 0.0


def main() -> int:
  v: BadVec = new(1.0)
  r: BadVec = v.bad()
  return 0 if r else 1
