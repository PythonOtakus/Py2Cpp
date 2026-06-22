"""函数形参 / 返回值上的 ``T @Desc(...)``：生成 ``__set_<fn>_param_<arg>`` / ``__set_<fn>_return`` 校验辅助函数并调用。"""
from __future__ import annotations

import ast
import copy
import re
from typing import TYPE_CHECKING

from ..analysis.ir import (
  is_native_function_body,
  is_overload_stub,
  parse_descriptor_type_annotation,
  strip_descriptor_type_annotation,
)
from .descriptors import (
  VALUE_FIELD,
  _expand_descriptor_method,
  _is_placeholder_body,
  _validate_descriptor_method_signature,
  apply_descriptor_type_substitution,
  bind_descriptor_ctor,
  build_descriptor_type_substitution,
  descriptor_protocol_bounds,
)

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator

_RETURN_TMP = "__py2cpp_return"
_RETURN_VALUE_PARAM = "value"
_HELPER_PARAM_RE = re.compile(r"^__set_(?P<func>.+)_param_(?P<arg>.+)$")
_HELPER_RETURN_RE = re.compile(r"^__set_(?P<func>.+)_return$")


def is_descriptor_signature_helper(name: str) -> bool:
  """译器注入的描述符签名校验辅助函数（``__set_pick_param_n`` / ``__set_pick_return``）。"""
  return bool(_HELPER_PARAM_RE.match(name) or _HELPER_RETURN_RE.match(name))


def _helper_param_name(func_name: str, arg_name: str) -> str:
  return f"__set_{func_name}_param_{arg_name}"


def _helper_return_name(func_name: str) -> str:
  return f"__set_{func_name}_return"


class _InlineDescriptorValue(ast.NodeTransformer):
  """签名校验：``self._lo`` 等折叠为常量；``self.__value__`` 读写均映射为 ``value_name``。"""

  def __init__(
    self,
    value_name: str,
    bound: dict[str, ast.expr],
    host_class: str,
  ):
    self._value_name = value_name
    self._bound = bound
    self._host_class = host_class

  def visit_Name(self, node: ast.Name) -> ast.expr:
    if node.id == "Self" and self._host_class:
      return ast.Name(id=self._host_class, ctx=node.ctx)
    return node

  def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
    self.generic_visit(node)
    if isinstance(node.value, ast.Name) and node.value.id == "self":
      if node.attr == VALUE_FIELD:
        return ast.Name(id=self._value_name, ctx=node.ctx)
      if node.attr in self._bound:
        return copy.deepcopy(self._bound[node.attr])
    return node


class _RenameValueParam(ast.NodeTransformer):
  def __init__(self, from_name: str, to_name: str):
    self._from = from_name
    self._to = to_name

  def visit_Name(self, node: ast.Name) -> ast.expr:
    if node.id == self._from and self._from != self._to:
      return ast.Name(id=self._to, ctx=node.ctx)
    return node

  def visit_arg(self, node: ast.arg) -> ast.arg:
    if node.arg == self._from and self._from != self._to:
      return ast.arg(
        arg=self._to,
        annotation=node.annotation,
        type_comment=node.type_comment,
      )
    return node


def _is_redundant_value_store(stmt: ast.stmt, value_name: str) -> bool:
  """签名校验：``self.__value__ = value`` 已映射为 ``value_name = value_name``，可删。"""
  if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
    return False
  target = stmt.targets[0]
  val = stmt.value
  if not isinstance(target, ast.Name) or not isinstance(val, ast.Name):
    return False
  return target.id == value_name and val.id == value_name


