"""``expand_lazy_params``：``default: V @lazy = expr`` → ``= None`` + 元数据。"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from ..analysis.lazy_param import is_lazy_type_annotation

if TYPE_CHECKING:
  from ..translator import Translator


def expand_lazy_params(tr: "Translator") -> None:
  """惰性形参默认值改为 ``None``；非 ``None`` 表达式存入 ``lazy_param_default_exprs``。"""
  for _mp, func in list(tr.module_functions):
    _expand_lazy_defaults_on_function(func, tr)
  for info in tr.classes.values():
    for method in info.methods.values():
      _expand_lazy_defaults_on_function(method, tr)


def _expand_lazy_defaults_on_function(func: ast.FunctionDef, tr: "Translator") -> None:
  args = func.args.args
  defaults = list(func.args.defaults or [])
  n = len(defaults)
  if n == 0:
    return
  pos_args = args[-n:]
  stored: dict[str, ast.expr] = {}
  new_defaults: list[ast.expr] = []
  for arg, default in zip(pos_args, defaults):
    if not is_lazy_type_annotation(arg.annotation):
      new_defaults.append(default)
      continue
    if isinstance(default, ast.Constant) and default.value is None:
      new_defaults.append(default)
      continue
    stored[arg.arg] = copy.deepcopy(default)
    new_defaults.append(ast.Constant(value=None, lineno=default.lineno, col_offset=default.col_offset))
  if stored:
    tr.lazy_param_default_exprs[id(func)] = stored
  if stored or len(new_defaults) == n:
    func.args.defaults = new_defaults
