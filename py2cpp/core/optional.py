"""``Optional[Value]``：``Value | None`` 的 ADT（``Some`` / ``None_``）。"""
from ..builtins import *
from py2cpp import native_name, property, union, variant


@union
@native_name("Py*")
class Optional[Value]:
  @variant
  class None_:
    pass

  @variant
  class Some:
    value: Value

  @property
  def value(self) -> Value:
    match self:
      case None:
        raise ValueError("Optional has no value")
      case v:
        return v
