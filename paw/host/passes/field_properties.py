"""类体 ``name: T @property = …`` → 只读 ``name__get()``（存储 ``name__value``；dunder 名不合并下划线，见 ``patterns.property_*_for``）。

``name: T @property.postsetter(cb) = …`` / ``@staticproperty.postsetter(cb)`` 简写 → 合成
``name__get``/``name__set``/``name__postset``（``cb`` 可为字段/方法/``Self.…``）。

手写 ``@property.postsetter def name(…)`` 仍支持；类型由 ``value: T`` 形参或字段注解推断。
"""
from __future__ import annotations

import ast
import copy

from ..analysis.ir import (
  ClassInfo,
  PropertyDef,
  is_property_type_annotation,
  parse_postsetter_type_annotation,
  strip_type_annotation_markers,
)
from ..analysis.type_emit import clear_field_ann_ast, field_ann_ast, write_field_ann_ast, write_field_storage
from .descriptors import VALUE_FIELD, storage_field_for


def _synthetic_field_property_getter(
  field: str,
  storage: str,
  base_ann: ast.expr | None,
) -> ast.FunctionDef:
  body = [
    ast.Return(
      value=ast.Attribute(
        value=ast.Name(id="self", ctx=ast.Load()),
        attr=storage,
        ctx=ast.Load(),
      ),
    ),
  ]
  return ast.FunctionDef(
    name=field,
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    ),
    body=body,
    decorator_list=[ast.Name(id="property", ctx=ast.Load())],
    returns=copy.deepcopy(base_ann) if base_ann is not None else None,
    type_comment=None,
  )


def _migrate_field_property_storage(info: ClassInfo, field: str, base_ann: ast.expr | None) -> str:
  """``value: T @property`` → 存储 ``value__value``，移出公开字段名 ``value``。"""
  storage = storage_field_for(field)
  if field in info.fields:
    info.fields.remove(field)
  if storage not in info.fields:
    info.fields.append(storage)
  if field in info.field_defaults:
    info.field_defaults[storage] = info.field_defaults.pop(field)
  ann = field_ann_ast(info, field)
  if ann is not None:
    write_field_ann_ast(
      info, storage, copy.deepcopy(strip_type_annotation_markers(ann))
    )
    clear_field_ann_ast(info, field)
  node = info.field_type_nodes.pop(field, None)
  if node is not None and base_ann is None:
    write_field_storage(info, storage, node)
  else:
    write_field_storage(info, field, None)
    if base_ann is not None:
      write_field_storage(info, storage, None)
    info.field_types.pop(field, None)
  return storage


def _method_value_arg_count(info: ClassInfo, class_name: str, method_name: str) -> int:
  """实例/静态方法除 ``self``/``cls`` 外形参个数；postsetter 回调仅支持 0 或 1。"""
  method = info.methods.get(method_name)
  if method is None:
    raise ValueError(
      f"{class_name}.{method_name}: postsetter 回调未找到对应方法"
    )
  extra = [a for a in method.args.args if a.arg not in ("self", "cls")]
  if len(extra) == 0:
    return 0
  if len(extra) == 1:
    return 1
  raise ValueError(
    f"{class_name}.{method_name}: postsetter 回调方法除 ``self``/``cls`` 外"
    f"至多一个形参（收到 {len(extra)} 个）"
  )


