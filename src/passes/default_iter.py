"""为同时实现 ``__getitem__(int)`` 与 ``__len__`` 且未写 ``__iter__`` 的类注入默认序列迭代器。

生成 ``{Host}_iterator``（逻辑同 ``list_iterator``：下标 ``0..len-1``）及 ``__iter__`` → ``return new(self)``。
"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo

if TYPE_CHECKING:
  from ..translator import Translator


def _has_immutable_decorator(node: ast.FunctionDef) -> bool:
  for dec in node.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == "immutable":
      return True
    if (
      isinstance(dec, ast.Call)
      and isinstance(dec.func, ast.Name)
      and dec.func.id == "immutable"
    ):
      return True
  return False


def _is_int_index_annotation(ann: ast.expr | None) -> bool:
  if ann is None:
    return False
  if isinstance(ann, ast.Name) and ann.id == "int":
    return True
  return (
    isinstance(ann, ast.Subscript)
    and isinstance(ann.value, ast.Name)
    and ann.value.id == "int"
  )


def _is_slice_index_annotation(ann: ast.expr | None) -> bool:
  if not isinstance(ann, ast.Subscript):
    return False
  val = ann.value
  return isinstance(val, ast.Name) and val.id == "slice"


def _int_getitem_method(info: ClassInfo) -> ast.FunctionDef | None:
  candidates: list[ast.FunctionDef] = []
  if "__getitem__" in info.method_overloads:
    candidates.extend(info.method_overloads["__getitem__"])
  elif "__getitem__" in info.methods:
    candidates.append(info.methods["__getitem__"])
  for meth in candidates:
    args = meth.args.args
    if len(args) < 2:
      continue
    if _is_slice_index_annotation(args[1].annotation):
      continue
    if _is_int_index_annotation(args[1].annotation):
      return meth
  return None


def _skip_host(info: ClassInfo, tr: Translator) -> bool:
  if (
    info.is_protocol
    or info.is_mixin
    or info.is_descriptor
    or info.is_annotation
    or info.is_refcount
    or info.is_boxing
  ):
    return True
  if tr._is_stdlib_module(info.module_path):
    return True
  return False


def _make_type_element_alias(type_param: str) -> ast.TypeAlias:
  stmt = ast.TypeAlias(
    name=ast.Name(id="Element", ctx=ast.Store()),
    type_params=[],
    value=ast.Name(id=type_param, ctx=ast.Load()),
  )
  ast.fix_missing_locations(stmt)
  return stmt


def _make_iterator_init(host_name: str, *, type_params: list[str]) -> ast.FunctionDef:
  host_ann: ast.expr = ast.Name(id=host_name, ctx=ast.Load())
  if type_params:
    host_ann = ast.Subscript(
      value=ast.Name(id=host_name, ctx=ast.Load()),
      slice=ast.Tuple(
        elts=[ast.Name(id=p, ctx=ast.Load()) for p in type_params],
        ctx=ast.Load(),
      ),
    )
  fn = ast.FunctionDef(
    name="__init__",
    args=ast.arguments(
      posonlyargs=[],
      args=[
        ast.arg(arg="self"),
        ast.arg(arg="_host", annotation=copy.deepcopy(host_ann)),
      ],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=[
      ast.Assign(
        targets=[
          ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="_host",
            ctx=ast.Store(),
          )
        ],
        value=ast.Name(id="_host", ctx=ast.Load()),
      ),
      ast.Assign(
        targets=[
          ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="_index",
            ctx=ast.Store(),
          )
        ],
        value=ast.Constant(value=0),
      ),
    ],
    decorator_list=[],
    returns=ast.Constant(value=None),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def _make_iterator_iter() -> ast.FunctionDef:
  fn = ast.FunctionDef(
    name="__iter__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=[ast.Return(value=ast.Name(id="self", ctx=ast.Load()))],
    decorator_list=[],
    returns=ast.Name(id="Self", ctx=ast.Load()),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def _make_iterator_next(element_ann: ast.expr | None) -> ast.FunctionDef:
  self_host = ast.Attribute(
    value=ast.Name(id="self", ctx=ast.Load()),
    attr="_host",
    ctx=ast.Load(),
  )
  self_index = ast.Attribute(
    value=ast.Name(id="self", ctx=ast.Load()),
    attr="_index",
    ctx=ast.Load(),
  )
  body: list[ast.stmt] = [
    ast.If(
      test=ast.Compare(
        left=copy.deepcopy(self_index),
        ops=[ast.GtE()],
        comparators=[
          ast.Call(
            func=ast.Name(id="len", ctx=ast.Load()),
            args=[copy.deepcopy(self_host)],
          )
        ],
      ),
      body=[ast.Raise(exc=ast.Call(func=ast.Name(id="StopIteration", ctx=ast.Load()), args=[]))],
      orelse=[],
    ),
    ast.AnnAssign(
      target=ast.Name(id="value", ctx=ast.Store()),
      annotation=copy.deepcopy(element_ann) if element_ann is not None else ast.Name(id="int", ctx=ast.Load()),
      value=ast.Subscript(
        value=copy.deepcopy(self_host),
        slice=copy.deepcopy(self_index),
      ),
      simple=1,
    ),
    ast.AugAssign(
      target=copy.deepcopy(self_index),
      op=ast.Add(),
      value=ast.Constant(value=1),
    ),
    ast.Return(value=ast.Name(id="value", ctx=ast.Load())),
  ]
  fn = ast.FunctionDef(
    name="__next__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=body,
    decorator_list=[],
    returns=copy.deepcopy(element_ann) if element_ann is not None else None,
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def _make_iterator_class(
  host_info: ClassInfo,
  getitem: ast.FunctionDef,
) -> ast.ClassDef:
  iter_name = f"{host_info.name}_iterator"
  type_params = list(host_info.type_params)
  body: list[ast.stmt] = []
  if type_params:
    body.append(_make_type_element_alias(type_params[0]))
  body.append(_make_iterator_init(host_info.name, type_params=type_params))
  body.append(_make_iterator_iter())
  body.append(_make_iterator_next(copy.deepcopy(getitem.returns)))
  node = ast.ClassDef(
    name=iter_name,
    bases=[],
    keywords=[],
    body=body,
    decorator_list=[],
    type_params=copy.deepcopy(host_info.node.type_params),
  )
  ast.fix_missing_locations(node)
  return node


def _iter_return_annotation(iter_name: str, *, type_params: list[str]) -> ast.expr:
  ann: ast.expr = ast.Name(id=iter_name, ctx=ast.Load())
  if type_params:
    ann = ast.Subscript(
      value=ast.Name(id=iter_name, ctx=ast.Load()),
      slice=ast.Tuple(
        elts=[ast.Name(id=p, ctx=ast.Load()) for p in type_params],
        ctx=ast.Load(),
      ),
    )
  return ann


def _make_host_iter_method(iter_name: str, *, type_params: list[str]) -> ast.FunctionDef:
  ctor = _iter_return_annotation(iter_name, type_params=type_params)
  fn = ast.FunctionDef(
    name="__iter__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=[
      ast.Return(
        value=ast.Call(
          func=ast.Name(id="new", ctx=ast.Load()),
          args=[ast.Name(id="self", ctx=ast.Load())],
        ),
      ),
    ],
    decorator_list=[],
    returns=copy.deepcopy(ctor),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def _insert_class_after(tr: Translator, host: ClassInfo, new_cls: ast.ClassDef) -> None:
  tree = tr.module_asts.get(host.module_path)
  if tree is None:
    return
  for i, stmt in enumerate(tree.body):
    if stmt is host.node:
      tree.body.insert(i + 1, new_cls)
      return


def expand_default_iter(tr: Translator) -> None:
  for info in list(tr.classes.values()):
    if _skip_host(info, tr):
      continue
    if "__iter__" in info.methods or "__iter__" in info.method_overloads:
      continue
    if f"{info.name}_iterator" in tr.classes:
      continue
    getitem = _int_getitem_method(info)
    if getitem is None:
      continue
    len_m = info.methods.get("__len__")
    if len_m is None or not _has_immutable_decorator(len_m):
      continue
    iter_cls = _make_iterator_class(info, getitem)
    _insert_class_after(tr, info, iter_cls)
    iter_info = ClassInfo(iter_cls, info.module_path)
    tr.classes[iter_cls.name] = iter_info
    info.seq_iterator_name = iter_cls.name
    iter_method = _make_host_iter_method(
      iter_cls.name, type_params=list(info.type_params),
    )
    info.node.body.append(iter_method)
    info.methods["__iter__"] = iter_method
    ast.fix_missing_locations(info.node)