def _strip_redundant_value_assignments(
  stmts: list[ast.stmt],
  value_name: str,
) -> list[ast.stmt]:
  out: list[ast.stmt] = []
  for stmt in stmts:
    if _is_redundant_value_store(stmt, value_name):
      continue
    if isinstance(stmt, ast.If):
      stmt.body = _strip_redundant_value_assignments(stmt.body, value_name)
      stmt.orelse = _strip_redundant_value_assignments(stmt.orelse, value_name)
    elif isinstance(stmt, ast.For):
      stmt.body = _strip_redundant_value_assignments(stmt.body, value_name)
      stmt.orelse = _strip_redundant_value_assignments(stmt.orelse, value_name)
    elif isinstance(stmt, ast.While):
      stmt.body = _strip_redundant_value_assignments(stmt.body, value_name)
      stmt.orelse = _strip_redundant_value_assignments(stmt.orelse, value_name)
    elif isinstance(stmt, ast.With):
      stmt.body = _strip_redundant_value_assignments(stmt.body, value_name)
    elif isinstance(stmt, (ast.Try, ast.TryStar)):
      stmt.body = _strip_redundant_value_assignments(stmt.body, value_name)
      for handler in stmt.handlers:
        handler.body = _strip_redundant_value_assignments(
          handler.body, value_name
        )
      stmt.orelse = _strip_redundant_value_assignments(stmt.orelse, value_name)
      stmt.finalbody = _strip_redundant_value_assignments(
        stmt.finalbody, value_name
      )
    elif isinstance(stmt, ast.Match):
      for case in stmt.cases:
        case.body = _strip_redundant_value_assignments(case.body, value_name)
    out.append(stmt)
  return out


def _descriptor_validate_stmts(
  desc: ClassInfo,
  call: ast.Call,
  value_name: str,
  host_class: str,
  value_type_ann: ast.expr | None = None,
) -> list[ast.stmt]:
  setter = desc.methods.get("__set__")
  if setter is None:
    raise ValueError(
      f"描述符 {desc.name} 缺少 __set__，不能用于函数形参/返回类型 ``T @{desc.name}(...)``"
    )
  _validate_descriptor_method_signature(desc.name, setter)
  cloned = copy.deepcopy(setter)
  cloned.decorator_list = []
  _expand_descriptor_method(cloned)
  apply_descriptor_type_substitution(
    cloned, build_descriptor_type_substitution(desc, value_type_ann)
  )
  value_params = [a.arg for a in cloned.args.args if a.arg != "self"]
  if not value_params:
    raise ValueError(f"{desc.name}.__set__ 需要 value 形参")
  value_param = value_params[0]
  if value_param != value_name:
    _RenameValueParam(value_param, value_name).visit(cloned)
  body = cloned.body
  inliner = _InlineDescriptorValue(
    value_name, bind_descriptor_ctor(desc, call), host_class
  )
  for i, stmt in enumerate(body):
    body[i] = inliner.visit(stmt)
  body = _strip_redundant_value_assignments(body, value_name)
  ast.fix_missing_locations(cloned)
  return copy.deepcopy(body)


def _stripped_type_annotation(
  ann: ast.expr | None,
  desc_names: set[str],
) -> ast.expr | None:
  if ann is None:
    return ast.Name(id="int", ctx=ast.Load())
  return strip_descriptor_type_annotation(ann, desc_names)


def _make_validate_helper(
  helper_name: str,
  value_name: str,
  value_ann: ast.expr | None,
  body: list[ast.stmt],
  *,
  class_static: bool,
) -> ast.FunctionDef:
  decorators: list[ast.expr] = []
  if class_static:
    decorators.append(ast.Name(id="staticmethod", ctx=ast.Load()))
  fn = ast.FunctionDef(
    name=helper_name,
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg=value_name, annotation=value_ann)],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      vararg=None,
      kwarg=None,
    ),
    body=body,
    decorator_list=decorators,
    returns=ast.Constant(value=None),
    type_comment=None,
  )
  ast.fix_missing_locations(fn)
  return fn


