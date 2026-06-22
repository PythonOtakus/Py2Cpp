"""``@copyable``：``c = b`` 翻译为 ``c.__copy__(b)``；与 ``__copy__`` 联用生成复制构造/赋值。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, has_named_decorator

if TYPE_CHECKING:
  from ..translator import Translator


def _copy_init(info: ClassInfo) -> ast.FunctionDef | None:
  for init in info.inits:
    params = [a for a in init.args.args if a.arg not in ("self", "cls")]
    if len(params) != 1:
      continue
    ann = params[0].annotation
    if isinstance(ann, ast.Name) and ann.id in (info.name, "Self"):
      return init
  return None


def expand_copyable(tr: Translator) -> None:
  """标记 ``@copyable`` 类；``@union`` 隐式可复制。复制赋值体由翻译器生成。"""
  for info in tr.classes.values():
    info.is_copyable = has_named_decorator(info.node, "copyable") or info.is_union