def _callback_call_expr(
  info: ClassInfo,
  callback: ast.expr,
  *,
  static: bool,
) -> ast.Call:
  """``cb`` → ``self.cb(value)`` / ``self.cb()`` / ``Self.cb(value)`` 等。"""
  value_node = ast.Name(id="value", ctx=ast.Load())
  owner = info.name

  def _args_for_method(method_name: str) -> list[ast.expr]:
    n = _method_value_arg_count(info, owner, method_name)
    return [] if n == 0 else [value_node]

  def _recv_name(static_recv: bool) -> ast.Name:
    return ast.Name(id="Self" if static_recv else "self", ctx=ast.Load())

  if isinstance(callback, ast.Name):
    name = callback.id
    if name in info.methods:
      return ast.Call(
        func=ast.Attribute(value=_recv_name(static), attr=name, ctx=ast.Load()),
        args=_args_for_method(name),
        keywords=[],
      )
    if static:
      return ast.Call(
        func=ast.Attribute(value=_recv_name(True), attr=name, ctx=ast.Load()),
        args=[value_node],
        keywords=[],
      )
    return ast.Call(
      func=ast.Attribute(value=_recv_name(False), attr=name, ctx=ast.Load()),
      args=[value_node],
      keywords=[],
    )

  if isinstance(callback, ast.Attribute) and isinstance(callback.value, ast.Name):
    recv = callback.value.id
    attr = callback.attr
    if recv == "Self":
      if attr in info.methods:
        return ast.Call(
          func=ast.Attribute(value=_recv_name(True), attr=attr, ctx=ast.Load()),
          args=_args_for_method(attr),
          keywords=[],
        )
      return ast.Call(
        func=ast.Attribute(value=_recv_name(True), attr=attr, ctx=ast.Load()),
        args=[value_node],
        keywords=[],
      )
    if recv == "self" and not static:
      if attr in info.methods:
        return ast.Call(
          func=ast.Attribute(value=_recv_name(False), attr=attr, ctx=ast.Load()),
          args=_args_for_method(attr),
          keywords=[],
        )
      return ast.Call(
        func=ast.Attribute(value=_recv_name(False), attr=attr, ctx=ast.Load()),
        args=[value_node],
        keywords=[],
      )

  raise ValueError(
    f"{owner}: postsetter 回调须为名称或 ``Self.…`` / ``self.…``，"
    f"收到 ``{ast.unparse(callback)}``"
  )


def _synthetic_postsetter_from_callbacks(
  name: str,
  base_ann: ast.expr,
  callbacks: tuple[ast.expr, ...],
  info: ClassInfo,
  *,
  static: bool,
) -> ast.FunctionDef:
  body = [
    ast.Expr(value=_callback_call_expr(info, callback, static=static))
    for callback in callbacks
  ]
  if static:
    args = ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="value", annotation=copy.deepcopy(base_ann))],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    )
  else:
    args = ast.arguments(
      posonlyargs=[],
      args=[
        ast.arg(arg="self"),
        ast.arg(arg="value", annotation=copy.deepcopy(base_ann)),
      ],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    )
  fn = ast.FunctionDef(
    name=name,
    args=args,
    body=body,
    decorator_list=[],
    returns=ast.Constant(value=None),
    type_comment=None,
  )
  ast.fix_missing_locations(fn)
  return fn


def _migrate_static_postsetter_storage(
  info: ClassInfo,
  field: str,
  base_ann: ast.expr | None,
) -> str:
  """``origin: T @staticproperty.postsetter(cb)`` → 存储 ``origin__value``。"""
  storage = storage_field_for(field)
  if field in info.fields:
    info.fields.remove(field)
  info.static_property_storage.add(storage)
  if field in info.field_defaults:
    info.field_defaults[storage] = info.field_defaults.pop(field)
  ann = field_ann_ast(info, field)
  if ann is not None:
    write_field_ann_ast(
      info, storage, copy.deepcopy(base_ann) if base_ann else None
    )
    clear_field_ann_ast(info, field)
  node = info.field_type_nodes.pop(field, None)
  if node is not None and base_ann is None:
    write_field_storage(info, storage, node)
  else:
    write_field_storage(info, field, None)
    if base_ann is not None:
      write_field_storage(info, storage, None)
    info.field_types.pop(field, None)
  return storage


def _conflict_postsetter(
  info: ClassInfo,
  name: str,
  prop: PropertyDef,
  *,
  static: bool,
  shorthand: bool,
) -> None:
  kind = "@staticproperty.postsetter" if static else "@property.postsetter"
  where = "字段注解" if shorthand else "方法"
  if prop.getter is not None or prop.setter is not None:
    raise ValueError(
      f"{info.name}.{name}: 已有 {kind}（{where}），不可再写 getter/setter"
    )
  if prop.postsetter is not None:
    other = "方法" if shorthand else "字段注解"
    raise ValueError(
      f"{info.name}.{name}: {kind} 与 {other} 写法冲突"
    )


