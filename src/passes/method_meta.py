"""``Self.iter_methods`` / ``Self.iter_methods[Ann]`` 译期展开。"""
from __future__ import annotations

import ast
import copy

from ..analysis.ir import ClassInfo, decorator_string_arg, has_named_decorator
from .annotation_options import IterReflectOptions, filter_iter_names
from .match_case import _clone_body_replace_names, _simplify_const_ifs
from .static_reflect import fold_static_reflect


def _host_method_names_in_order(
  host: ClassInfo,
  classes: dict[str, ClassInfo],
  *,
  public_only: bool,
  mro: bool,
  glob: str | None = None,
) -> list[str]:
  from .annotation_options import walk_entity_bases

  def names_on(ci: ClassInfo) -> list[str]:
    out: list[str] = []
    for stmt in ci.node.body:
      if not isinstance(stmt, ast.FunctionDef):
        continue
      if stmt.name in ("__init__",):
        continue
      if public_only and stmt.name.startswith("_"):
        continue
      out.append(stmt.name)
    return out

  result = names_on(host)
  if not mro:
    return filter_iter_names(result, glob)
  seen = set(result)
  host_methods = set(host.methods)
  for bi in walk_entity_bases(host, classes):
    for m in names_on(bi):
      if m in seen:
        continue
      if m in host_methods:
        continue
      seen.add(m)
      result.append(m)
  return filter_iter_names(result, glob)


def annotated_methods(
  host: ClassInfo,
  annotation_class: str,
  classes: dict[str, ClassInfo] | None = None,
  *,
  public_only: bool = False,
  mro: bool = False,
  glob: str | None = None,
) -> list[str]:
  """类体内带 ``@annotation_class`` 的方法名（声明序）。"""
  from .annotation_options import annotation_options_for, walk_entity_bases

  def names_on(ci: ClassInfo) -> list[str]:
    out: list[str] = []
    for stmt in ci.node.body:
      if not isinstance(stmt, ast.FunctionDef):
        continue
      if public_only and stmt.name.startswith("_"):
        continue
      if has_named_decorator(stmt, annotation_class):
        out.append(stmt.name)
    return out

  out = names_on(host)
  seen = set(out)
  if mro and classes is not None:
    opts = annotation_options_for(classes, annotation_class)
    if opts is not None and opts.inheritable:
      host_methods = set(host.methods)
      for bi in walk_entity_bases(host, classes):
        for m in names_on(bi):
          if m in seen:
            continue
          if m in host_methods:
            continue
          out.append(m)
          seen.add(m)
  return filter_iter_names(out, glob)


def method_meta_label(host: ClassInfo, method_name: str, meta_name: str) -> str:
  """``@Meta("…")`` 单串实参；无参或裸 ``@Meta`` → 方法名。"""
  method = host.methods.get(method_name)
  if method is None:
    return method_name
  label = decorator_string_arg(method, meta_name)
  if label:
    return label
  return method_name


def _is_iter_methods_call(node: ast.expr) -> bool:
  return (
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and isinstance(node.func.value, ast.Name)
    and node.func.value.id == "Self"
    and node.func.attr == "iter_methods"
  )


def _parse_iter_methods_options(node: ast.expr):
  from .annotation_options import parse_self_iter_call_options

  if not _is_iter_methods_call(node):
    return None
  return parse_self_iter_call_options(
    node,
    allowed=frozenset({"public_only", "mro", "glob"}),
    label="Self.iter_methods",
  )


def _parse_iter_methods_public_only(node: ast.expr) -> bool | None:
  opts = _parse_iter_methods_options(node)
  if opts is None:
    return None
  return opts.public_only


def _iter_methods_subscript_annotation(iter_node: ast.expr) -> str | None:
  match iter_node:
    case ast.Call(
      func=ast.Subscript(
        value=ast.Attribute(value=ast.Name(id="Self"), attr="iter_methods"),
        slice=sl,
      ),
    ):
      if isinstance(sl, ast.Name):
        return sl.id
      if isinstance(sl, ast.Call) and isinstance(sl.func, ast.Name):
        return sl.func.id
  return None


def _is_iter_methods_subscript_call(node: ast.expr) -> bool:
  return _iter_methods_subscript_annotation(node) is not None


def _parse_iter_methods_subscript_options(
  iter_node: ast.expr,
) -> tuple[str, IterReflectOptions] | None:
  from .annotation_options import parse_self_iter_call_options

  ann = _iter_methods_subscript_annotation(iter_node)
  if ann is None:
    return None
  opts = parse_self_iter_call_options(
    iter_node,
    allowed=frozenset({"mro", "glob"}),
    label="Self.iter_methods",
  )
  return ann, opts or IterReflectOptions()


