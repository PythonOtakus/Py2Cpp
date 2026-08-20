"""翻译期展开 ``Mixin.iterSubclasses()`` / ``addTestsFromMixin``。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..constant.mixin import ITER_SUBCLASSES, ITER_SUBCLASSES_SORT_CONST

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator

ADD_TESTS_FROM_MIXIN = "addTestsFromMixin"
DEFAULT_HOST_METHOD = "test"


def _mixin_name_from_expr(node: ast.expr) -> str | None:
  if isinstance(node, ast.Name):
    return node.id
  return None


def _const_int_expr(value: ast.expr | None) -> int | None:
  if isinstance(value, ast.Constant) and isinstance(value.value, int):
    return value.value
  if (
    isinstance(value, ast.UnaryOp)
    and isinstance(value.op, ast.USub)
    and isinstance(value.operand, ast.Constant)
    and isinstance(value.operand.value, int)
  ):
    return -value.operand.value
  return None


def _host_static_field_int(info: ClassInfo, field: str) -> int:
  """读取宿主类体对 ``static const`` 字段的编译期整型（混入合并后）。"""
  for stmt in info.node.body:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
      continue
    target = stmt.targets[0]
    if isinstance(target, ast.Name) and target.id == field:
      v = _const_int_expr(stmt.value)
      if v is not None:
        return v
  static = info.static_class_fields.get(field)
  if static is not None:
    v = _const_int_expr(static.value)
    if v is not None:
      return v
  return 0


def _parse_sortConst_keyword(node: ast.Call) -> str | None | object:
  """解析 ``sortConst=…``；无该关键字返回 ``None``；非法则 ``_SENTINEL``。"""
  sort_key: str | None = None
  for kw in node.keywords:
    if kw.arg != ITER_SUBCLASSES_SORT_CONST:
      return _SENTINEL
    if (
      isinstance(kw.value, ast.Constant)
      and isinstance(kw.value.value, str)
    ):
      sort_key = kw.value.value
    else:
      return _SENTINEL
  return sort_key


_SENTINEL = object()


def _parse_iter_register_call(
  node: ast.expr,
) -> tuple[str, str | None] | None:
  """``Mixin.iterSubclasses()`` / ``iterSubclasses(sortConst=\"_testTag\")`` → (mixin, sort_key|None)。"""
  if not isinstance(node, ast.Call):
    return None
  func = node.func
  if not isinstance(func, ast.Attribute):
    return None
  mixin_name = _mixin_name_from_expr(func.value)
  if mixin_name is None or func.attr != ITER_SUBCLASSES or node.args:
    return None
  parsed = _parse_sortConst_keyword(node)
  if parsed is _SENTINEL:
    return None
  return mixin_name, parsed


def _parse_add_test_from_class_loop(
  node: ast.For,
) -> tuple[str, str, str, str | None] | None:
  """``for Cls in Mixin.iter_*(): suite.addTest(Cls())`` → (suite, cls_var, mixin, sort_key)。"""
  if not isinstance(node.target, ast.Name):
    return None
  parsed = _parse_iter_register_call(node.iter)
  if parsed is None:
    return None
  mixin_name, sort_key = parsed
  if len(node.body) != 1:
    return None
  stmt = node.body[0]
  if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
    return None
  call = stmt.value
  if not (
    isinstance(call.func, ast.Attribute)
    and call.func.attr == "addTest"
    and isinstance(call.func.value, ast.Name)
    and len(call.args) == 1
  ):
    return None
  arg = call.args[0]
  if not (
    isinstance(arg, ast.Call)
    and isinstance(arg.func, ast.Name)
    and arg.func.id == node.target.id
    and not arg.args
    and not arg.keywords
  ):
    return None
  return call.func.value.id, node.target.id, mixin_name, sort_key


def _parse_add_tests_from_mixin_call(
  node: ast.Expr,
) -> tuple[str, str] | None:
  """``suite.addTestsFromMixin(SomeMixin)`` → (suite_var, mixin_name)。"""
  if not isinstance(node.value, ast.Call):
    return None
  call = node.value
  if not (
    isinstance(call.func, ast.Attribute)
    and call.func.attr == ADD_TESTS_FROM_MIXIN
    and isinstance(call.func.value, ast.Name)
    and len(call.args) == 1
  ):
    return None
  mixin = _mixin_name_from_expr(call.args[0])
  if mixin is None:
    return None
  return call.func.value.id, mixin


def collect_ordered_mixin_hosts(
  tr: Translator,
  module_path: str,
  mixin_name: str,
  *,
  requireMethod: str | None = DEFAULT_HOST_METHOD,
) -> list[str]:
  """入口模块内按 ``class`` 声明顺序收集 ``mixin_name`` 宿主类名。"""
  tree = tr.module_asts.get(module_path)
  if tree is None:
    return []
  mixin_info = tr.classes.get(mixin_name)
  if mixin_info is not None and not mixin_info.is_mixin:
    return []
  out: list[str] = []
  for node in tree.body:
    if not isinstance(node, ast.ClassDef):
      continue
    info = tr.classes.get(node.name)
    if info is None or info.module_path != module_path:
      continue
    if info.is_mixin or info.is_annotation or info.is_protocol:
      continue
    if mixin_name not in info.bases:
      continue
    if requireMethod is not None and requireMethod not in info.methods:
      continue
    out.append(node.name)
  return out


def sort_mixin_hosts(
  tr: Translator,
  hosts: list[str],
  sort_key: str,
) -> list[str]:
  """按宿主 ``static const`` 字段名（与参数同名）排序；同键保持声明顺序（稳定排序）。"""
  field = sort_key
  indexed: list[tuple[int, int, str]] = []
  for order, name in enumerate(hosts):
    info = tr.classes.get(name)
    key = _host_static_field_int(info, field) if info is not None else 0
    indexed.append((key, order, name))
  indexed.sort()
  return [name for _key, _order, name in indexed]


def _make_add_test_stmts(suite_var: str, class_names: list[str]) -> list[ast.stmt]:
  return [
    ast.Expr(
      value=ast.Call(
        func=ast.Attribute(
          value=ast.Name(id=suite_var, ctx=ast.Load()),
          attr="addTest",
          ctx=ast.Load(),
        ),
        args=[
          ast.Call(
            func=ast.Name(id=name, ctx=ast.Load()),
            args=[],
            keywords=[],
          ),
        ],
        keywords=[],
      ),
    )
    for name in class_names
  ]


def _expand_main_body(tr: Translator, body: list[ast.stmt]) -> list[ast.stmt]:
  out: list[ast.stmt] = []
  for stmt in body:
    if isinstance(stmt, ast.For):
      parsed = _parse_add_test_from_class_loop(stmt)
      if parsed is not None:
        suite_var, _, mixin_name, sort_key = parsed
        hosts = collect_ordered_mixin_hosts(tr, tr.entry_module_path, mixin_name)
        if sort_key is not None:
          hosts = sort_mixin_hosts(tr, hosts, sort_key)
        if hosts:
          out.extend(_make_add_test_stmts(suite_var, hosts))
          continue
    if isinstance(stmt, ast.Expr):
      parsed = _parse_add_tests_from_mixin_call(stmt)
      if parsed is not None:
        suite_var, mixin_name = parsed
        hosts = collect_ordered_mixin_hosts(tr, tr.entry_module_path, mixin_name)
        if hosts:
          out.extend(_make_add_test_stmts(suite_var, hosts))
          continue
    out.append(stmt)
  return out


def expand_test_discovery(tr: Translator) -> None:
  """展开入口 ``main()`` 中的测试类自动注入（须在 ``expand_mixins`` 之后）。"""
  for mp, func in tr.module_functions:
    if mp != tr.entry_module_path or func.name != "main":
      continue
    func.body = _expand_main_body(tr, func.body)
