"""描述符类展开：将 ``@descriptor`` 标记类的逻辑内联到使用方类中。

宿主字段写法（与普通字段相同，默认值在 ``=`` 右侧）::

  score: int @PlainValueVar() = 0
  level: int @ClampedIntVar(0, 10) = 0

描述符方法签名（内联后 ``self`` 即宿主实例，**勿**写 CPython 的 ``owner`` / ``obj``）::

  def __get__(self): ...
  def __set__(self, value): ...

``__get__`` / ``__set__`` 可仅写 ``...`` → 读写 ``self.__value__``（→ 宿主 ``attr__value``）。
"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, PropertyDef, parse_descriptor_type_annotation
from ..analysis.type_emit import clear_field_ann_ast, field_ann_ast, write_field_ann_ast, write_field_storage
from ..analysis.patterns import (
  property_getter_method_for,
  property_postsetter_method_for,
  property_setter_method_for,
  property_storage_field_for,
)

if TYPE_CHECKING:
  from ..translator import Translator

DESCRIPTOR_DECORATOR = "descriptor"
VALUE_FIELD = "__value__"
LEGACY_DESCRIPTOR_ASSIGN_MSG = (
  "描述符字段请写 ``name: T @Desc(...) = 默认值``；"
  "勿将 ``Desc(...)`` 放在等号右侧"
)


def is_descriptor_class(info: ClassInfo) -> bool:
  for dec in info.node.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == DESCRIPTOR_DECORATOR:
      return True
    if (
      isinstance(dec, ast.Call)
      and isinstance(dec.func, ast.Name)
      and dec.func.id == DESCRIPTOR_DECORATOR
    ):
      return True
  return False


def storage_field_for(attr: str) -> str:
  """``self.__value__`` 对应宿主类上的存储字段（同 ``property_storage_field_for``）。"""
  return property_storage_field_for(attr)


def bind_descriptor_ctor(desc: ClassInfo, call: ast.Call) -> dict[str, ast.expr]:
  """将描述符构造实参绑定到 ``__init__`` 形参名及 ``self._field = param`` 字段名。"""
  if not desc.inits:
    return {}
  init = desc.inits[0]
  params = [a.arg for a in init.args.args if a.arg != "self"]
  bound: dict[str, ast.expr] = {}
  for i, name in enumerate(params):
    if i < len(call.args):
      bound[name] = call.args[i]
  for kw in call.keywords:
    if kw.arg:
      bound[kw.arg] = kw.value
  for stmt in init.body:
    if not isinstance(stmt, ast.Assign):
      continue
    for target in stmt.targets:
      if not (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
        and isinstance(stmt.value, ast.Name)
      ):
        continue
      param = stmt.value.id
      if param in bound:
        bound[target.attr] = bound[param]
  return bound


class _InlineDescriptor(ast.NodeTransformer):
  """把描述符方法体中的 ``self.__value__`` / ``Self`` / 构造期字段替换为宿主类成员或常量。"""

  def __init__(self, attr: str, bound: dict[str, ast.expr], host_class: str):
    self._storage = storage_field_for(attr)
    self._bound = bound
    self._host_class = host_class

  def visit_Name(self, node: ast.Name) -> ast.expr:
    if node.id == "Self":
      return ast.Name(id=self._host_class, ctx=node.ctx)
    return node

  def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
    self.generic_visit(node)
    if isinstance(node.value, ast.Name) and node.value.id == "self":
      if node.attr == VALUE_FIELD:
        return ast.Attribute(
          value=ast.Name(id="self", ctx=node.ctx),
          attr=self._storage,
          ctx=node.ctx,
        )
      if node.attr in self._bound:
        return copy.deepcopy(self._bound[node.attr])
    return node


def _is_placeholder_body(body: list[ast.stmt]) -> bool:
  if not body:
    return True
  if len(body) != 1:
    return False
  stmt = body[0]
  if isinstance(stmt, ast.Pass):
    return True
  return (
    isinstance(stmt, ast.Expr)
    and (
      (isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis)
      or isinstance(stmt.value, ast.Ellipsis)
    )
  )


def _default_descriptor_get_body() -> list[ast.stmt]:
  return [
    ast.Return(
      value=ast.Attribute(
        value=ast.Name(id="self", ctx=ast.Load()),
        attr=VALUE_FIELD,
        ctx=ast.Load(),
      ),
    ),
  ]


def _default_descriptor_set_body(param: str) -> list[ast.stmt]:
  return [
    ast.Assign(
      targets=[
        ast.Attribute(
          value=ast.Name(id="self", ctx=ast.Store()),
          attr=VALUE_FIELD,
          ctx=ast.Store(),
        ),
      ],
      value=ast.Name(id=param, ctx=ast.Load()),
    ),
  ]


def _expand_descriptor_method(method: ast.FunctionDef) -> ast.FunctionDef:
  """``__get__`` / ``__set__`` 仅写 ``...`` 时展开为读写 ``self.__value__`` 的默认逻辑。"""
  if not _is_placeholder_body(method.body):
    return method
  if method.name == "__get__":
    method.body = _default_descriptor_get_body()
  elif method.name == "__set__":
    params = [a.arg for a in method.args.args if a.arg != "self"]
    if not params:
      raise ValueError(f"{method.name} 需要除 self 外的 value 参数")
    method.body = _default_descriptor_set_body(params[0])
  else:
    raise ValueError(
      f"描述符方法 {method.name} 不能使用 ``...`` 占位；仅 __get__ / __set__ 支持省略函数体"
    )
  ast.fix_missing_locations(method)
  return method


def descriptor_protocol_bounds(desc: ClassInfo) -> tuple[str, ...]:
  """描述符类 PEP 695 形参上的 ``@protocol`` 约束名（按 ``type_params`` 顺序）。"""
  if not desc.type_params:
    return ()
  out: list[str] = []
  for p in desc.type_params:
    out.extend(desc.type_param_constraints.get(p, ()))
  return tuple(out)


def build_descriptor_type_substitution(
  desc: ClassInfo,
  value_type_ann: ast.expr | None,
) -> dict[str, ast.expr]:
  """单形参 ``T`` 描述符：``T`` ← 宿主 ``int @Desc(...)`` 左侧类型。"""
  if value_type_ann is None or not desc.type_params:
    return {}
  if len(desc.type_params) != 1:
    raise ValueError(
      f"{desc.name}: 多类型参数描述符暂不支持；请仅使用单形参 T"
    )
  return {desc.type_params[0]: copy.deepcopy(value_type_ann)}


class _SubstituteDescriptorTypes(ast.NodeTransformer):
  """将描述符方法注解中的形参名 ``T`` 替换为宿主具体类型注解 AST。"""

  def __init__(self, subst: dict[str, ast.expr]):
    self._subst = subst

  def _subst_type(self, node: ast.expr) -> ast.expr:
    if isinstance(node, ast.Name) and node.id in self._subst:
      return copy.deepcopy(self._subst[node.id])
    if isinstance(node, ast.Subscript):
      node = copy.deepcopy(node)
      node.value = self._subst_type(node.value)
      if isinstance(node.slice, ast.Tuple):
        elts = [self._subst_type(e) for e in node.slice.elts]
        node.slice = ast.Tuple(elts=elts, ctx=node.slice.ctx)
      else:
        node.slice = self._subst_type(node.slice)
      return node
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
      node = copy.deepcopy(node)
      node.left = self._subst_type(node.left)
      node.right = self._subst_type(node.right)
      return node
    if isinstance(node, ast.Tuple):
      return ast.Tuple(
        elts=[self._subst_type(e) for e in node.elts],
        ctx=node.ctx,
      )
    return node

  def visit_arg(self, node: ast.arg) -> ast.arg:
    node = copy.deepcopy(node)
    if node.annotation is not None:
      node.annotation = self._subst_type(node.annotation)
    return node

  def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
    node = self.generic_visit(node)
    if node.returns is not None:
      node.returns = self._subst_type(node.returns)
    return node


def apply_descriptor_type_substitution(
  method: ast.FunctionDef,
  subst: dict[str, ast.expr],
) -> None:
  if subst:
    _SubstituteDescriptorTypes(subst).visit(method)
    ast.fix_missing_locations(method)


def _validate_descriptor_method_signature(desc_name: str, method: ast.FunctionDef) -> None:
  args = [a.arg for a in method.args.args]
  if method.name == "__get__":
    if args != ["self"]:
      raise ValueError(
        f"{desc_name}.{method.name} 形参须为 (self)，"
        f"勿写 owner/obj/owner_type；当前: ({', '.join(args)})"
      )
  elif method.name == "__set__":
    if len(args) != 2 or args[0] != "self":
      raise ValueError(
        f"{desc_name}.{method.name} 形参须为 (self, value)，"
        f"当前: ({', '.join(args)})"
      )


def _clone_descriptor_method(
  method: ast.FunctionDef,
  attr: str,
  bound: dict[str, ast.expr],
  host: ClassInfo,
  desc: ClassInfo,
  *,
  value_type_ann: ast.expr | None = None,
) -> ast.FunctionDef:
  _validate_descriptor_method_signature(desc.name, method)
  cloned = _expand_descriptor_method(copy.deepcopy(method))
  cloned.decorator_list = []
  subst = build_descriptor_type_substitution(desc, value_type_ann)
  apply_descriptor_type_substitution(cloned, subst)
  _InlineDescriptor(attr, bound, host.cpp_name()).visit(cloned)
  ast.fix_missing_locations(cloned)
  return cloned


def _reject_legacy_descriptor_rhs(stmt: ast.stmt, desc_names: set[str]) -> None:
  """``name = Desc(...)`` / ``name: T = Desc(...)`` 旧写法 → 翻译期报错。"""
  value: ast.expr | None = None
  match stmt:
    case ast.Assign(targets=[t], value=v):
      if isinstance(t, ast.Name):
        value = v
    case ast.AnnAssign(value=v) if v is not None:
      value = v
    case _:
      return
  if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
    return
  if value.func.id not in desc_names:
    return
  raise ValueError(LEGACY_DESCRIPTOR_ASSIGN_MSG)


def _host_descriptor_field(
  stmt: ast.stmt,
  desc_names: set[str],
) -> tuple[str, str, ast.Call, ast.expr | None] | None:
  if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
    return None
  parsed = parse_descriptor_type_annotation(stmt.annotation, desc_names)
  if parsed is None:
    return None
  desc_name, call = parsed
  return stmt.target.id, desc_name, call, stmt.value


def apply_descriptor_field(
  host: ClassInfo,
  desc: ClassInfo,
  attr: str,
  call: ast.Call,
  default: ast.expr | None,
  value_type_ann: ast.expr | None,
) -> None:
  storage = storage_field_for(attr)
  if storage not in host.fields:
    host.fields.append(storage)
  if attr in host.fields:
    host.fields.remove(attr)

  if default is not None:
    host.field_defaults[storage] = copy.deepcopy(default)
  if attr in host.field_defaults:
    host.field_defaults.pop(attr, None)

  if value_type_ann is not None:
    write_field_ann_ast(host, storage, copy.deepcopy(value_type_ann))
    write_field_storage(host, storage, None)
  if field_ann_ast(host, attr) is not None:
    clear_field_ann_ast(host, attr)
  write_field_storage(host, attr, None)

  bound = bind_descriptor_ctor(desc, call)
  prop = host.properties.setdefault(attr, PropertyDef(name=attr))
  prop.from_descriptor = True
  bounds = descriptor_protocol_bounds(desc)
  if bounds:
    prop.descriptor_protocol_bounds = bounds
    host.descriptor_method_protocol_bounds[property_setter_method_for(attr)] = bounds

  getter = desc.methods.get("__get__")
  if getter is not None:
    prop.getter = _clone_descriptor_method(
      getter, attr, bound, host, desc, value_type_ann=value_type_ann
    )
    host._collect_fields(prop.getter)

  setter = desc.methods.get("__set__")
  if setter is not None:
    prop.setter = _clone_descriptor_method(
      setter, attr, bound, host, desc, value_type_ann=value_type_ann
    )
    host._collect_fields(prop.setter)


def expand_descriptors(tr: Translator) -> None:
  for info in tr.classes.values():
    info.is_descriptor = is_descriptor_class(info)

  desc_names = {name for name, info in tr.classes.items() if info.is_descriptor}

  for host in tr.classes.values():
    if host.is_descriptor:
      continue
    for stmt in list(host.node.body):
      _reject_legacy_descriptor_rhs(stmt, desc_names)
      parsed = _host_descriptor_field(stmt, desc_names)
      if parsed is None:
        continue
      attr, desc_name, call, default = parsed
      if desc_name not in desc_names:
        continue
      from ..analysis.ir import strip_descriptor_type_annotation

      value_ann = strip_descriptor_type_annotation(
        stmt.annotation if isinstance(stmt, ast.AnnAssign) else None,
        desc_names,
      )
      apply_descriptor_field(
        host,
        tr.classes[desc_name],
        attr,
        call,
        default,
        value_ann,
      )
