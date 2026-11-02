"""编译期条件类型别名：多分支萃取与严格变体。详见 ``docs/type-conditional.md`` §3。"""
from ..builtins import *
from ..core.never import Never

type ValOf[T, _V = ..., _W = ...] = (
  _V if T is list[_V]
  else _W if T is dict[str, _W]
  else T
)

type StrDictValueOf[T, _V = ...] = _V if T is dict[str, _V] else T

type ListElemOf[T, _V = ...] = _V if T is list[_V] else T

type ListOnly[T, _V = ...] = _V if T is list[_V] else Never
