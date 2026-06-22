"""``IterResult[YieldValue, ReturnValue]``：``__next__`` / ``send`` / ``async for`` 的 ADT。"""
from ..builtins import *
from py2cpp import native_name, union, variant


@union
@native_name("Py*")
class IterResult[YieldValue, ReturnValue]:
  @variant
  class Yield:
    value: YieldValue

  @variant
  class Return:
    return_value: ReturnValue

  @property
  def done(self) -> bool:
    match self:
      case new.Return(_):
        return True
      case new.Yield(_):
        return False

  @property
  def value(self) -> YieldValue:
    match self:
      case new.Yield(v):
        return v
      case new.Return(_):
        return YieldValue()

  @property
  def return_value(self) -> ReturnValue:
    match self:
      case new.Return(r):
        return r
      case new.Yield(_):
        return ReturnValue()


def result_done[YieldValue, ReturnValue]() -> IterResult[YieldValue, ReturnValue]:
  """翻译器内建：迭代结束，``return_value`` 为 ``ReturnValue()``。"""
  return new.Return(ReturnValue())