def expand_field_postsetter_shorthand(classes: dict[str, ClassInfo]) -> None:
  for info in classes.values():
    if info.is_mixin or info.is_annotation or info.is_descriptor:
      continue
    for field in list(info.fields):
      ann = field_ann_ast(info, field)
      parsed = parse_postsetter_type_annotation(ann)
      if parsed is None:
        continue
      base_ann, kind, callbacks = parsed
      if kind == "property":
        prop = info.properties.setdefault(field, PropertyDef(name=field))
        _conflict_postsetter(info, field, prop, static=False, shorthand=True)
        storage = _migrate_field_property_storage(info, field, base_ann)
        prop.postsetter = _synthetic_postsetter_from_callbacks(
          field, base_ann, callbacks, info, static=False,
        )
        info.postsetter_properties.add(field)
        if prop.getter is None:
          getter = _synthetic_field_property_getter(field, storage, base_ann)
          ast.fix_missing_locations(getter)
          prop.getter = getter
      else:
        prop = info.static_properties.setdefault(field, PropertyDef(name=field))
        _conflict_postsetter(info, field, prop, static=True, shorthand=True)
        storage = _migrate_static_postsetter_storage(info, field, base_ann)
        prop.postsetter = _synthetic_postsetter_from_callbacks(
          field, base_ann, callbacks, info, static=True,
        )
        info.postsetter_properties.add(field)
        if prop.getter is None:
          getter = _synthetic_static_property_getter(field, storage, base_ann)
          ast.fix_missing_locations(getter)
          prop.getter = getter


def expand_field_properties(classes: dict[str, ClassInfo]) -> None:
  for info in classes.values():
    if info.is_mixin or info.is_annotation:
      continue
    for field in list(info.fields):
      ann = field_ann_ast(info, field)
      if not is_property_type_annotation(ann):
        continue
      info.field_properties.add(field)
      base_ann = strip_type_annotation_markers(ann)
      storage = _migrate_field_property_storage(info, field, base_ann)
      prop = info.properties.setdefault(field, PropertyDef(name=field))
      if prop.getter is None:
        getter = _synthetic_field_property_getter(field, storage, base_ann)
        ast.fix_missing_locations(getter)
        prop.getter = getter
  expand_field_postsetter_shorthand(classes)
  expand_postsetter_properties(classes)


def _postsetter_value_arg(method: ast.FunctionDef, *, static: bool) -> ast.arg:
  skip = ("self", "cls")
  params = [a for a in method.args.args if a.arg not in skip]
  if len(params) != 1 or params[0].arg != "value":
    dec = "@staticproperty.postsetter" if static else "@property.postsetter"
    raise ValueError(
      f"{method.name}: {dec} 须写 ``def {method.name}"
      f"({'value: T' if static else 'self, value: T'}) -> None``"
    )
  if params[0].annotation is None:
    raise ValueError(f"{method.name}: postsetter 的 ``value`` 须有类型注解")
  return params[0]


def _ensure_postsetter_storage(info: ClassInfo, name: str) -> str:
  storage = storage_field_for(name)
  if storage not in info.fields:
    info.fields.append(storage)
  write_field_storage(info, storage, None)
  return storage


def expand_postsetter_properties(classes: dict[str, ClassInfo]) -> None:
  for info in classes.values():
    if info.is_mixin or info.is_annotation or info.is_descriptor:
      continue
    for prop in info.properties.values():
      if prop.postsetter is None:
        continue
      value_arg = _postsetter_value_arg(prop.postsetter, static=False)
      base_ann = strip_type_annotation_markers(copy.deepcopy(value_arg.annotation))
      storage = _ensure_postsetter_storage(info, prop.name)
      info.postsetter_properties.add(prop.name)
      if prop.getter is None:
        getter = _synthetic_field_property_getter(prop.name, storage, base_ann)
        ast.fix_missing_locations(getter)
        prop.getter = getter
    for prop in info.static_properties.values():
      if prop.postsetter is None:
        continue
      value_arg = _postsetter_value_arg(prop.postsetter, static=True)
      base_ann = strip_type_annotation_markers(copy.deepcopy(value_arg.annotation))
      storage = storage_field_for(prop.name)
      _ensure_static_property_storage_field(info, storage)
      info.postsetter_properties.add(prop.name)
      if prop.getter is None:
        getter = _synthetic_static_property_getter(prop.name, storage, base_ann)
        ast.fix_missing_locations(getter)
        prop.getter = getter