def expand_iter_methods_loop(
  method: ast.FunctionDef,
  host: ClassInfo,
  classes: dict[str, ClassInfo],
) -> ast.FunctionDef | None:
  """``for name in Self.iter_methods([public_only=…, mro=…]):`` → 按声明序展开。"""
  for_idx: int | None = None
  for i, stmt in enumerate(method.body):
    if isinstance(stmt, ast.For) and _is_iter_methods_call(stmt.iter):
      for_idx = i
      break
  if for_idx is None:
    return None
  for_node = method.body[for_idx]
  if not isinstance(for_node.target, ast.Name):
    return None
  method_var = for_node.target.id
  loop_opts = _parse_iter_methods_options(for_node.iter)
  assert loop_opts is not None
  names = _host_method_names_in_order(
    host,
    classes,
    public_only=loop_opts.public_only,
    mro=loop_opts.mro,
    glob=loop_opts.glob,
  )
  unrolled: list[ast.stmt] = []
  for method_name in names:
    unrolled.extend(
      _clone_body_replace_names(
        for_node.body,
        {method_var: ast.Constant(value=method_name)},
        known_fields=frozenset(host.fields),
      )
    )
  out = copy.deepcopy(method)
  out.body = method.body[:for_idx] + unrolled + method.body[for_idx + 1 :]
  return out


def expand_iter_methods_subscript_loop(
  method: ast.FunctionDef,
  host: ClassInfo,
  classes: dict[str, ClassInfo],
) -> ast.FunctionDef | None:
  """``for name in Self.iter_methods[Ann]([mro=…]):`` → 按匹配方法展开。"""
  for_idx: int | None = None
  for i, stmt in enumerate(method.body):
    if isinstance(stmt, ast.For) and _is_iter_methods_subscript_call(stmt.iter):
      for_idx = i
      break
  if for_idx is None:
    return None
  for_node = method.body[for_idx]
  parsed = _parse_iter_methods_subscript_options(for_node.iter)
  if parsed is None or not isinstance(for_node.target, ast.Name):
    return None
  ann, opts = parsed
  method_var = for_node.target.id
  names = annotated_methods(
    host,
    ann,
    classes,
    public_only=False,
    mro=opts.mro,
    glob=opts.glob,
  )
  if not names:
    out = copy.deepcopy(method)
    out.body = method.body[:for_idx] + method.body[for_idx + 1 :]
    ast.fix_missing_locations(out)
    return out
  known = frozenset(host.fields)
  unrolled: list[ast.stmt] = []
  for i, method_name in enumerate(names):
    unrolled.extend(
      _clone_body_replace_names(
        for_node.body,
        {
          method_var: ast.Constant(value=method_name),
          "btn_id": ast.Constant(value=i),
        },
        known_fields=known,
      )
    )
  out = copy.deepcopy(method)
  out.body = method.body[:for_idx] + unrolled + method.body[for_idx + 1 :]
  fold_static_reflect(out, known_fields=known, known_methods=frozenset(host.methods))
  out.body = _simplify_const_ifs(out.body)
  ast.fix_missing_locations(out)
  return out


def parse_self_get_method_annotation_meta(node: ast.expr) -> tuple[str, ast.expr] | None:
  """``Self.get_method_annotation[Meta](method)`` → ``(Meta, method_expr)``。"""
  if not isinstance(node, ast.Call):
    return None
  func = node.func
  if not (
    isinstance(func, ast.Subscript)
    and isinstance(func.value, ast.Attribute)
    and isinstance(func.value.value, ast.Name)
    and func.value.value.id == "Self"
    and func.value.attr == "get_method_annotation"
    and len(node.args) == 1
  ):
    return None
  sl = func.slice
  if isinstance(sl, ast.Name):
    return sl.id, node.args[0]
  if isinstance(sl, ast.Call) and isinstance(sl.func, ast.Name):
    return sl.func.id, node.args[0]
  return None


def _is_method_var_label_assign(stmt: ast.stmt, method_var: str, label_names: frozenset[str]) -> str | None:
  """``label`` / ``btn_label`` = ``method`` → 标签变量名。"""
  if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
    if stmt.target.id in label_names and isinstance(stmt.value, ast.Name) and stmt.value.id == method_var:
      return stmt.target.id
  if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
    tgt = stmt.targets[0]
    if isinstance(tgt, ast.Name) and tgt.id in label_names:
      if isinstance(stmt.value, ast.Name) and stmt.value.id == method_var:
        return tgt.id
  return None


