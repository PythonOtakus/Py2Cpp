"""``Result[OkValue, ErrValue]``：``@noexcept`` 函数的 ADT（``Ok`` / ``Err``）。"""
from ..builtins import *
from py2cpp import native_name, property, union, variant


@union
@native_name("Py*")
class Result[OkValue, ErrValue]:
  @variant
  class Ok:
    value: OkValue

  @variant
  class Err:
    error: ErrValue

  @property
  def ok(self) -> bool:
    match self:
      case new.Ok(_):
        return True
      case new.Err(_):
        return False

  @property
  def value(self) -> OkValue:
    match self:
      case new.Ok(v):
        return v
      case new.Err(e):
        raise e


type OkOf[T, _O = ...] = _O if T is Result[_O, ...] else T

type ErrOf[T, _E = ...] = _E if T is Result[..., _E] else T
