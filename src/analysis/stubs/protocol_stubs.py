"""从 ``py2cpp/**/protocols.py`` AST 推导 ``ir.PROTOCOL_*`` 表。"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

from ...constant.protocol_scan import (
  PROTOCOL_PARAM_ERASE_EXCLUDE,
  PROTOCOL_SCAN_REL_PATHS,
)
from ..ir import has_named_decorator
from .paths import PY2CPP

_IMPL_ASSOC_METHODS = frozenset({
  "__iter__",
  "__next__",
  "__reversed__",
  "__aiter__",
  "__anext__",
})


def _protocol_module_paths() -> list[Path]:
  paths: list[Path] = []
  for rel in PROTOCOL_SCAN_REL_PATHS:
    path = PY2CPP.joinpath(*rel.split("/")).with_suffix(".py")
    if path.is_file():
      paths.append(path)
  return paths


def _type_param_names(node: ast.ClassDef) -> set[str]:
  names: set[str] = set()
  for tp in getattr(node, "type_params", None) or ():
    if isinstance(tp, ast.TypeVar):
      names.add(tp.name)
    elif isinstance(tp, ast.TypeVarTuple):
      names.add(tp.name)
    elif isinstance(tp, ast.ParamSpec):
      names.add(tp.name)
  return names


def _returns_iterator_of_param(ann: ast.expr | None, type_params: set[str]) -> bool:
  if ann is None:
    return False
  match ann:
    case ast.Subscript(value=ast.Name(id=base), slice=ast.Name(id=t)):
      return base in ("Iterator", "AsyncIterator") and t in type_params
    case _:
      return False


def _returns_type_param(ann: ast.expr | None, type_params: set[str]) -> bool:
  return isinstance(ann, ast.Name) and ann.id in type_params


def _returns_iter_result_of_param(ann: ast.expr | None, type_params: set[str]) -> bool:
  if ann is None:
    return False
  match ann:
    case ast.Subscript(value=ast.Name(id="IterResult"), slice=slice_):
      if isinstance(slice_, ast.Tuple) and slice_.elts:
        first = slice_.elts[0]
        return isinstance(first, ast.Name) and first.id in type_params
      return isinstance(slice_, ast.Name) and slice_.id in type_params
    case _:
      return False


def _ann_refs_any_name(ann: ast.expr | None, names: set[str]) -> bool:
  if ann is None:
    return False
  if isinstance(ann, ast.Name):
    return ann.id in names
  for child in ast.iter_child_nodes(ann):
    if _ann_refs_any_name(child, names):
      return True
  return False


def _method_arg_refs_any_name(method: ast.FunctionDef, names: set[str]) -> bool:
  for arg in method.args.args:
    if arg.arg == "self":
      continue
    if _ann_refs_any_name(arg.annotation, names):
      return True
  return False


def _method_implies_assoc_receiver(method: ast.FunctionDef, type_params: set[str]) -> bool:
  ann = method.returns
  if method.name in ("__iter__", "__reversed__", "__aiter__"):
    return _returns_iterator_of_param(ann, type_params)
  if method.name == "__next__":
    return _returns_type_param(ann, type_params)
  if method.name == "__anext__":
    return _returns_iter_result_of_param(ann, type_params)
  return False


def _has_type_alias_to_param(node: ast.ClassDef, type_params: set[str]) -> bool:
  for item in node.body:
    if isinstance(item, ast.TypeAlias) and isinstance(item.value, ast.Name):
      if item.value.id in type_params:
        return True
  return False


def _type_alias_names(node: ast.ClassDef) -> set[str]:
  names: set[str] = set()
  for item in node.body:
    if isinstance(item, ast.TypeAlias):
      names.add(item.name.id if isinstance(item.name, ast.Name) else ast.unparse(item.name))
  return names


def _single_type_param_used_as_method_arg(node: ast.ClassDef, type_params: set[str]) -> bool:
  if len(type_params) != 1:
    return False
  for item in node.body:
    if isinstance(item, ast.FunctionDef) and _method_arg_refs_any_name(item, type_params):
      return True
  return False


def _single_assoc_alias_used_as_method_arg(node: ast.ClassDef) -> bool:
  tparams = _type_param_names(node)
  if len(tparams) != 1:
    return False
  aliases = _type_alias_names(node)
  if not aliases:
    return False
  for item in node.body:
    if isinstance(item, ast.FunctionDef) and _method_arg_refs_any_name(item, aliases):
      return True
  return False


def _scan_protocol_classes() -> list[ast.ClassDef]:
  out: list[ast.ClassDef] = []
  for path in _protocol_module_paths():
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
      if isinstance(node, ast.ClassDef) and has_named_decorator(node, "protocol"):
        out.append(node)
  return out


@lru_cache(maxsize=1)
def load_protocol_param_erase() -> frozenset[str]:
  """``Comparable`` / ``Iterable[T]`` 等须 ``FuncTypeParams`` 约束的协议（非运行时擦除）。"""
  from .protocol_erase_stubs import load_protocol_runtime_erase

  names = {node.name for node in _scan_protocol_classes()}
  names -= PROTOCOL_PARAM_ERASE_EXCLUDE
  names -= load_protocol_runtime_erase()
  return frozenset(names)


@lru_cache(maxsize=1)
def load_protocol_parametric_receiver() -> frozenset[str]:
  """``Navigatable[Node]``：方括号内为关联形参，接收者另增模板形参。"""
  out: set[str] = set()
  for node in _scan_protocol_classes():
    tparams = _type_param_names(node)
    if tparams and (
      _has_type_alias_to_param(node, tparams)
      or _single_type_param_used_as_method_arg(node, tparams)
    ):
      out.add(node.name)
  return frozenset(out)


@lru_cache(maxsize=1)
def load_protocol_impl_assoc_receiver() -> frozenset[str]:
  """``Iterable[T]`` → ``Iterable_requires<Impl, T>``（双形参 SFINAE）。"""
  out: set[str] = set()
  for node in _scan_protocol_classes():
    if _single_assoc_alias_used_as_method_arg(node):
      out.add(node.name)
      continue
    tparams = _type_param_names(node)
    if not tparams:
      continue
    for item in node.body:
      if not isinstance(item, ast.FunctionDef):
        continue
      if item.name not in _IMPL_ASSOC_METHODS:
        continue
      if _method_implies_assoc_receiver(item, tparams):
        out.add(node.name)
        break
  return frozenset(out)