def _synthetic_static_property_getter(
  field: str,
  storage: str,
  base_ann: ast.expr | None,
) -> ast.FunctionDef:
  body = [
    ast.Return(
      value=ast.Attribute(
        value=ast.Name(id="Self", ctx=ast.Load()),
        attr=storage,
        ctx=ast.Load(),
      ),
    ),
  ]
  return ast.FunctionDef(
    name=field,
    args=ast.arguments(
      posonlyargs=[],
      args=[],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    ),
    body=body,
    decorator_list=[ast.Name(id="staticproperty", ctx=ast.Load())],
    returns=copy.deepcopy(base_ann) if base_ann is not None else None,
    type_comment=None,
  )


def property_storage_field(info: ClassInfo, prop_name: str) -> str:
  """``@property`` getter/setter 内 ``self.__value__`` 对应的存储字段。"""
  return storage_field_for(prop_name)


def _ensure_property_storage_field(info: ClassInfo, storage: str) -> None:
  if storage not in info.fields:
    info.fields.append(storage)


def _ensure_static_property_storage_field(info: ClassInfo, storage: str) -> None:
  info.static_property_storage.add(storage)


class _InlinePropertyValue(ast.NodeTransformer):
  """实例 ``@property``：``self.__value__`` → ``{name}__value``。"""

  def __init__(self, storage_field: str):
    self._storage_field = storage_field

  def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
    self.generic_visit(node)
    if (
      isinstance(node.value, ast.Name)
      and node.value.id == "self"
      and node.attr == VALUE_FIELD
    ):
      return ast.Attribute(
        value=ast.Name(id="self", ctx=node.ctx),
        attr=self._storage_field,
        ctx=node.ctx,
      )
    return node


class _InlineStaticPropertyValue(ast.NodeTransformer):
  """``@staticproperty``：``Self.__value__`` → ``Self.{name}__value``。"""

  def __init__(self, storage_field: str):
    self._storage_field = storage_field

  def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
    self.generic_visit(node)
    if (
      isinstance(node.value, ast.Name)
      and node.value.id == "Self"
      and node.attr == VALUE_FIELD
    ):
      return ast.Attribute(
        value=ast.Name(id="Self", ctx=node.ctx),
        attr=self._storage_field,
        ctx=node.ctx,
      )
    return node


def _property_uses_value_field(node: ast.AST | None) -> bool:
  if node is None:
    return False
  for child in ast.walk(node):
    if isinstance(child, ast.Attribute):
      if isinstance(child.value, ast.Name) and child.value.id in ("self", "Self"):
        if child.attr == VALUE_FIELD:
          return True
  return False


def expand_property_value_references(classes: dict[str, ClassInfo]) -> None:
  for info in classes.values():
    if info.is_mixin or info.is_annotation or info.is_descriptor:
      continue
    for prop in info.properties.values():
      if not (
        _property_uses_value_field(prop.getter)
        or _property_uses_value_field(prop.setter)
        or _property_uses_value_field(prop.postsetter)
      ):
        continue
      storage = property_storage_field(info, prop.name)
      _ensure_property_storage_field(info, storage)
      if prop.getter is not None:
        prop.getter = _InlinePropertyValue(storage).visit(prop.getter)
        ast.fix_missing_locations(prop.getter)
      if prop.setter is not None:
        prop.setter = _InlinePropertyValue(storage).visit(prop.setter)
        ast.fix_missing_locations(prop.setter)
      if prop.postsetter is not None:
        prop.postsetter = _InlinePropertyValue(storage).visit(prop.postsetter)
        ast.fix_missing_locations(prop.postsetter)
    for prop in info.static_properties.values():
      if not (
        _property_uses_value_field(prop.getter)
        or _property_uses_value_field(prop.setter)
        or _property_uses_value_field(prop.postsetter)
      ):
        continue
      storage = property_storage_field(info, prop.name)
      _ensure_static_property_storage_field(info, storage)
      if prop.getter is not None:
        prop.getter = _InlineStaticPropertyValue(storage).visit(prop.getter)
        ast.fix_missing_locations(prop.getter)
      if prop.setter is not None:
        prop.setter = _InlineStaticPropertyValue(storage).visit(prop.setter)
        ast.fix_missing_locations(prop.setter)
      if prop.postsetter is not None:
        prop.postsetter = _InlineStaticPropertyValue(storage).visit(prop.postsetter)
        ast.fix_missing_locations(prop.postsetter)