def _fold_method_meta_label_assign(
  body: list[ast.stmt],
  method_var: str,
  method_name: str,
  meta_name: str,
  host: ClassInfo,
) -> list[ast.stmt]:
  """折叠 ``label`` / ``btn_label`` = ``method`` + ``get_method_annotation`` + ``ui_btn.label``。"""
  label = method_meta_label(host, method_name, meta_name)
  label_names = frozenset({"label", "btn_label"})
  out: list[ast.stmt] = []
  skip_next_label_fold = False
  for stmt in body:
    if skip_next_label_fold:
      skip_next_label_fold = False
      continue
    label_name = _is_method_var_label_assign(stmt, method_var, label_names)
    if label_name is not None:
      if isinstance(stmt, ast.AnnAssign):
        out.append(
          ast.AnnAssign(
            target=ast.Name(id=label_name, ctx=ast.Store()),
            annotation=ast.Name(id="str", ctx=ast.Load()),
            value=ast.Constant(value=label),
            simple=1,
          )
        )
      else:
        out.append(
          ast.Assign(
            targets=[ast.Name(id=label_name, ctx=ast.Store())],
            value=ast.Constant(value=label),
          )
        )
      continue
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
      tgt = stmt.targets[0]
      parsed = parse_self_get_method_annotation_meta(stmt.value)
      if parsed is not None and parsed[0] == meta_name:
        continue
    if isinstance(stmt, ast.If):
      test = stmt.test
      if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        continue
      if (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
        and isinstance(test.left, ast.Name)
        and test.left.id == "ui_btn"
      ):
        continue
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
      func = stmt.value.func
      if (
        isinstance(func, ast.Name)
        and func.id == "getattr"
        and len(stmt.value.args) == 2
        and isinstance(stmt.value.args[0], ast.Name)
        and stmt.value.args[0].id == "self"
      ):
        arg1 = stmt.value.args[1]
        if isinstance(arg1, ast.Name) and arg1.id == method_var:
          out.append(
            ast.Expr(
              value=ast.Call(
                func=ast.Attribute(
                  value=ast.Name(id="self", ctx=ast.Load()),
                  attr=method_name,
                  ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
              )
            )
          )
          continue
    if isinstance(stmt, ast.AugAssign) and isinstance(stmt.op, ast.Add):
      val = stmt.value
      if (
        isinstance(val, ast.Call)
        and isinstance(val.func, ast.Name)
        and val.func.id == "getattr"
        and len(val.args) == 2
        and isinstance(val.args[0], ast.Name)
        and val.args[0].id == "self"
      ):
        arg1 = val.args[1]
        if isinstance(arg1, ast.Name) and arg1.id == method_var:
          out.append(
            ast.AugAssign(
              target=copy.deepcopy(stmt.target),
              op=ast.Add(),
              value=ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr=method_name,
                ctx=ast.Load(),
              ),
            )
          )
          continue
    out.append(stmt)
  return out


def _loop_uses_get_method_annotation(body: list[ast.stmt], meta_name: str) -> bool:
  for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
      parsed = parse_self_get_method_annotation_meta(stmt.value)
      if parsed is not None and parsed[0] == meta_name:
        return True
  return False


def expand_iter_methods_subscript_meta(
  method: ast.FunctionDef,
  host: ClassInfo,
  classes: dict[str, ClassInfo] | None = None,
) -> ast.FunctionDef | None:
  """``Self.iter_methods[Ann]`` 循环内折叠 ``get_method_annotation`` 与 ``label``。"""
  for_idx: int | None = None
  meta_name: str | None = None
  opts = IterReflectOptions()
  for i, stmt in enumerate(method.body):
    if isinstance(stmt, ast.For) and _is_iter_methods_subscript_call(stmt.iter):
      for_idx = i
      parsed = _parse_iter_methods_subscript_options(stmt.iter)
      if parsed is not None:
        meta_name, opts = parsed
      break
  if for_idx is None or meta_name is None:
    return None
  for_node = method.body[for_idx]
  if not isinstance(for_node.target, ast.Name):
    return None
  if not _loop_uses_get_method_annotation(for_node.body, meta_name):
    return None
  method_var = for_node.target.id
  names = annotated_methods(
    host,
    meta_name,
    classes,
    public_only=False,
    mro=opts.mro,
    glob=opts.glob,
  )
  if not names:
    out = copy.deepcopy(method)
    out.body = method.body[:for_idx] + method.body[for_idx + 1 :]
    ast.fix_missing_locations(out)
    return out
  unrolled: list[ast.stmt] = []
  for i, method_name in enumerate(names):
    folded = _fold_method_meta_label_assign(
      for_node.body,
      method_var,
      method_name,
      meta_name,
      host,
    )
    unrolled.extend(
      _clone_body_replace_names(
        folded,
        {
          method_var: ast.Constant(value=method_name),
          "btn_id": ast.Constant(value=i),
        },
        known_fields=frozenset(host.fields),
      )
    )
  out = copy.deepcopy(method)
  out.body = method.body[:for_idx] + unrolled + method.body[for_idx + 1 :]
  fold_static_reflect(out, known_fields=frozenset(host.fields), known_methods=frozenset(host.methods))
  out.body = _simplify_const_ifs(out.body)
  ast.fix_missing_locations(out)
  return out