def _make_helper_call(
  helper_name: str,
  arg_name: str,
  host_class: str,
) -> ast.Expr:
  if host_class:
    func: ast.expr = ast.Attribute(
      value=ast.Name(id=host_class, ctx=ast.Load()),
      attr=helper_name,
      ctx=ast.Load(),
    )
  else:
    func = ast.Name(id=helper_name, ctx=ast.Load())
  return ast.Expr(
    value=ast.Call(
      func=func,
      args=[ast.Name(id=arg_name, ctx=ast.Load())],
      keywords=[],
    )
  )


def _register_helper(
  tr: Translator,
  module_path: str,
  host: ClassInfo | None,
  helper: ast.FunctionDef,
  *,
  protocol_bounds: tuple[str, ...] = (),
) -> None:
  if protocol_bounds:
    if host is not None:
      host.descriptor_method_protocol_bounds[helper.name] = protocol_bounds
    else:
      tr.descriptor_helper_protocol_bounds[(module_path, helper.name)] = protocol_bounds
  if host is not None:
    if helper.name in host.methods:
      raise ValueError(f"重复的描述符校验辅助函数 {host.name}.{helper.name}")
    host.methods[helper.name] = helper
    return
  tr.module_functions.append((module_path, helper))


def _strip_func_descriptor_annotations(
  func: ast.FunctionDef,
  desc_names: set[str],
) -> None:
  for arg in func.args.args:
    if arg.annotation is not None:
      arg.annotation = strip_descriptor_type_annotation(arg.annotation, desc_names)
  if func.returns is not None:
    func.returns = strip_descriptor_type_annotation(func.returns, desc_names)


def _inject_param_validations(
  func: ast.FunctionDef,
  desc_names: set[str],
  classes: dict[str, ClassInfo],
  host_class: str,
  module_path: str,
  host: ClassInfo | None,
  tr: Translator,
) -> None:
  prefix: list[ast.stmt] = []
  for arg in func.args.args:
    if arg.arg in ("self", "cls") or arg.annotation is None:
      continue
    parsed = parse_descriptor_type_annotation(arg.annotation, desc_names)
    if parsed is None:
      continue
    desc_name, call = parsed
    desc = classes[desc_name]
    helper_name = _helper_param_name(func.name, arg.arg)
    value_ann = _stripped_type_annotation(arg.annotation, desc_names)
    body = _descriptor_validate_stmts(
      desc, call, arg.arg, host_class, value_type_ann=value_ann
    )
    helper = _make_validate_helper(
      helper_name,
      arg.arg,
      value_ann,
      body,
      class_static=bool(host_class),
    )
    _register_helper(
      tr,
      module_path,
      host,
      helper,
      protocol_bounds=descriptor_protocol_bounds(desc),
    )
    prefix.append(_make_helper_call(helper_name, arg.arg, host_class))
  if prefix:
    func.body = prefix + func.body


def _transform_block_for_return_validate(
  stmts: list[ast.stmt],
  validate_factory,
) -> list[ast.stmt]:
  out: list[ast.stmt] = []
  for stmt in stmts:
    if isinstance(stmt, ast.Return):
      if stmt.value is None:
        out.append(stmt)
        continue
      out.append(
        ast.Assign(
          targets=[ast.Name(id=_RETURN_TMP, ctx=ast.Store())],
          value=copy.deepcopy(stmt.value),
        )
      )
      out.extend(validate_factory(_RETURN_TMP))
      out.append(ast.Return(value=ast.Name(id=_RETURN_TMP, ctx=ast.Load())))
      continue
    if isinstance(stmt, ast.If):
      stmt.body = _transform_block_for_return_validate(stmt.body, validate_factory)
      stmt.orelse = _transform_block_for_return_validate(stmt.orelse, validate_factory)
      out.append(stmt)
      continue
    if isinstance(stmt, ast.For):
      stmt.body = _transform_block_for_return_validate(stmt.body, validate_factory)
      stmt.orelse = _transform_block_for_return_validate(stmt.orelse, validate_factory)
      out.append(stmt)
      continue
    if isinstance(stmt, ast.While):
      stmt.body = _transform_block_for_return_validate(stmt.body, validate_factory)
      stmt.orelse = _transform_block_for_return_validate(stmt.orelse, validate_factory)
      out.append(stmt)
      continue
    if isinstance(stmt, ast.With):
      stmt.body = _transform_block_for_return_validate(stmt.body, validate_factory)
      out.append(stmt)
      continue
    if isinstance(stmt, (ast.Try, ast.TryStar)):
      stmt.body = _transform_block_for_return_validate(stmt.body, validate_factory)
      for handler in stmt.handlers:
        handler.body = _transform_block_for_return_validate(
          handler.body, validate_factory
        )
      stmt.orelse = _transform_block_for_return_validate(stmt.orelse, validate_factory)
      stmt.finalbody = _transform_block_for_return_validate(
        stmt.finalbody, validate_factory
      )
      out.append(stmt)
      continue
    if isinstance(stmt, ast.Match):
      for case in stmt.cases:
        case.body = _transform_block_for_return_validate(case.body, validate_factory)
      out.append(stmt)
      continue
    out.append(stmt)
  return out


