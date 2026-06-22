"""负向：``VarStack`` 声明与使用须在同一作用域（``build_fail.bat``）。"""
from py2cpp import *


@mixin
class BadMixin:
  @immutable
  def leak(self, cond: bool) -> Self:
    if cond:
      vs: VarStack = new()
      for f in Self.iter_fields(public_only=True):
        vs.push(getattr(self, f))
    return new(*vs)


@copyable
@dataclass(eq=False, repr=False)
class BadVec(BadMixin):
  x: float64 = 0.0
  y: float64 = 0.0


def main() -> int:
  v: BadVec = new(1.0, 2.0)
  r: BadVec = v.leak(True)
  return 0 if r else 1
