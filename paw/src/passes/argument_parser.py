"""带 ``*ArgMeta`` 的 dataclass：校验；须显式继承 ``ArgumentParserMixin``。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, has_named_decorator, is_optional_type_annotation
from ..translation_error import raise_translation_error

if TYPE_CHECKING:
  from ..translator import Translator

_POS = "PosArgMeta"
_OPT = "OptArgMeta"
_FLAG = "FlagArgMeta"
_SKIP_NAMES = frozenset({_POS, _OPT, _FLAG, "ArgumentParserMixin", "ArgParserIO"})
_MIXIN = "ArgumentParserMixin"


@dataclass
class _ArgField:
  name: str
  kind: str
  type_name: str
  default: ast.expr | None
  meta: ast.expr
  node: ast.AST


def _meta_name(expr: ast.expr) -> str | None:
  if isinstance(expr, ast.Name):
    return expr.id
  if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name):
    return expr.func.id
  return None


def _ann_base_and_metas(ann: ast.expr) -> tuple[ast.expr, list[ast.expr]]:
  metas: list[ast.expr] = []
  cur = ann
  while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.MatMult):
    metas.append(cur.right)
    cur = cur.left
  return cur, metas


def _meta_for(metas: list[ast.expr], want: str) -> ast.expr | None:
  for m in metas:
    if _meta_name(m) == want:
      return m
  return None


def _meta_kw(meta: ast.expr, key: str) -> ast.expr | None:
  if not isinstance(meta, ast.Call):
    return None
  for kw in meta.keywords:
    if kw.arg == key:
      return kw.value
  return None


def _const_str(expr: ast.expr | None) -> str:
  if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
    return expr.value
  return ""


def _const_bool(expr: ast.expr | None) -> bool:
  return isinstance(expr, ast.Constant) and expr.value is True


def _snake_to_kebab(name: str) -> str:
  return name.replace("_", "-")


def _type_name(ann: ast.expr) -> str:
  if isinstance(ann, ast.Name):
    return ann.id
  return ast.unparse(ann)


def _error(
  tr: Translator,
  node: ast.AST | None,
  message: str,
  *,
  module_path: str | None = None,
) -> None:
  raise_translation_error(tr, node, message, module_path=module_path)


def _collect_arg_fields(tr: Translator, info: ClassInfo) -> list[_ArgField]:
  out: list[_ArgField] = []
  longs: dict[str, str] = {}
  shorts: dict[str, str] = {}
  for stmt in info.node.body:
    if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
      continue
    name = stmt.target.id
    if name.startswith("_"):
      continue
    base, metas = _ann_base_and_metas(stmt.annotation)
    kinds = [k for k in (_POS, _OPT, _FLAG) if _meta_for(metas, k) is not None]
    if not kinds:
      continue
    if len(kinds) > 1:
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: 同一字段至多一个 PosArgMeta/OptArgMeta/FlagArgMeta",
        module_path=info.module_path,
      )
    kind = kinds[0]
    meta = _meta_for(metas, kind)
    assert meta is not None
    tip = _type_name(base)
    if kind == _FLAG and tip != "bool":
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: FlagArgMeta 仅允许 bool，得到 {tip}",
        module_path=info.module_path,
      )
    if kind == _OPT and tip == "bool":
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: OptArgMeta 不能标在 bool（请用 FlagArgMeta）",
        module_path=info.module_path,
      )
    default = stmt.value
    if kind == _POS and default is not None:
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: 首版 PosArgMeta 不支持默认值",
        module_path=info.module_path,
      )
    if kind == _OPT and default is None:
      if not is_optional_type_annotation(stmt.annotation):
        _error(
          tr,
          stmt,
          f"{info.name}.{name}: OptArgMeta 须有默认值或 @optional",
          module_path=info.module_path,
        )
    long_name = "--" + _snake_to_kebab(name)
    if kind == _FLAG and _const_bool(_meta_kw(meta, "negated")):
      long_name = "--no-" + _snake_to_kebab(name)
    if long_name in longs:
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: 长选项 {long_name} 与 {longs[long_name]} 冲突",
        module_path=info.module_path,
      )
    longs[long_name] = name
    short = _const_str(_meta_kw(meta, "short"))
    if short:
      if not (len(short) == 2 and short[0] == "-"):
        _error(
          tr,
          stmt,
          f"{info.name}.{name}: short 须形如 -x，得到 {short!r}",
          module_path=info.module_path,
        )
      if short in shorts:
        _error(
          tr,
          stmt,
          f"{info.name}.{name}: 短选项 {short} 与 {shorts[short]} 冲突",
          module_path=info.module_path,
        )
      shorts[short] = name
    out.append(
      _ArgField(
        name=name,
        kind=kind,
        type_name=tip,
        default=default,
        meta=meta,
        node=stmt,
      )
    )
  return out


def _has_parser_mixin(info: ClassInfo, classes: dict[str, ClassInfo]) -> bool:
  seen: set[str] = set()
  stack = list(info.bases)
  while stack:
    name = stack.pop()
    if name == _MIXIN:
      return True
    if name in seen:
      continue
    seen.add(name)
    base = classes.get(name)
    if base is not None:
      stack.extend(base.bases)
  return False


def _is_parse_subscript_call(node: ast.expr) -> ast.Call | None:
  if not isinstance(node, ast.Call):
    return None
  func = node.func
  if not isinstance(func, ast.Subscript):
    return None
  if not isinstance(func.value, ast.Attribute) or func.value.attr != "parse":
    return None
  recv = func.value.value
  if isinstance(recv, ast.Name):
    if recv.id != _MIXIN:
      return None
  elif isinstance(recv, ast.Attribute) and recv.attr == _MIXIN:
    pass
  else:
    return None
  return node


class _RejectParseSubscript(ast.NodeVisitor):
  def __init__(self, tr: Translator):
    self.tr = tr

  def visit_Call(self, node: ast.Call) -> None:
    if _is_parse_subscript_call(node) is not None:
      _error(
        self.tr,
        node,
        "请写 Host.parse(...) / new.parse(...)，勿 ArgumentParserMixin.parse[T]",
      )
    self.generic_visit(node)


def expand_argument_parser(tr: Translator) -> None:
  """校验 ``*ArgMeta``；须显式继承 mixin。``parse`` 由 mixin 反射展开。"""
  for info in list(tr.classes.values()):
    if info.name in _SKIP_NAMES or info.is_mixin or info.is_annotation:
      continue
    fields = _collect_arg_fields(tr, info)
    if not fields:
      continue
    if not has_named_decorator(info.node, "dataclass"):
      _error(
        tr,
        info.node,
        f"{info.name}: 带 PosArgMeta/OptArgMeta/FlagArgMeta 的类须为 @dataclass",
        module_path=info.module_path,
      )
    if not _has_parser_mixin(info, tr.classes):
      _error(
        tr,
        info.node,
        f"{info.name}: 带 PosArgMeta/OptArgMeta/FlagArgMeta 的类须继承 ArgumentParserMixin",
        module_path=info.module_path,
      )

  rejector = _RejectParseSubscript(tr)
  for tree in tr.module_asts.values():
    rejector.visit(tree)
  for info in tr.classes.values():
    for method in list(info.methods.values()):
      rejector.visit(method)
    for overloads in info.method_overloads.values():
      for method in overloads:
        rejector.visit(method)
    for init in info.inits:
      rejector.visit(init)
  for _mp, fn in tr.module_functions:
    rejector.visit(fn)
