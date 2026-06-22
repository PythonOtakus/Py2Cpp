"""``getattr`` / ``setattr`` / ``hasattr`` 编译期成员解析（零运行时反射）。"""
from __future__ import annotations

import ast
import copy
import re

_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def fold_joined_str(node: ast.expr) -> str | None:
  """常量 ``JoinedStr`` / ``f"a{b}c"``（``b`` 已为常量）→ 字符串。"""
  if isinstance(node, ast.Constant) and isinstance(node.value, str):
    return node.value
  if not isinstance(node, ast.JoinedStr):
    return None
  parts: list[str] = []
  for val in node.values:
    if isinstance(val, ast.Constant) and isinstance(val.value, str):
      parts.append(val.value)
      continue
    if isinstance(val, ast.FormattedValue):
      if isinstance(val.value, ast.Constant) and isinstance(val.value.value, str):
        parts.append(val.value.value)
        continue
    return None
  return "".join(parts)


def static_field_name(attr: ast.expr) -> str | None:
  """字段名在编译期已知时返回标识符，否则 ``None``。"""
  match attr:
    case ast.Constant(value=str(name)):
      return name if _FIELD_NAME_RE.match(name) else None
    case ast.Call(func=ast.Name(id="str"), args=[ast.Constant(value=str(name))], keywords=[]):
      return name if _FIELD_NAME_RE.match(name) else None
    case _:
      return None


def _field_allowed(name: str, known_fields: frozenset[str] | None) -> bool:
  if not _FIELD_NAME_RE.match(name):
    return False
  if known_fields is None:
    return True
  return name in known_fields


def _const_compare_result(left: ast.expr, op: ast.cmpop, right: ast.expr) -> bool | None:
  """两常量比较 → ``bool``；非常量则 ``None``。"""
  if not isinstance(left, ast.Constant) or not isinstance(right, ast.Constant):
    return None
  lv, rv = left.value, right.value
  if isinstance(op, ast.Eq):
    return lv == rv
  if isinstance(op, ast.NotEq):
    return lv != rv
  return None


class StaticReflectFolder(ast.NodeTransformer):
  """将 ``getattr``/``setattr``/``hasattr`` 折叠为 ``ast.Attribute`` / 常量布尔。"""

  def __init__(
    self,
    known_fields: frozenset[str] | None = None,
    *,
    known_methods: frozenset[str] | None = None,
    require_known_member: bool = False,
  ):
    self.known_fields = known_fields
    self.known_methods = known_methods
    self.require_known_member = require_known_member

  def _resolve_member_name(self, attr: ast.expr) -> str | None:
    name = static_field_name(attr)
    if name is None:
      name = fold_joined_str(attr)
    if name is None or not _FIELD_NAME_RE.match(name):
      return None
    in_fields = self.known_fields is not None and name in self.known_fields
    in_methods = self.known_methods is not None and name in self.known_methods
    if self.require_known_member and self.known_fields is not None:
      if not in_fields and not in_methods:
        raise ValueError(f"编译期成员不存在: {name!r}")
    if in_fields or in_methods:
      return name
    if self.known_fields is None and self.known_methods is None:
      return name if _field_allowed(name, None) else None
    return None

  def _resolve_field(self, attr: ast.expr) -> str | None:
    name = self._resolve_member_name(attr)
    if name is None:
      return None
    if self.known_fields is not None and name not in self.known_fields:
      if self.known_methods is not None and name in self.known_methods:
        return name
      if self.known_methods is None:
        return None
    return name

  def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.expr:
    self.generic_visit(node)
    folded = fold_joined_str(node)
    if folded is not None:
      return ast.Constant(value=folded)
    return node

  def visit_Compare(self, node: ast.Compare) -> ast.expr:
    self.generic_visit(node)
    if len(node.ops) == 1 and len(node.comparators) == 1:
      folded = _const_compare_result(node.left, node.ops[0], node.comparators[0])
      if folded is not None:
        return ast.Constant(value=folded)
    return node

  def visit_IfExp(self, node: ast.IfExp) -> ast.expr:
    self.generic_visit(node)
    if isinstance(node.test, ast.Constant) and isinstance(node.test.value, bool):
      return copy.deepcopy(node.body if node.test.value else node.orelse)
    return node

  def visit_Call(self, node: ast.Call) -> ast.AST:
    self.generic_visit(node)
    if not isinstance(node.func, ast.Name):
      return node
    if node.func.id == "hasattr" and len(node.args) == 2:
      name = self._resolve_member_name(node.args[1])
      if name is not None and (
        self.known_fields is not None or self.known_methods is not None
      ):
        exists = (self.known_fields is not None and name in self.known_fields) or (
          self.known_methods is not None and name in self.known_methods
        )
        return ast.Constant(value=exists)
    if node.func.id == "getattr" and len(node.args) == 2:
      member = self._resolve_member_name(node.args[1])
      if member is not None:
        return ast.Attribute(
          value=copy.deepcopy(node.args[0]),
          attr=member,
          ctx=ast.Load(),
        )
    return node

  def visit_Expr(self, node: ast.Expr) -> ast.stmt:
    if (
      isinstance(node.value, ast.Call)
      and isinstance(node.value.func, ast.Name)
      and node.value.func.id == "setattr"
      and len(node.value.args) == 3
    ):
      field = self._resolve_field(node.value.args[1])
      if field is not None:
        return ast.Assign(
          targets=[
            ast.Attribute(
              value=copy.deepcopy(node.value.args[0]),
              attr=field,
              ctx=ast.Store(),
            )
          ],
          value=copy.deepcopy(node.value.args[2]),
        )
    node.value = self.visit(node.value)
    return node


def fold_static_reflect(
  node: ast.FunctionDef | ast.AsyncFunctionDef,
  *,
  known_fields: frozenset[str] | None = None,
  known_methods: frozenset[str] | None = None,
  require_known_member: bool = False,
) -> None:
  folder = StaticReflectFolder(
    known_fields,
    known_methods=known_methods,
    require_known_member=require_known_member,
  )
  node.body = [folder.visit(stmt) for stmt in node.body]
  ast.fix_missing_locations(node)


def fold_static_reflect_tree(
  tree: ast.AST,
  *,
  known_fields: frozenset[str] | None = None,
  known_methods: frozenset[str] | None = None,
  require_known_member: bool = False,
) -> ast.AST:
  return StaticReflectFolder(
    known_fields,
    known_methods=known_methods,
    require_known_member=require_known_member,
  ).visit(tree)