def _inject_return_validations(
  func: ast.FunctionDef,
  desc_names: set[str],
  classes: dict[str, ClassInfo],
  host_class: str,
  module_path: str,
  host: ClassInfo | None,
  tr: Translator,
) -> None:
  if func.returns is None:
    return
  parsed = parse_descriptor_type_annotation(func.returns, desc_names)
  if parsed is None:
    return
  desc_name, call = parsed
  desc = classes[desc_name]
  helper_name = _helper_return_name(func.name)
  value_ann = _stripped_type_annotation(func.returns, desc_names)
  body = _descriptor_validate_stmts(
    desc, call, _RETURN_VALUE_PARAM, host_class, value_type_ann=value_ann
  )
  helper = _make_validate_helper(
    helper_name,
    _RETURN_VALUE_PARAM,
    value_ann,
    body,
    class_static=bool(host_class),
  )
  _register_helper(
    tr,
    module_path,
    host,
    helper,
    protocol_bounds=descriptor_protocol_bounds(desc),
  )

  def factory(tmp: str) -> list[ast.stmt]:
    return [_make_helper_call(helper_name, tmp, host_class)]

  func.body = _transform_block_for_return_validate(func.body, factory)


def _should_skip_function(func: ast.FunctionDef) -> bool:
  if is_descriptor_signature_helper(func.name):
    return True
  if is_native_function_body(func.body):
    return True
  if is_overload_stub(func):
    return True
  return False


def _apply_to_function(
  func: ast.FunctionDef,
  desc_names: set[str],
  classes: dict[str, ClassInfo],
  host_class: str,
  module_path: str,
  host: ClassInfo | None,
  tr: Translator,
) -> None:
  if _should_skip_function(func):
    return
  _inject_param_validations(
    func, desc_names, classes, host_class, module_path, host, tr
  )
  _inject_return_validations(
    func, desc_names, classes, host_class, module_path, host, tr
  )
  _strip_func_descriptor_annotations(func, desc_names)


def expand_descriptor_signatures(tr: Translator) -> None:
  desc_names = {name for name, info in tr.classes.items() if info.is_descriptor}
  if not desc_names:
    return
  classes = tr.classes

  for module_path, func in list(tr.module_functions):
    if tr._is_stdlib_module(module_path):
      continue
    _apply_to_function(func, desc_names, classes, "", module_path, None, tr)

  for host in tr.classes.values():
    if tr._is_stdlib_module(host.module_path):
      continue
    if host.is_descriptor or host.is_mixin or host.is_annotation or host.is_protocol:
      continue
    host_cpp = host.cpp_name()
    for func in list(host.iter_methods()):
      _apply_to_function(
        func, desc_names, classes, host_cpp, host.module_path, host, tr
      )
    for func in host.inits:
      _apply_to_function(
        func, desc_names, classes, host_cpp, host.module_path, host, tr
      )
