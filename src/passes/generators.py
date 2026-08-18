"""生成器 / 协程：``yield`` / ``yield from`` / ``async def``+``await`` → ``*_generator`` / ``*_coroutine``。"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..translator import Translator

from ..analysis.delegates import is_delegate_definition
from ..analysis.ir import ClassInfo, iter_matmult_marker_names, strip_type_annotation_markers
from ..constant.stdlib_layout import RUNTIME_PKG
from ..analysis.runtime_symbols import (
  BUILTINS_CPP_RUNTIME_FUNCS,
  TRANSLATION_ONLY_FUNCS,
)
from .coroutine_desugar import async_def_to_function
from .decorators import is_context_definition, is_decorator_definition

_MODULE_FUNC_SKIP = TRANSLATION_ONLY_FUNCS

GENERATOR_SUFFIX = "_generator"
COROUTINE_SUFFIX = "_coroutine"
_STATE_FIELD = "_state"
_SEND_FIELD = "_send_value"
_SEND_FLAG = "_send_pending"
_YF_PREFIX = "_yf"
_FOR_PREFIX = "_for"


@dataclass(frozen=True)
class GeneratorTypes:
  """``GeneratorType[Yield, Send, Return]`` 三型参（AST 注解节点）。"""

  yield_ann: ast.expr
  send_ann: ast.expr
  return_ann: ast.expr


def body_has_yield(body: list[ast.stmt]) -> bool:
  for node in ast.walk(ast.Module(body=body, type_ignores=[])):
    if isinstance(node, (ast.Yield, ast.YieldFrom)):
      return True
  return False


def body_has_await(body: list[ast.stmt]) -> bool:
  for node in ast.walk(ast.Module(body=body, type_ignores=[])):
    if isinstance(node, ast.Await):
      return True
  return False


def body_needs_resume_machine(body: list[ast.stmt]) -> bool:
  return body_has_yield(body) or body_has_await(body)


def _leading_docstring_stmt(body: list[ast.stmt]) -> ast.Expr | None:
  if body and isinstance(body[0], ast.Expr):
    val = body[0].value
    if isinstance(val, ast.Constant) and isinstance(val.value, str):
      return body[0]
  return None


def _strip_leading_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
  """生成器/协程状态机勿将前导 docstring ``Expr`` 当作可执行语句。"""
  if _leading_docstring_stmt(body) is not None:
    return body[1:]
  return body


def _body_with_leading_docstring(
  func: ast.FunctionDef, body: list[ast.stmt],
) -> list[ast.stmt]:
  """包装函数保留原 ``def`` 的 docstring，供 ``ast.get_docstring`` → ``///``。"""
  doc = _leading_docstring_stmt(func.body)
  if doc is None:
    return body
  return [copy.deepcopy(doc), *body]


def _stmt_list_needs_suspend(stmts: list[ast.stmt]) -> bool:
  return body_has_yield(stmts) or body_has_await(stmts)


def async_for_needs_suspend(node: ast.AsyncFor) -> bool:
  """``async for`` 在协程 ``__resume`` 中须分态（``await``/``else``/``break`` 标志）。"""
  if node.orelse:
    return True
  return _stmt_list_needs_suspend(node.body)


def _slice_elts(sl: ast.expr) -> list[ast.expr]:
  if isinstance(sl, ast.Tuple):
    return list(sl.elts)
  return [sl]


def _norm_type_ann(ann: ast.expr) -> ast.expr:
  if isinstance(ann, ast.Constant) and ann.value is None:
    return ast.Name(id="PyNone")
  return ann


def _parse_generator_ann(annotation: ast.expr | None) -> GeneratorTypes | None:
  if annotation is None:
    return None
  if not isinstance(annotation, ast.Subscript):
    return None
  if isinstance(annotation.value, ast.Name) and annotation.value.id in (
    "GeneratorType",
    "CoroutineType",
  ):
    elts = _slice_elts(annotation.slice)
    if len(elts) == 3:
      return GeneratorTypes(
        _norm_type_ann(elts[0]),
        _norm_type_ann(elts[1]),
        _norm_type_ann(elts[2]),
      )
    if len(elts) == 2:
      none = ast.Name(id="PyNone")
      return GeneratorTypes(_norm_type_ann(elts[0]), none, _norm_type_ann(elts[1]))
    if len(elts) == 1:
      none = ast.Name(id="PyNone")
      return GeneratorTypes(_norm_type_ann(elts[0]), none, none)
  if (
    isinstance(annotation.value, ast.Name)
    and annotation.value.id == "AsyncGeneratorType"
  ):
    elts = _slice_elts(annotation.slice)
    none = ast.Name(id="PyNone")
    if len(elts) == 2:
      return GeneratorTypes(
        _norm_type_ann(elts[0]),
        _norm_type_ann(elts[1]),
        none,
      )
    if len(elts) == 1:
      return GeneratorTypes(_norm_type_ann(elts[0]), none, none)
  return None


def _infer_yield_ann(body: list[ast.stmt]) -> ast.expr:
  for node in ast.walk(ast.Module(body=body, type_ignores=[])):
    if isinstance(node, ast.Yield):
      if node.value is None:
        return ast.Name(id="PyNone")
      if isinstance(node.value, ast.Constant):
        if isinstance(node.value.value, int):
          return ast.Name(id="int")
        if isinstance(node.value.value, str):
          return ast.Name(id="str")
      break
  for node in ast.walk(ast.Module(body=body, type_ignores=[])):
    if isinstance(node, ast.Return):
      if node.value is None:
        return ast.Name(id="PyNone")
      if isinstance(node.value, ast.Constant) and node.value.value is None:
        return ast.Name(id="PyNone")
  return ast.Name(id="int")


def _infer_return_ann(body: list[ast.stmt]) -> ast.expr:
  for node in ast.walk(ast.Module(body=body, type_ignores=[])):
    if isinstance(node, ast.Return) and node.value is not None:
      if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
        return ast.Name(id="int")
      if isinstance(node.value, ast.Name):
        return ast.Name(id=node.value.id)
      break
  return ast.Constant(value=None)


def generator_types_for(func: ast.FunctionDef, body: list[ast.stmt]) -> GeneratorTypes:
  ann = _parse_generator_ann(func.returns)
  if ann is not None:
    return ann
  y = _infer_yield_ann(body)
  r = _infer_return_ann(body)
  return GeneratorTypes(y, ast.Constant(value=None), r)


def _iter_result_ann(yield_ann: ast.expr, return_ann: ast.expr) -> ast.expr:
  return ast.Subscript(
    value=ast.Name(id="IterResult"),
    slice=ast.Tuple(elts=[copy.deepcopy(yield_ann), copy.deepcopy(return_ann)]),
  )


def _iter_class_for_func(name: str, tr: Translator) -> str | None:
  for suffix in (COROUTINE_SUFFIX, GENERATOR_SUFFIX):
    cn = f"{name}{suffix}"
    if cn in tr.classes:
      return cn
  return None


def _callable_ctor_name(func_name: str, tr: Translator) -> str | None:
  """``Cls(...)`` 构造；内置 ``iter``/``anext`` 等不是类型名。"""
  if func_name in BUILTINS_CPP_RUNTIME_FUNCS:
    return None
  if func_name in tr.classes:
    return func_name
  if func_name and func_name[0].isupper():
    return func_name
  return None


def _nested_stmt_bodies(stmt: ast.stmt) -> list[list[ast.stmt]]:
  """``if``/``while``/``for``/``try``/``match`` 等内层语句表（生成器 hoist 用）。"""
  out: list[list[ast.stmt]] = []
  if isinstance(stmt, (ast.If, ast.While, ast.For, ast.AsyncFor)):
    out.append(stmt.body)
    if stmt.orelse:
      out.append(stmt.orelse)
  elif isinstance(stmt, (ast.Try, ast.TryStar)):
    for handler in stmt.handlers:
      out.append(handler.body)
    if stmt.orelse:
      out.append(stmt.orelse)
    if stmt.finalbody:
      out.append(stmt.finalbody)
  elif isinstance(stmt, ast.Match):
    for case in stmt.cases:
      out.append(case.body)
  return out


def _iter_body_stmts(body: list[ast.stmt]):
  """深度优先遍历函数体（含嵌套块），保持源码顺序。"""
  for stmt in body:
    yield stmt
    for nested in _nested_stmt_bodies(stmt):
      yield from _iter_body_stmts(nested)


def _find_hoisted_assign_value(name: str, body: list[ast.stmt]) -> ast.expr | None:
  fname = _field_name(name)
  for stmt in _iter_body_stmts(body):
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
      t = stmt.targets[0]
      if isinstance(t, ast.Name) and t.id == name:
        return stmt.value
      if (
        isinstance(t, ast.Attribute)
        and isinstance(t.value, ast.Name)
        and t.value.id == "self"
        and t.attr == fname
      ):
        return stmt.value
    if (
      isinstance(stmt, ast.AnnAssign)
      and isinstance(stmt.target, ast.Name)
      and stmt.target.id == name
      and stmt.value is not None
    ):
      return stmt.value
  return None


def _coroutine_element_ann(coro_class: str, tr: Translator) -> ast.expr | None:
  info = tr.classes.get(coro_class)
  if info is None:
    return None
  for node in info.node.body:
    if isinstance(node, ast.TypeAlias) and node.name.id == "Element":
      return copy.deepcopy(node.value)
  return None


def _infer_call_result_ann(expr: ast.expr, tr: Translator) -> ast.expr | None:
  if not isinstance(expr, ast.Call):
    return None
  if isinstance(expr.func, ast.Attribute) and isinstance(expr.func.value, ast.Name):
    cls_name = expr.func.value.id
    info = tr.classes.get(cls_name)
    method = info.methods.get(expr.func.attr) if info is not None else None
    if method is not None and method.returns is not None:
      if isinstance(method.returns, ast.Name) and method.returns.id == "Self":
        return ast.Name(id=cls_name)
      return copy.deepcopy(method.returns)
  if not isinstance(expr.func, ast.Name):
    return None
  name = expr.func.id
  if name == "anext" and len(expr.args) == 1:
    arg = expr.args[0]
    if (
      isinstance(arg, ast.Call)
      and isinstance(arg.func, ast.Name)
      and arg.func.id == "aiter"
      and len(arg.args) == 1
    ):
      inner = arg.args[0]
      if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
        cn = _iter_class_for_func(inner.func.id, tr)
        if cn is not None:
          elem = _coroutine_element_ann(cn, tr)
          if elem is not None:
            return _iter_result_ann(elem, ast.Name(id="PyNone"))
  if name == "next" and len(expr.args) == 1:
    arg = expr.args[0]
    if (
      isinstance(arg, ast.Call)
      and isinstance(arg.func, ast.Name)
      and arg.func.id == "iter"
      and len(arg.args) == 1
    ):
      inner = arg.args[0]
      if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
        cn = _iter_class_for_func(inner.func.id, tr)
        if cn is not None:
          elem = _coroutine_element_ann(cn, tr)
          if elem is not None:
            return _iter_result_ann(elem, ast.Name(id="PyNone"))
  ctor = _callable_ctor_name(name, tr)
  if ctor is not None:
    return ast.Name(id=ctor)
  return None


def _find_hoisted_assign_ann(name: str, body: list[ast.stmt]) -> ast.expr | None:
  """``out: list[Self] = []`` 等注解优先于 ``[]``  ctor 推断（含 ``while``/``if`` 内）。"""
  fname = _field_name(name)
  for stmt in _iter_body_stmts(body):
    if not isinstance(stmt, ast.AnnAssign) or stmt.annotation is None:
      continue
    t = stmt.target
    if isinstance(t, ast.Name) and t.id == name:
      return stmt.annotation
    if (
      isinstance(t, ast.Attribute)
      and isinstance(t.value, ast.Name)
      and t.value.id == "self"
      and t.attr == fname
    ):
      return stmt.annotation
  return None


def _coroutine_class_return_ann(coro_class: str, tr: Translator) -> ast.expr | None:
  info = tr.classes.get(coro_class)
  if info is None:
    return None
  for node in info.node.body:
    if isinstance(node, ast.TypeAlias) and node.name.id == "ReturnType":
      return copy.deepcopy(node.value)
  return None


def _infer_await_completion_ann(
  inner: ast.expr,
  tr: Translator,
  body: list[ast.stmt] | None = None,
  *,
  host_class: str | None = None,
  current_gen: str | None = None,
  ann_body: list[ast.stmt] | None = None,
  params: list[ast.arg] | None = None,
  target_ann: ast.expr | None = None,
) -> ast.expr | None:
  """``yield from ….__await__()`` 完成后的赋值类型（``await`` / ``__aenter__`` 等）。"""
  if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
    if inner.func.attr == "__aenter__":
      recv = inner.func.value
      info = tr._class_info_for_expr(recv)
      if info is None and isinstance(recv, ast.Name) and body is not None:
        ctor = _var_ctor_class(recv.id, body, tr)
        if ctor is not None:
          info = tr.classes.get(ctor)
      if info is not None:
        ret = tr._receiver_method_return_cpp_type(info, "__aenter__")
        if ret and ret != "Self" and not ret.endswith("_coroutine") and "CoroutineType" not in ret:
          from ..analysis.ir import strip_cpp_ref, cpp_ident
          ret = strip_cpp_ref(ret)
          if ret in ("int", cpp_ident("int")):
            return ast.Name(id="int")
          return ast.Name(id=ret.rsplit("::", 1)[-1])
        from ..passes.generators import COROUTINE_SUFFIX
        for coro_name in (
          f"{info.name}___aenter__{COROUTINE_SUFFIX}",
          f"{info.name}__aenter__{COROUTINE_SUFFIX}",
        ):
          coro_ret = _coroutine_class_return_ann(coro_name, tr)
          if coro_ret is not None:
            return coro_ret
        return ast.Name(id=info.cpp_name())
    if inner.func.attr == "__await__":
      return _infer_await_completion_ann(
        inner.func.value,
        tr,
        body,
        host_class=host_class,
        current_gen=current_gen,
        ann_body=ann_body,
        params=params,
        target_ann=target_ann,
      )
  if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
    from ..passes.generators import COROUTINE_SUFFIX
    coro_name = f"{inner.func.id}{COROUTINE_SUFFIX}"
    ret = _coroutine_class_return_ann(coro_name, tr)
    if ret is not None:
      return ret
  if isinstance(inner, ast.Call):
    it_ann = _infer_iter_type(
      inner,
      tr,
      body or [],
      host_class=host_class,
      current_gen=current_gen,
      ann_body=ann_body,
      params=params,
      target_ann=target_ann,
    )
    if isinstance(it_ann, ast.Name):
      ret = _coroutine_class_return_ann(it_ann.id, tr)
      if ret is not None:
        return ret
    if (
      isinstance(it_ann, ast.Subscript)
      and isinstance(it_ann.value, ast.Name)
      and it_ann.value.id == "_TaskAwaitIter"
    ):
      if isinstance(it_ann.slice, ast.Constant) and it_ann.slice.value is None:
        return ast.Name(id="PyNone")
      return copy.deepcopy(it_ann.slice)
  return None


def _infer_yield_from_result_ann(
  expr: ast.expr,
  tr: Translator,
  body: list[ast.stmt] | None = None,
  *,
  host_class: str | None = None,
  current_gen: str | None = None,
  ann_body: list[ast.stmt] | None = None,
  params: list[ast.arg] | None = None,
  target_ann: ast.expr | None = None,
) -> ast.expr | None:
  if not isinstance(expr, ast.YieldFrom):
    return None
  inner = expr.value
  if (
    isinstance(inner, ast.Call)
    and isinstance(inner.func, ast.Attribute)
    and inner.func.attr == "__await__"
  ):
    inner = inner.func.value
  ta = _task_await_iter_ann(inner, tr)
  if isinstance(ta, ast.Subscript) and isinstance(ta.value, ast.Name):
    if ta.value.id == "_TaskAwaitIter":
      if isinstance(ta.slice, ast.Constant) and ta.slice.value is None:
        return ast.Name(id="PyNone")
      return copy.deepcopy(ta.slice)
  completion = _infer_await_completion_ann(
    inner,
    tr,
    body,
    host_class=host_class,
    current_gen=current_gen,
    ann_body=ann_body,
    params=params,
    target_ann=target_ann,
  )
  if completion is not None:
    return completion
  return None


def _infer_hoisted_field_ann(
  name: str,
  body: list[ast.stmt],
  tr: Translator,
  *,
  host_class: str | None = None,
  current_gen: str | None = None,
  ann_body: list[ast.stmt] | None = None,
  params: list[ast.arg] | None = None,
  target_ann: ast.expr | None = None,
) -> ast.expr:
  ann = _find_hoisted_assign_ann(name, body)
  if ann is not None:
    return copy.deepcopy(ann)
  val = _find_hoisted_assign_value(name, body)
  if val is not None:
    if isinstance(val, ast.Name):
      src_ann = _infer_hoisted_field_ann(
        val.id,
        body,
        tr,
        host_class=host_class,
        current_gen=current_gen,
        ann_body=ann_body,
        params=params,
        target_ann=target_ann,
      )
      if not (isinstance(src_ann, ast.Name) and src_ann.id == "int"):
        return copy.deepcopy(src_ann)
    yf_ann = _infer_yield_from_result_ann(
      val,
      tr,
      body,
      host_class=host_class,
      current_gen=current_gen,
      ann_body=ann_body,
      params=params,
      target_ann=target_ann,
    )
    if yf_ann is not None:
      return yf_ann
    inferred = _infer_call_result_ann(val, tr)
    if inferred is not None:
      return inferred
  cls = _var_ctor_class(name, body, tr)
  if cls is not None:
    return ast.Name(id=cls)
  for stmt in _iter_body_stmts(body):
    if isinstance(stmt, ast.For) and isinstance(stmt.target, ast.Name):
      if stmt.target.id == name:
        it_ann = _infer_iter_type(stmt.iter, tr, body)
        if (
          isinstance(it_ann, ast.Subscript)
          and isinstance(it_ann.value, ast.Name)
          and it_ann.value.id == "ListIterator"
        ):
          return copy.deepcopy(it_ann.slice)
  return ast.Name(id="int")


def _hoisted_field_needs_zero_init(ann: ast.expr) -> bool:
  match ann:
    case ast.Name(id="int"):
      return True
    case ast.Constant(value=v) if v is None or isinstance(v, int):
      return True
  return False


def _field_ctor_class(fname: str, body: list[ast.stmt], tr: Translator) -> str | None:
  for stmt in body:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
      continue
    t = stmt.targets[0]
    if (
      isinstance(t, ast.Attribute)
      and isinstance(t.value, ast.Name)
      and t.value.id == "self"
      and t.attr == fname
      and isinstance(stmt.value, ast.Call)
      and isinstance(stmt.value.func, ast.Name)
    ):
      return _callable_ctor_name(stmt.value.func.id, tr)
  return None


def _var_ctor_class(name: str, body: list[ast.stmt], tr: Translator) -> str | None:
  for stmt in _iter_body_stmts(body):
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == name:
      if isinstance(stmt.annotation, ast.Name):
        return stmt.annotation.id
      if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name):
        return _callable_ctor_name(stmt.value.func.id, tr)
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
      continue
    t = stmt.targets[0]
    if isinstance(t, ast.Name) and t.id == name:
      if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name):
        return _callable_ctor_name(stmt.value.func.id, tr)
    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
      if t.attr == _field_name(name):
        if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name):
          return _callable_ctor_name(stmt.value.func.id, tr)
  return None


def _list_iterator_ann(elem: ast.expr) -> ast.expr:
  return ast.Subscript(
    value=ast.Name(id="ListIterator"),
    slice=copy.deepcopy(elem),
  )


def _iter_ann_from_param_storage_ann(param_ann: ast.expr) -> ast.expr:
  """形参 ``list[T]`` 等存储类型 → ``yield from`` / ``for`` 用的迭代器注解。"""
  match param_ann:
    case ast.Subscript(value=ast.Name(id="list"), slice=elem):
      return _list_iterator_ann(elem)
    case ast.Subscript(value=ast.Name(id="Task"), slice=elem):
      return ast.Subscript(
        value=ast.Name(id="_TaskAwaitIter"),
        slice=copy.deepcopy(elem),
      )
  return param_ann


def _scandir_iter_ann() -> ast.expr:
  """``os.scandir`` → ``ScandirIterator``（``@native_name`` C++ 基名）。"""
  return ast.Name(id="ScandirIterator")


def _module_function_return_ann(tr: Translator, module_path: str | None, name: str) -> ast.expr | None:
  module_functions = getattr(tr, "module_functions", ())
  for f_mp, func in module_functions:
    if (
      module_path is not None
      and f_mp == module_path
      and func.name == name
      and func.returns is not None
    ):
      return copy.deepcopy(func.returns)
  hits = [
    func.returns
    for _f_mp, func in module_functions
    if func.name == name and func.returns is not None
  ]
  if len(hits) == 1:
    return copy.deepcopy(hits[0])
  return None


def _run_thread_return_ann(arg: ast.expr, tr: Translator) -> ast.expr:
  if isinstance(arg, ast.Name):
    binding = tr._effective_import_bindings().get(arg.id)
    if binding is not None and binding.kind == "function":
      hit = _module_function_return_ann(tr, binding.module_path, binding.symbol)
      if hit is not None:
        return hit
    hit = _module_function_return_ann(tr, tr._active_module_path(), arg.id)
    if hit is not None:
      return hit
  return ast.Name(id="int")


def _task_await_iter_ann(inner: ast.expr, tr: Translator) -> ast.expr | None:
  """``Task.sleep/gather/runThread(...)`` → ``_TaskAwaitIter[…]``（``__await__`` 接收者）。"""
  if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Attribute):
    return None
  recv = inner.func.value
  if not isinstance(recv, ast.Name) or recv.id != "Task":
    return None
  meth = inner.func.attr
  if meth == "sleep":
    return ast.Subscript(
      value=ast.Name(id="_TaskAwaitIter"),
      slice=ast.Constant(value=None),
    )
  if meth in ("waitRead", "waitWrite"):
    return ast.Subscript(
      value=ast.Name(id="_TaskAwaitIter"),
      slice=ast.Constant(value=None),
    )
  if meth == "gather":
    return ast.Subscript(
      value=ast.Name(id="_TaskAwaitIter"),
      slice=ast.Subscript(value=ast.Name(id="list"), slice=ast.Name(id="int")),
    )
  if meth == "runThread":
    elem: ast.expr = ast.Name(id="int")
    if inner.args:
      elem = _run_thread_return_ann(inner.args[0], tr)
    return ast.Subscript(
      value=ast.Name(id="_TaskAwaitIter"),
      slice=elem,
    )
  return None


def _infer_iter_type(
  expr: ast.expr,
  tr: Translator,
  body: list[ast.stmt],
  *,
  host_class: str | None = None,
  current_gen: str | None = None,
  ann_body: list[ast.stmt] | None = None,
  params: list[ast.arg] | None = None,
  target_ann: ast.expr | None = None,
) -> ast.expr:
  lookup_body = ann_body if ann_body is not None else body
  match expr:
    case ast.Call(func=ast.Attribute(value=inner, attr="__await__")):
      ta = _task_await_iter_ann(inner, tr)
      if ta is not None:
        return ta
      return _infer_iter_type(
        inner, tr, body, host_class=host_class, current_gen=current_gen,
        ann_body=ann_body, params=params, target_ann=target_ann,
      )
    case ast.Call(func=ast.Attribute(value=ast.Name(id="Task"), attr=meth)) if meth == "sleep":
      none = ast.Constant(value=None)
      return ast.Subscript(value=ast.Name(id="_TaskAwaitIter"), slice=none)
    case ast.Call(func=ast.Attribute(value=ast.Name(id="Task"), attr=meth)) if meth in ("waitRead", "waitWrite"):
      none = ast.Constant(value=None)
      return ast.Subscript(value=ast.Name(id="_TaskAwaitIter"), slice=none)
    case ast.Call(func=ast.Attribute(value=ast.Name(id="Task"), attr=meth)) if meth == "runThread":
      elem: ast.expr = ast.Name(id="int")
      if expr.args:
        elem = _run_thread_return_ann(expr.args[0], tr)
      return ast.Subscript(value=ast.Name(id="_TaskAwaitIter"), slice=elem)
    case ast.Call(func=ast.Attribute(value=ast.Name(id="self"), attr=meth)):
      if host_class is not None:
        return ast.Name(id=f"{host_class}_{meth}{COROUTINE_SUFFIX}")
    case ast.Call(
      func=ast.Attribute(
        value=ast.Attribute(value=ast.Name(id="self"), attr=host_field),
        attr=meth,
      ),
    ) if host_class is not None and host_field == _field_name("self"):
      return ast.Name(id=f"{host_class}_{meth}{COROUTINE_SUFFIX}")
    case ast.Call(func=ast.Attribute(value=ast.Name(id=var), attr=meth)):
      if var == "new":
        target_cls = _class_name_from_ann(target_ann)
        if target_cls is not None:
          return ast.Name(id=f"{target_cls}_{meth}{COROUTINE_SUFFIX}")
      param_ann = _param_ann_by_name(params, var)
      cls_name = _class_name_from_ann(param_ann)
      if cls_name is not None:
        storage_ann = _method_coroutine_storage_ann(tr, cls_name, meth)
        if storage_ann is not None:
          return storage_ann
        return ast.Name(id=f"{cls_name}_{meth}{COROUTINE_SUFFIX}")
      if host_class is not None and var in ("Self", host_class):
        elem = _static_method_returns_list_elem(host_class, meth, tr)
        if elem is not None:
          return _list_iterator_ann(elem)
        gen_name = f"{host_class}_{meth}{GENERATOR_SUFFIX}"
        if gen_name in tr.classes:
          return ast.Name(id=gen_name)
        host_info = tr.classes.get(host_class)
        host_m = host_info.methods.get(meth) if host_info is not None else None
        if host_m is not None and _parse_generator_ann(host_m.returns):
          return ast.Name(id=gen_name)
      cls = _var_ctor_class(var, body, tr)
      if cls is not None:
        return ast.Name(id=f"{cls}_{meth}{COROUTINE_SUFFIX}")
    case ast.Call(
      func=ast.Attribute(
        value=ast.Attribute(
          value=ast.Attribute(value=ast.Name(id="self"), attr=host_attr),
          attr=field,
        ),
        attr=meth,
      ),
    ) if host_class is not None and host_attr == _field_name("self"):
      field_ann = _host_field_ann(tr, host_class, field)
      field_cls = _class_name_from_ann(field_ann)
      if field_cls is not None:
        storage_ann = _method_coroutine_storage_ann(tr, field_cls, meth)
        if storage_ann is not None:
          return storage_ann
        return ast.Name(id=f"{field_cls}_{meth}{COROUTINE_SUFFIX}")
    case ast.Call(
      func=ast.Attribute(
        value=ast.Attribute(value=ast.Name(id="self"), attr=fname),
        attr=meth,
      ),
    ):
      param_ann = _param_ann_by_name(params, fname)
      cls_name = _class_name_from_ann(param_ann)
      if cls_name is not None:
        storage_ann = _method_coroutine_storage_ann(tr, cls_name, meth)
        if storage_ann is not None:
          return storage_ann
        return ast.Name(id=f"{cls_name}_{meth}{COROUTINE_SUFFIX}")
      if fname.startswith("g_"):
        local_ann = _find_hoisted_assign_ann(fname[2:], lookup_body)
        local_cls = _class_name_from_ann(local_ann)
        if local_cls is not None:
          storage_ann = _method_coroutine_storage_ann(tr, local_cls, meth)
          if storage_ann is not None:
            return storage_ann
          return ast.Name(id=f"{local_cls}_{meth}{COROUTINE_SUFFIX}")
      if host_class is not None:
        field_ann = _host_field_ann(tr, host_class, fname)
        field_cls = _class_name_from_ann(field_ann)
        if field_cls is not None:
          storage_ann = _method_coroutine_storage_ann(tr, field_cls, meth)
          if storage_ann is not None:
            return storage_ann
          return ast.Name(id=f"{field_cls}_{meth}{COROUTINE_SUFFIX}")
      cls = _field_ctor_class(fname, body, tr)
      if cls is None and host_class is not None and fname == _field_name("self"):
        cls = host_class
      if cls is not None:
        return ast.Name(id=f"{cls}_{meth}{COROUTINE_SUFFIX}")
    case ast.Call(
      func=ast.Attribute(
        value=ast.Subscript(
          value=ast.Attribute(value=ast.Name(id="self"), attr=fname),
          slice=ast.Constant(value=0),
        ),
        attr=meth,
      ),
    ):
      param_ann = _param_ann_by_name(params, fname)
      cls_name = _class_name_from_ann(param_ann)
      if cls_name is not None:
        storage_ann = _method_coroutine_storage_ann(tr, cls_name, meth)
        if storage_ann is not None:
          return storage_ann
        return ast.Name(id=f"{cls_name}_{meth}{COROUTINE_SUFFIX}")
    case ast.Call(func=ast.Name(id=name)):
      active_module_path = (
        tr._active_module_path() if hasattr(tr, "_active_module_path") else None
      )
      ret_ann = _module_function_return_ann(tr, active_module_path, name)
      if (
        isinstance(ret_ann, ast.Subscript)
        and isinstance(ret_ann.value, ast.Name)
        and ret_ann.value.id == "list"
      ):
        return _list_iterator_ann(ret_ann.slice)
      cn = _iter_class_for_func(name, tr)
      if cn is not None:
        return ast.Name(id=cn)
      if current_gen is not None and current_gen == f"{name}{GENERATOR_SUFFIX}":
        return ast.Name(id=current_gen)
      if name == "listDir":
        return _list_iterator_ann(ast.Name(id="str"))
      if name == "scandir":
        return _scandir_iter_ann()
    case ast.Attribute(
      value=ast.Attribute(value=ast.Name(id="self"), attr=host_attr),
      attr=field,
    ) if host_class is not None and host_attr == _field_name("self"):
      ann = _host_field_ann(tr, host_class, field)
      if ann is not None and _parse_generator_ann(ann) is not None:
        return ann
    case ast.Name(id=var):
      param_ann = _param_ann_by_name(params, var)
      if param_ann is not None:
        return _iter_ann_from_param_storage_ann(param_ann)
      ann = _find_hoisted_assign_ann(var, lookup_body)
      if ann is not None:
        match ann:
          case ast.Subscript(value=ast.Name(id="list"), slice=elem):
            return _list_iterator_ann(elem)
      val = _find_hoisted_assign_value(var, lookup_body)
      if val is not None:
        match val:
          case ast.Call(func=ast.Name(id="listDir")):
            return _list_iterator_ann(ast.Name(id="str"))
          case ast.Call(func=ast.Name(id="scandir")):
            return _scandir_iter_ann()
    case ast.Attribute(value=ast.Name(id="self"), attr=fname):
      param_ann = _param_ann_by_name(params, fname)
      if param_ann is not None:
        return _iter_ann_from_param_storage_ann(param_ann)
      if fname.startswith("g_"):
        ann = _find_hoisted_assign_ann(fname[2:], lookup_body)
        if ann is not None:
          return _iter_ann_from_param_storage_ann(ann)
    case ast.Name(id="xs"):
      return _list_iterator_ann(ast.Name(id="int"))
  return _list_iterator_ann(ast.Name(id="int"))


def _collect_hoisted_names(body: list[ast.stmt], params: set[str]) -> list[str]:
  seen: set[str] = set()
  order: list[str] = []

  class V(ast.NodeVisitor):
    def visit_Name(self, node: ast.Name) -> None:
      if isinstance(node.ctx, ast.Store) and node.id not in params and node.id != "self":
        if node.id not in seen:
          seen.add(node.id)
          order.append(node.id)

  for stmt in body:
    V().visit(stmt)
  return order


def _host_class_from_gen_name(gen_name: str, func_name: str) -> str | None:
  """``str_xsplit_generator`` / ``str_foo_coroutine`` → ``str``。"""
  for suffix in (GENERATOR_SUFFIX, COROUTINE_SUFFIX):
    suf = f"_{func_name}{suffix}"
    if gen_name.endswith(suf):
      return gen_name[: -len(suf)]
  return None


def _substitute_host_self_in_ann(
  ann: ast.expr | None,
  host_class: str | None,
  tr: Translator,
) -> ast.expr | None:
  """生成器 ``__init__`` 形参 ``Self`` → 宿主 C++ 基名（``PyStr`` 等），勿解析为 ``*_generator``。"""
  if ann is None or host_class is None:
    return ann
  host_info = tr.classes.get(host_class)
  if host_info is None:
    return ann
  host_cpp = host_info.cpp_name().partition("<")[0].strip()

  class _Repl(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.expr:
      if node.id == "Self":
        return ast.Name(id=host_cpp, ctx=node.ctx)
      return node

  return _Repl().visit(copy.deepcopy(ann))


def _host_substitute_ann(
  ann: ast.expr,
  host_class: str | None,
  tr: Translator,
) -> ast.expr:
  if host_class is None:
    return ann
  return _substitute_host_self_in_ann(ann, host_class, tr) or ann


def _static_method_returns_list_elem(
  host_class: str,
  meth: str,
  tr: Translator,
) -> ast.expr | None:
  """``Self._glob_select`` 等 ``@staticmethod`` 返回 ``list[T]`` → 迭代 ``T``。"""
  info = tr.classes.get(host_class)
  if info is None:
    return None
  method = info.methods.get(meth)
  if method is None or method.returns is None:
    return None
  ret = method.returns
  if (
    isinstance(ret, ast.Subscript)
    and isinstance(ret.value, ast.Name)
    and ret.value.id == "list"
  ):
    return _host_substitute_ann(copy.deepcopy(ret.slice), host_class, tr)
  return None


def _make_init(
  params: list[ast.arg],
  hoisted: list[str],
  yf_fields: list[tuple[str, ast.expr]],
  for_fields: list[tuple[str, ast.expr]],
  send_ann: ast.expr,
  *,
  resume_body: list[ast.stmt],
  ann_body: list[ast.stmt],
  host_class: str | None = None,
  current_gen: str | None = None,
  host_field: str | None = None,
  ref_params: set[str] | None = None,
  tr: Translator,
) -> ast.FunctionDef:
  body: list[ast.stmt] = []
  host_param = "_py2cpp_host"
  ref_params = ref_params or set()
  body.append(
    ast.Assign(
      targets=[ast.Attribute(ast.Name(id="self"), _STATE_FIELD, ast.Store())],
      value=ast.Constant(value=0),
    )
  )
  body.append(
    ast.Assign(
      targets=[ast.Attribute(ast.Name(id="self"), _SEND_FLAG, ast.Store())],
      value=ast.Constant(value=False),
    )
  )
  send_init = ast.Constant(value=None)
  if isinstance(send_ann, ast.Name) and send_ann.id == "PyNone":
    send_init = ast.Call(func=ast.Name(id="PyNone"), args=[])
  elif isinstance(send_ann, ast.Name) and send_ann.id == "int":
    send_init = ast.Constant(value=0)
  body.append(
    ast.AnnAssign(
      target=ast.Attribute(ast.Name(id="self"), _SEND_FIELD, ast.Store()),
      annotation=copy.deepcopy(send_ann),
      value=send_init,
      simple=1,
    )
  )
  for i, _ in enumerate(yf_fields):
    body.append(
      ast.Assign(
        targets=[
          ast.Attribute(ast.Name(id="self"), f"{_YF_PREFIX}{i}_active", ast.Store())
        ],
        value=ast.Constant(value=False),
      )
    )
  for i, _ in enumerate(for_fields):
    body.append(
      ast.Assign(
        targets=[
          ast.Attribute(ast.Name(id="self"), f"{_FOR_PREFIX}{i}_active", ast.Store())
        ],
        value=ast.Constant(value=False),
      )
    )
  if host_field and host_class:
    body.append(
      ast.Assign(
        targets=[
          ast.Attribute(ast.Name(id="self"), host_field, ast.Store()),
        ],
        value=ast.Name(id=host_param, ctx=ast.Load()),
      )
    )
  for arg in params:
    if arg.arg == "self":
      continue
    ann = arg.annotation or ast.Name(id="int")
    ann = _substitute_host_self_in_ann(ann, host_class, tr) or ann
    value: ast.expr = ast.Name(id=arg.arg)
    if arg.arg in ref_params:
      field_ann = _ref_param_field_ann(ann)
      if field_ann is not None:
        ann = field_ann
        value = ast.Call(
          func=ast.Name(id="id", ctx=ast.Load()),
          args=[ast.Name(id=arg.arg, ctx=ast.Load())],
          keywords=[],
        )
    body.append(
      ast.AnnAssign(
        target=ast.Attribute(ast.Name(id="self"), arg.arg, ast.Store()),
        annotation=copy.deepcopy(ann),
        value=value,
        simple=1,
      )
    )
  for name in hoisted:
    fname = _field_name(name)
    cls = _field_ctor_class(fname, resume_body, tr)
    if cls:
      body.append(
        ast.Assign(
          targets=[ast.Attribute(ast.Name(id="self"), fname, ast.Store())],
          value=ast.Call(func=ast.Name(id=cls), args=[]),
        )
      )
    elif _hoisted_field_needs_zero_init(
      _infer_hoisted_field_ann(
        name,
        ann_body,
        tr,
        host_class=host_class,
        current_gen=current_gen,
        ann_body=ann_body,
        params=params,
      )
    ):
      body.append(
        ast.Assign(
          targets=[ast.Attribute(ast.Name(id="self"), fname, ast.Store())],
          value=ast.Constant(value=0),
        )
      )
  init_params = [ast.arg(arg="self")]
  if host_field and host_class:
    host_info = tr.classes.get(host_class)
    host_ann = ast.Name(
      id=host_info.cpp_name() if host_info is not None else host_class,
      ctx=ast.Load(),
    )
    init_params.append(ast.arg(arg=host_param, annotation=host_ann))
  for arg in params:
    if arg.arg == "self":
      continue
    ann = _substitute_host_self_in_ann(arg.annotation, host_class, tr) or arg.annotation
    init_params.append(
      ast.arg(
        arg=arg.arg,
        annotation=copy.deepcopy(ann) if ann is not None else None,
      ),
    )
  return ast.FunctionDef(
    name="__init__",
    args=ast.arguments(
      posonlyargs=[],
      args=init_params,
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    ),
    body=body,
    decorator_list=[],
    returns=ast.Constant(value=None),
  )


def _iter_field_uses_copy_from(
  it_field: str,
  class_info,
) -> bool:
  """``PyListIterator`` 等容器迭代器用 ``copyFrom``；原生/子生成器用 ``=``。"""
  if class_info is None:
    return True
  from ..analysis.type_emit import field_ann_ast, field_storage_cpp

  ann = field_ann_ast(class_info, it_field)
  if ann is not None:
    return _yield_from_iter_uses_assign(ann)
  for stmt in class_info.node.body:
    if (
      isinstance(stmt, ast.AnnAssign)
      and isinstance(stmt.target, ast.Attribute)
      and isinstance(stmt.target.value, ast.Name)
      and stmt.target.value.id == "self"
      and stmt.target.attr == it_field
    ):
      return _yield_from_iter_uses_assign(stmt.annotation)
  ft = field_storage_cpp(class_info, it_field)
  if ft:
    if "PyListIterator" in ft:
      return True
    if "PyCoroutine" in ft or "PyGenerator" in ft or "PyAsyncGenerator" in ft:
      return False
    if "ScandirIterator" in ft:
      return False
    return not (ft.endswith(GENERATOR_SUFFIX) or ft.endswith(COROUTINE_SUFFIX))
  return True


def _yield_from_iter_uses_assign(ann: ast.expr) -> bool:
  """容器迭代器用 ``copyFrom`` 绑定 owner；子生成器/协程/原生迭代器用复制赋值。"""
  match ann:
    case ast.Name(id=name):
      if name in ("ScandirIterator", "ScandirIterator"):
        return False
      return not (
        name.endswith(GENERATOR_SUFFIX) or name.endswith(COROUTINE_SUFFIX)
      )
    case ast.Subscript(value=ast.Name(id=name)):
      if name in ("GeneratorType", "CoroutineType", "AsyncGeneratorType"):
        return False
      if name == "_TaskAwaitIter":
        return False
      return True
    case _:
      return True


def _target_ann_for_yield_from_field(
  target: ast.expr,
  *,
  ann_body: list[ast.stmt] | None,
  params: list[ast.arg] | None,
) -> ast.expr | None:
  lookup_body = ann_body or []
  if isinstance(target, ast.Name):
    ann = _find_hoisted_assign_ann(target.id, lookup_body)
    if ann is not None:
      return copy.deepcopy(ann)
    return _param_ann_by_name(params, target.id)
  if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
    if target.value.id == "self":
      if target.attr.startswith("g_"):
        ann = _find_hoisted_assign_ann(target.attr[2:], lookup_body)
        if ann is not None:
          return copy.deepcopy(ann)
      return _param_ann_by_name(params, target.attr)
  return None


def _yield_from_target_ann_by_id(
  body: list[ast.stmt],
  *,
  ann_body: list[ast.stmt] | None,
  params: list[ast.arg] | None,
) -> dict[int, ast.expr]:
  out: dict[int, ast.expr] = {}

  class V(ast.NodeVisitor):
    def _record(self, target: ast.expr, value: ast.expr | None) -> None:
      if not isinstance(value, ast.YieldFrom):
        return
      ann = _target_ann_for_yield_from_field(
        target, ann_body=ann_body, params=params,
      )
      if ann is not None:
        out[id(value)] = ann

    def visit_Assign(self, node: ast.Assign) -> None:
      if len(node.targets) == 1:
        self._record(node.targets[0], node.value)
      self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
      if node.value is not None:
        ann = node.annotation or _target_ann_for_yield_from_field(
          node.target, ann_body=ann_body, params=params,
        )
        if isinstance(node.value, ast.YieldFrom) and ann is not None:
          out[id(node.value)] = copy.deepcopy(ann)
      self.generic_visit(node)

  for stmt in body:
    V().visit(stmt)
  return out


def _yield_from_fields(
  body: list[ast.stmt],
  tr: Translator,
  *,
  host_class: str | None = None,
  current_gen: str | None = None,
  ann_body: list[ast.stmt] | None = None,
  params: list[ast.arg] | None = None,
) -> list[tuple[str, ast.expr]]:
  out: list[tuple[str, ast.expr]] = []
  target_anns = _yield_from_target_ann_by_id(
    body, ann_body=ann_body, params=params,
  )

  class V(ast.NodeVisitor):
    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
      out.append((
        f"{_YF_PREFIX}{len(out)}_it",
        _infer_iter_type(
          node.value, tr, body,
          host_class=host_class, current_gen=current_gen, ann_body=ann_body,
          params=params, target_ann=target_anns.get(id(node)),
        ),
      ))
      self.generic_visit(node)

  for stmt in body:
    V().visit(stmt)
  return out


def _param_ann_by_name(params: list[ast.arg] | None, name: str) -> ast.expr | None:
  if not params:
    return None
  for arg in params:
    if arg.arg == name and arg.annotation is not None:
      return copy.deepcopy(arg.annotation)
  return None


def _class_name_from_ann(ann: ast.expr | None) -> str | None:
  if isinstance(ann, ast.Name):
    return ann.id
  if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.MatMult):
    return _class_name_from_ann(ann.left)
  return None


def _host_field_ann(tr: Translator, host_class: str, field: str) -> ast.expr | None:
  from ..analysis.type_emit import field_ann_ast

  info = tr.classes.get(host_class)
  if info is None:
    return None
  ann = field_ann_ast(info, field)
  if isinstance(ann, ast.expr):
    return copy.deepcopy(ann)
  for stmt in info.node.body:
    if (
      isinstance(stmt, ast.AnnAssign)
      and isinstance(stmt.target, ast.Name)
      and stmt.target.id == field
      and isinstance(stmt.annotation, ast.expr)
    ):
      return copy.deepcopy(stmt.annotation)
  return None


def _class_method_node(
  info: ClassInfo,
  meth: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
  method = info.methods.get(meth)
  if method is not None:
    return method
  for stmt in info.node.body:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == meth:
      return stmt
  return None


def _single_return_value(func: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr | None:
  body = _strip_leading_docstring(list(func.body))
  if len(body) != 1:
    return None
  stmt = body[0]
  if not isinstance(stmt, ast.Return) or stmt.value is None:
    return None
  return stmt.value


def _forwarded_method_iter_ann(
  tr: Translator,
  class_name: str,
  method: ast.FunctionDef | ast.AsyncFunctionDef,
) -> ast.expr | None:
  if method.returns is not None:
    return None
  expr = _single_return_value(method)
  if not isinstance(expr, ast.Call):
    return None
  if not isinstance(expr.func, ast.Attribute):
    return None
  recv = expr.func.value
  if not (
    isinstance(recv, ast.Attribute)
    and isinstance(recv.value, ast.Name)
    and recv.value.id == "self"
  ):
    return None
  field_ann = _host_field_ann(tr, class_name, recv.attr)
  field_cls = _class_name_from_ann(field_ann)
  if field_cls is None:
    return None
  return _method_coroutine_storage_ann(tr, field_cls, expr.func.attr)


def _method_coroutine_storage_ann(
  tr: Translator, class_name: str, meth: str,
) -> ast.expr | None:
  info = tr.classes.get(class_name)
  if info is None:
    return None
  method = _class_method_node(info, meth)
  if method is None:
    return None
  if isinstance(method, ast.AsyncFunctionDef):
    return ast.Name(id=f"{class_name}_{meth}{COROUTINE_SUFFIX}")
  if method.returns is None:
    return _forwarded_method_iter_ann(tr, class_name, method)
  if isinstance(method.returns, ast.Name) and method.returns.id.endswith(COROUTINE_SUFFIX):
    return copy.deepcopy(method.returns)
  if _parse_generator_ann(method.returns) is not None:
    return copy.deepcopy(method.returns)
  return None


def _for_iter_needs_seq_hoist(expr: ast.expr) -> bool:
  """``for x in expr`` 中 ``expr`` 为非常量名且产出 ``ListIterator`` 时须持久化 ``list``。"""
  return not isinstance(expr, ast.Name)


def _list_ann_from_iter_ann(iter_ann: ast.expr) -> ast.expr | None:
  if (
    isinstance(iter_ann, ast.Subscript)
    and isinstance(iter_ann.value, ast.Name)
    and iter_ann.value.id == "ListIterator"
  ):
    return ast.Subscript(
      value=ast.Name(id="list"),
      slice=copy.deepcopy(iter_ann.slice),
    )
  return None


def _list_ann_from_generator_name(
  gen_name: str, tr: Translator,
) -> tuple[ast.expr, ast.expr] | None:
  """分态 ``for`` 不能嵌套生成器成员，物化 ``list`` + ``ListIterator``。"""
  info = tr.classes.get(gen_name)
  if info is not None:
    elem = info.type_aliases.get("Element")
    if elem is not None:
      elem_ann = copy.deepcopy(elem.value)
      return (
        _list_iterator_ann(elem_ann),
        ast.Subscript(value=ast.Name(id="list"), slice=elem_ann),
      )
  hm = _meth_host_from_generator_name(gen_name, tr)
  if hm is not None:
    return _list_ann_from_method_generator(hm[0], hm[1], tr)
  return None


def _meth_host_from_generator_name(
  gen_name: str, tr: Translator,
) -> tuple[str, str] | None:
  if not gen_name.endswith(GENERATOR_SUFFIX):
    return None
  stem = gen_name[: -len(GENERATOR_SUFFIX)]
  best: tuple[str, str] | None = None
  best_len = -1
  for cls_name, info in tr.classes.items():
    if getattr(info, "is_mixin", False) or getattr(info, "is_protocol", False):
      continue
    if getattr(info, "is_annotation", False):
      continue
    prefix = cls_name + "_"
    if stem.startswith(prefix) and len(prefix) > best_len:
      best = (cls_name, stem[len(prefix):])
      best_len = len(prefix)
  return best


def _list_ann_from_method_generator(
  host: str, meth: str, tr: Translator,
) -> tuple[ast.expr, ast.expr] | None:
  host_info = tr.classes.get(host)
  if host_info is None:
    return None
  method = host_info.methods.get(meth)
  if method is None:
    return None
  gtypes = _parse_generator_ann(method.returns)
  if gtypes is None:
    return None
  elem = _host_substitute_ann(gtypes.yield_ann, host, tr)
  if elem is None:
    return None
  elem_ann = copy.deepcopy(elem)
  return (
    _list_iterator_ann(elem_ann),
    ast.Subscript(value=ast.Name(id="list"), slice=elem_ann),
  )


def _suspend_for_generator_materialize(
  it_ann: ast.expr,
  tr: Translator,
  *,
  current_gen: str | None,
  elem_ann: ast.expr | None,
) -> tuple[ast.expr, ast.expr] | None:
  """分态 ``for`` 的成员不能嵌套生成器，须 ``list`` + ``ListIterator``。"""
  if not isinstance(it_ann, ast.Name):
    return None
  name = it_ann.id
  if not name.endswith(GENERATOR_SUFFIX):
    return None
  pair = _list_ann_from_generator_name(name, tr)
  if pair is None and elem_ann is not None and name == current_gen:
    pair = (
      _list_iterator_ann(copy.deepcopy(elem_ann)),
      ast.Subscript(value=ast.Name(id="list"), slice=copy.deepcopy(elem_ann)),
    )
  return pair


def _for_iter_suspend_fields(
  body: list[ast.stmt],
  tr: Translator,
  *,
  host_class: str | None = None,
  current_gen: str | None = None,
  ann_body: list[ast.stmt] | None = None,
  elem_ann: ast.expr | None = None,
) -> list[tuple[str, ast.expr, ast.expr | None]]:
  """``for``/``async for`` 分态字段：``(it_field, it_ann, seq_ann|None)``。"""
  from ..emit.loops_emit import is_direct_range_call
  out: list[tuple[str, ast.expr, ast.expr | None]] = []
  for node in ast.walk(ast.Module(body=body, type_ignores=[])):
    if isinstance(node, ast.For):
      if not body_has_yield(node.body):
        continue
      if is_direct_range_call(node.iter):
        continue
    elif isinstance(node, ast.AsyncFor):
      if not async_for_needs_suspend(node):
        continue
    else:
      continue
    it_ann = _infer_iter_type(
      node.iter, tr, body,
      host_class=host_class, current_gen=current_gen, ann_body=ann_body,
    )
    seq_ann: ast.expr | None = None
    pair = _suspend_for_generator_materialize(
      it_ann, tr, current_gen=current_gen, elem_ann=elem_ann,
    )
    if pair is not None:
      it_ann, seq_ann = pair
    elif _for_iter_needs_seq_hoist(node.iter):
      seq_ann = _list_ann_from_iter_ann(it_ann)
    out.append((f"{_FOR_PREFIX}{len(out)}_it", it_ann, seq_ann))
  return out


def _is_suspend_assign_value(val: ast.expr | None) -> bool:
  return isinstance(val, (ast.Yield, ast.YieldFrom))


def _loads_hoisted_field(
  expr: ast.expr, hoisted_fields: set[str], *, via_self: bool = False,
) -> bool:
  if via_self:
    if (
      isinstance(expr, ast.Attribute)
      and isinstance(expr.value, ast.Name)
      and expr.value.id == "self"
      and expr.attr in hoisted_fields
    ):
      return True
  elif isinstance(expr, ast.Name) and _field_name(expr.id) in hoisted_fields:
    return True
  for child in ast.iter_child_nodes(expr):
    if _loads_hoisted_field(child, hoisted_fields, via_self=via_self):
      return True
  return False


def _is_hoisted_preamble_value(val: ast.expr) -> bool:
  """``pat = a + b`` / ``part = parts[idx]`` 等须在 ``__resume__`` 保留、非仅类型占位用的提升初值。"""
  return isinstance(
    val, (ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.Subscript, ast.Attribute)
  )


def _strip_hoisted_init_stmts(body: list[ast.stmt], hoisted: set[str]) -> list[ast.stmt]:
  """去掉仅用于默认构造的 ``self.g_x = 0``；保留 ``self.g_x = yield ...``。"""
  out: list[ast.stmt] = []
  hoisted_fields = {_field_name(n) for n in hoisted}
  for stmt in body:
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
      if stmt.target.id in hoisted and stmt.value is not None:
        if (
          isinstance(stmt.value, ast.Call)
          or _is_hoisted_preamble_value(stmt.value)
          or _loads_hoisted_field(stmt.value, hoisted_fields)
        ):
          out.append(stmt)
          continue
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Attribute):
      if isinstance(stmt.target.value, ast.Name) and stmt.target.value.id == "self":
        if stmt.target.attr in hoisted_fields:
          if _is_suspend_assign_value(stmt.value):
            out.append(stmt)
          elif stmt.value is not None and (
            isinstance(stmt.value, ast.Call)
            or _is_hoisted_preamble_value(stmt.value)
            or _loads_hoisted_field(stmt.value, hoisted_fields, via_self=True)
          ):
            out.append(stmt)
          continue
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
      t = stmt.targets[0]
      if isinstance(t, ast.Name) and _field_name(t.id) in hoisted_fields:
        keep = (
          isinstance(stmt.value, ast.Call)
          or _is_hoisted_preamble_value(stmt.value)
          or _loads_hoisted_field(stmt.value, hoisted_fields)
        )
        if keep:
          out.append(stmt)
          continue
      if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
        if t.attr in hoisted_fields:
          keep = (
            _is_suspend_assign_value(stmt.value)
            or isinstance(stmt.value, ast.Call)
            or _is_hoisted_preamble_value(stmt.value)
            or _loads_hoisted_field(stmt.value, hoisted_fields, via_self=True)
          )
          if keep:
            out.append(stmt)
            continue
    out.append(stmt)
  return out


def _default_send_expr(send_ann: ast.expr) -> ast.expr:
  if isinstance(send_ann, ast.Name) and send_ann.id == "PyNone":
    return ast.Call(func=ast.Name(id="PyNone"), args=[])
  if isinstance(send_ann, ast.Name) and send_ann.id == "int":
    return ast.Constant(value=0)
  return ast.Call(func=copy.deepcopy(send_ann), args=[], keywords=[])


def _make_send_method(send_ann: ast.expr, result_ann: ast.expr) -> ast.FunctionDef:
  return ast.FunctionDef(
    name="send",
    args=ast.arguments(
      posonlyargs=[],
      args=[
        ast.arg(arg="self"),
        ast.arg(arg="value", annotation=copy.deepcopy(send_ann)),
      ],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    ),
    body=[
      ast.Assign(
        targets=[ast.Attribute(ast.Name(id="self"), _SEND_FIELD, ast.Store())],
        value=ast.Name(id="value"),
      ),
      ast.Assign(
        targets=[ast.Attribute(ast.Name(id="self"), _SEND_FLAG, ast.Store())],
        value=ast.Constant(value=True),
      ),
      ast.Return(
        value=ast.Call(
          func=ast.Attribute(ast.Name(id="self"), "__resume", ast.Load()),
          args=[],
        ),
      ),
    ],
    decorator_list=[],
    returns=copy.deepcopy(result_ann),
  )


def _is_async_generator_yield(yield_ann: ast.expr) -> bool:
  return not (
    isinstance(yield_ann, ast.Name)
    and yield_ann.id in ("PyNone", "None", "LoopHandle")
  )


def _make_aiter_method() -> ast.FunctionDef:
  return ast.FunctionDef(
    name="__aiter__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    ),
    body=[ast.Return(value=ast.Name(id="self"))],
    decorator_list=[],
    returns=ast.Name(id="Self"),
  )


def _make_anext_method(result_ann: ast.expr) -> ast.FunctionDef:
  return ast.FunctionDef(
    name="__anext__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    ),
    body=[
      ast.Return(
        value=ast.Call(
          func=ast.Name(id="next", ctx=ast.Load()),
          args=[ast.Name(id="self", ctx=ast.Load())],
          keywords=[],
        ),
      ),
    ],
    decorator_list=[],
    returns=copy.deepcopy(result_ann),
  )


def _make_await_method() -> ast.FunctionDef:
  return ast.FunctionDef(
    name="__await__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    ),
    body=[ast.Return(value=ast.Name(id="self"))],
    decorator_list=[],
    returns=ast.Name(id="Self"),
  )


def _make_next_method(send_ann: ast.expr, result_ann: ast.expr) -> ast.FunctionDef:
  return ast.FunctionDef(
    name="__next__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
    ),
    body=[
      ast.Return(
        value=ast.Call(
          func=ast.Attribute(ast.Name(id="self"), "send", ast.Load()),
          args=[_default_send_expr(send_ann)],
        ),
      ),
    ],
    decorator_list=[],
    returns=copy.deepcopy(result_ann),
  )


def _make_generator_class(
  gen_name: str,
  func: ast.FunctionDef,
  body: list[ast.stmt],
  *,
  ann_body: list[ast.stmt],
  hoisted: list[str],
  gtypes: GeneratorTypes,
  tr: Translator,
  is_coroutine: bool = False,
) -> ast.ClassDef:
  host_class = _host_class_from_gen_name(gen_name, func.name)
  params = [a for a in func.args.args if a.arg != "self"]
  ref_params = {a.arg for a in params if _param_should_store_ref(a)}
  yield_ann = _host_substitute_ann(gtypes.yield_ann, host_class, tr)
  yf_fields = _yield_from_fields(
    body, tr, host_class=host_class, current_gen=gen_name, ann_body=ann_body,
    params=params,
  )
  for_fields = _for_iter_suspend_fields(
    body, tr, host_class=host_class, current_gen=gen_name, ann_body=ann_body,
    elem_ann=yield_ann,
  )
  send_ann = _host_substitute_ann(gtypes.send_ann, host_class, tr)
  return_ann = _host_substitute_ann(gtypes.return_ann, host_class, tr)
  result_ann = _iter_result_ann(yield_ann, return_ann)
  host_field = _field_name("self") if any(a.arg == "self" for a in func.args.args) else None

  class_body: list[ast.stmt] = []
  class_body.append(
    ast.TypeAlias(
      name=ast.Name(id="Element", ctx=ast.Load()),
      type_params=[],
      value=copy.deepcopy(yield_ann),
    )
  )
  class_body.append(
    ast.TypeAlias(
      name=ast.Name(id="SendType", ctx=ast.Load()),
      type_params=[],
      value=copy.deepcopy(send_ann),
    )
  )
  class_body.append(
    ast.TypeAlias(
      name=ast.Name(id="ReturnType", ctx=ast.Load()),
      type_params=[],
      value=copy.deepcopy(return_ann),
    )
  )
  for name in hoisted:
    fname = _field_name(name)
    ann = _host_substitute_ann(
      _infer_hoisted_field_ann(
        name,
        ann_body,
        tr,
        host_class=host_class,
        current_gen=gen_name,
        ann_body=ann_body,
        params=params,
      ),
      host_class,
      tr,
    )
    class_body.append(
      ast.AnnAssign(
        target=ast.Attribute(ast.Name(id="self"), fname, ast.Store()),
        annotation=copy.deepcopy(ann),
        value=None,
        simple=1,
      )
    )
  for fname, ann in yf_fields:
    class_body.append(
      ast.AnnAssign(
        target=ast.Attribute(ast.Name(id="self"), fname, ast.Store()),
        annotation=_host_substitute_ann(ann, host_class, tr),
        value=None,
        simple=1,
      )
    )
  for fname, ann, seq_ann in for_fields:
    class_body.append(
      ast.AnnAssign(
        target=ast.Attribute(ast.Name(id="self"), fname, ast.Store()),
        annotation=_host_substitute_ann(ann, host_class, tr),
        value=None,
        simple=1,
      )
    )
    if seq_ann is not None:
      seq_field = fname[: -len("_it")] + "_seq"
      class_body.append(
        ast.AnnAssign(
          target=ast.Attribute(ast.Name(id="self"), seq_field, ast.Store()),
          annotation=_host_substitute_ann(seq_ann, host_class, tr),
          value=None,
          simple=1,
        )
      )
  if host_field and host_class:
    class_body.append(
      ast.AnnAssign(
        target=ast.Attribute(ast.Name(id="self"), host_field, ast.Store()),
        annotation=ast.Name(id=host_class, ctx=ast.Load()),
        value=None,
        simple=1,
      )
    )
  class_body.append(
    _make_init(
      params,
      hoisted,
      yf_fields,
      for_fields,
      send_ann,
      resume_body=body,
      ann_body=ann_body,
      host_class=host_class,
      current_gen=gen_name,
      host_field=host_field,
      ref_params=ref_params,
      tr=tr,
    ),
  )
  class_body.append(
    ast.FunctionDef(
      name="__iter__",
      args=ast.arguments(
        posonlyargs=[],
        args=[ast.arg(arg="self")],
        kwonlyargs=[],
        kw_defaults=[],
        defaults=[],
      ),
      body=[ast.Return(value=ast.Name(id="self"))],
      decorator_list=[],
      returns=ast.Name(id="Self"),
    )
  )
  class_body.append(
    ast.FunctionDef(
      name="__resume",
      args=ast.arguments(
        posonlyargs=[],
        args=[ast.arg(arg="self")],
        kwonlyargs=[],
        kw_defaults=[],
        defaults=[],
      ),
      body=body,
      decorator_list=[],
      returns=copy.deepcopy(result_ann),
    )
  )
  class_body.append(_make_next_method(send_ann, result_ann))
  class_body.append(_make_send_method(send_ann, result_ann))
  if is_coroutine:
    class_body.append(_make_await_method())
    if _is_async_generator_yield(yield_ann):
      class_body.append(_make_aiter_method())
      class_body.append(_make_anext_method(result_ann))
  return ast.ClassDef(
    name=gen_name,
    bases=[],
    keywords=[],
    body=class_body,
    decorator_list=[],
  )


def _field_name(name: str) -> str:
  return f"g_{name}"


def _is_slice_array_ann(ann: ast.expr | None) -> bool:
  ann = strip_type_annotation_markers(ann)
  return (
    isinstance(ann, ast.Subscript)
    and isinstance(ann.slice, ast.Slice)
  )


def _param_should_store_ref(arg: ast.arg) -> bool:
  """状态机参数字段：显式 ``@ref`` 与 ``T[:]`` 参数保存指向调用方对象的指针。

  普通函数形参里的 ``@ref`` 会生成 C++ ``T&``；展开成 coroutine/generator
  状态机后，若继续把它作为值字段保存就会复制对象并丢失引用语义。
  ``T[:]`` 在调用侧同样按引用传入（native recv 写入 caller buffer），
  因此也必须保存为指针字段。
  """
  ann = arg.annotation
  return (
    "ref" in iter_matmult_marker_names(ann)
    or _is_slice_array_ann(ann)
  )


def _ref_param_field_ann(ann: ast.expr | None) -> ast.expr | None:
  base = strip_type_annotation_markers(ann)
  if base is None:
    return None
  return ast.Subscript(
    value=ast.Name(id="Pointer", ctx=ast.Load()),
    slice=copy.deepcopy(base),
    ctx=ast.Load(),
  )


def _param_ref_expr(field: str, ctx: ast.expr_context) -> ast.Subscript:
  return ast.Subscript(
    value=ast.Attribute(ast.Name(id="self", ctx=ast.Load()), field, ast.Load()),
    slice=ast.Constant(value=0),
    ctx=ctx,
  )


def _assign_self_field(field: str, value: ast.expr) -> ast.Assign:
  """``__resume`` 内写字段：类型已在生成器类体声明，勿 ``self.f: T = …``。"""
  return ast.Assign(
    targets=[ast.Attribute(ast.Name(id="self"), field, ast.Store())],
    value=value,
  )


def _rewrite_params(
  body: list[ast.stmt],
  params: set[str],
  *,
  host_field: str | None = None,
  ref_params: set[str] | None = None,
) -> list[ast.stmt]:
  ref_params = ref_params or set()

  class R(ast.NodeTransformer):
    def _field_for_param(self, name: str) -> str:
      if name == "self" and host_field:
        return host_field
      return name

    def _target_for_param(self, name: str, ctx: ast.expr_context) -> ast.expr:
      field = self._field_for_param(name)
      if name in ref_params:
        return _param_ref_expr(field, ctx)
      return ast.Attribute(ast.Name(id="self", ctx=ast.Load()), field, ctx)

    def visit_Name(self, node: ast.Name) -> ast.expr:
      if node.id in params and isinstance(node.ctx, ast.Load):
        return self._target_for_param(node.id, ast.Load())
      return node

    def visit_Assign(self, node: ast.Assign) -> ast.stmt:
      node = copy.deepcopy(node)
      if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        t = node.targets[0]
        if t.id in params:
          return ast.Assign(
            targets=[self._target_for_param(t.id, ast.Store())],
            value=self.visit(node.value),
          )
      return self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> ast.stmt:
      node = copy.deepcopy(node)
      if isinstance(node.target, ast.Name) and node.target.id in params:
        return ast.AugAssign(
          target=self._target_for_param(node.target.id, ast.Store()),
          op=node.op,
          value=self.visit(node.value),
        )
      return self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.stmt:
      node = copy.deepcopy(node)
      if isinstance(node.target, ast.Name) and node.target.id in params:
        if node.value is None:
          return ast.Pass()
        if node.target.id in ref_params:
          return ast.Assign(
            targets=[self._target_for_param(node.target.id, ast.Store())],
            value=self.visit(node.value),
          )
        return _assign_self_field(self._field_for_param(node.target.id), self.visit(node.value))
      return self.generic_visit(node)

  return [R().visit(s) for s in body]


def _rewrite_hoisted(body: list[ast.stmt], hoisted: set[str]) -> list[ast.stmt]:
  class R(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.expr:
      if node.id in hoisted and isinstance(node.ctx, ast.Load):
        return ast.Attribute(
          ast.Name(id="self"), _field_name(node.id), ast.Load()
        )
      return node

    def visit_Assign(self, node: ast.Assign) -> ast.stmt:
      node = copy.deepcopy(node)
      if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        t = node.targets[0]
        if t.id in hoisted:
          return ast.Assign(
            targets=[
              ast.Attribute(
                ast.Name(id="self"), _field_name(t.id), ast.Store()
              )
            ],
            value=self.visit(node.value),
          )
      return self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> ast.stmt:
      node = copy.deepcopy(node)
      if isinstance(node.target, ast.Name) and node.target.id in hoisted:
        return ast.AugAssign(
          target=ast.Attribute(
            ast.Name(id="self"), _field_name(node.target.id), ast.Store()
          ),
          op=node.op,
          value=self.visit(node.value),
        )
      return self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.stmt:
      node = copy.deepcopy(node)
      if isinstance(node.target, ast.Name) and node.target.id in hoisted:
        if node.value is None:
          return ast.Pass()
        return _assign_self_field(
          _field_name(node.target.id),
          self.visit(node.value),
        )
      return self.generic_visit(node)

  return [R().visit(s) for s in body]


def _coroutine_return_ann(func: ast.FunctionDef) -> ast.expr:
  if func.returns is not None:
    parsed = _parse_generator_ann(func.returns)
    if parsed is not None:
      if (
        isinstance(func.returns, ast.Subscript)
        and isinstance(func.returns.value, ast.Name)
        and func.returns.value.id == "AsyncGeneratorType"
      ):
        return ast.Subscript(
          value=ast.Name(id="CoroutineType"),
          slice=ast.Tuple(
            elts=[
              copy.deepcopy(parsed.yield_ann),
              copy.deepcopy(parsed.send_ann),
              copy.deepcopy(parsed.return_ann),
            ],
          ),
        )
      return func.returns
  none = ast.Name(id="PyNone")
  if func.returns is not None:
    ret_ty = copy.deepcopy(func.returns)
    return ast.Subscript(
      value=ast.Name(id="CoroutineType"),
      slice=ast.Tuple(elts=[none, none, ret_ty]),
    )
  r = _infer_return_ann(func.body)
  y = _infer_yield_ann(func.body)
  return ast.Subscript(
    value=ast.Name(id="CoroutineType"),
    slice=ast.Tuple(elts=[copy.deepcopy(y), none, copy.deepcopy(r)]),
  )


def _unwrap_task_scheduling_expr(expr: ast.expr) -> ast.expr:
  """``await Task.sleep(...)`` 或 ``yield from Task.sleep(...).__await__()`` → 内层 ``Call``。"""
  if isinstance(expr, ast.Await):
    return _unwrap_task_scheduling_expr(expr.value)
  if (
    isinstance(expr, ast.Call)
    and isinstance(expr.func, ast.Attribute)
    and expr.func.attr == "__await__"
    and not expr.args
  ):
    return _unwrap_task_scheduling_expr(expr.func.value)
  return expr


def _is_task_scheduling_call(expr: ast.expr) -> bool:
  inner = _unwrap_task_scheduling_expr(expr)
  if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Attribute):
    return False
  recv = inner.func.value
  if isinstance(recv, ast.Name) and recv.id == "Task":
    return inner.func.attr in ("sleep", "gather", "create", "runThread", "waitRead", "waitWrite")
  return False


def _body_uses_task_scheduling(body: list[ast.stmt]) -> bool:
  """``await Task.sleep/gather/create(...)``（含 ``async def`` 脱糖后的 ``yield from``）。"""
  for node in ast.walk(ast.Module(body=body, type_ignores=[])):
    if isinstance(node, ast.Await) and _is_task_scheduling_call(node):
      return True
    if isinstance(node, ast.YieldFrom) and _is_task_scheduling_call(node.value):
      return True
  return False


def coroutine_types_for(func: ast.FunctionDef, body: list[ast.stmt]) -> GeneratorTypes:
  parsed = _parse_generator_ann(_coroutine_return_ann(func))
  if parsed is not None:
    if (
      _body_uses_task_scheduling(body)
      or (
        isinstance(parsed.yield_ann, ast.Name)
        and parsed.yield_ann.id in ("PyNone", "None")
      )
    ):
      loop = ast.Name(id="LoopHandle")
      return GeneratorTypes(
        loop,
        copy.deepcopy(parsed.send_ann),
        copy.deepcopy(parsed.return_ann),
      )
    return parsed
  return generator_types_for(func, body)


def _yield_from_targets_generator(ann: ast.expr) -> bool:
  if isinstance(ann, ast.Name):
    return ann.id.endswith(GENERATOR_SUFFIX) or ann.id.endswith(COROUTINE_SUFFIX)
  return False


def _desugar_generator_yield_from_to_for(
  body: list[ast.stmt],
  tr: Translator,
  *,
  host_class: str | None,
  current_gen: str,
  ann_body: list[ast.stmt],
) -> list[ast.stmt]:
  """Expand 阶段：``yield from`` 子 ``*_generator`` → ``for``+``yield``（避免嵌套/自引用成员）。"""

  def _needs_desugar(yf_value: ast.expr) -> bool:
    it_ann = _infer_iter_type(
      yf_value,
      tr,
      body,
      host_class=host_class,
      current_gen=current_gen,
      ann_body=ann_body,
    )
    return _yield_from_targets_generator(it_ann)

  dg_idx = 0

  def _for_from_yield_from(yf: ast.YieldFrom) -> ast.For:
    nonlocal dg_idx
    var = f"_dg_yf_{dg_idx}"
    dg_idx += 1
    return ast.For(
      target=ast.Name(id=var, ctx=ast.Store()),
      iter=yf.value,
      body=[ast.Expr(value=ast.Yield(value=ast.Name(id=var, ctx=ast.Load())))],
      orelse=[],
    )

  class T(ast.NodeTransformer):
    def visit_Expr(self, node: ast.Expr) -> ast.AST:
      if isinstance(node.value, ast.YieldFrom) and _needs_desugar(node.value.value):
        repl = _for_from_yield_from(node.value)
        ast.copy_location(repl, node)
        return repl
      return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
      return self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
      return self.generic_visit(node)

  out = T().visit(ast.Module(body=body, type_ignores=[]))
  assert isinstance(out, ast.Module)
  return out.body


def _transform_function(
  func: ast.FunctionDef,
  gen_name: str,
  tr: Translator,
  *,
  is_coroutine: bool = False,
) -> tuple[ast.FunctionDef, ast.ClassDef]:
  body = _strip_leading_docstring(copy.deepcopy(func.body))
  ann_body = copy.deepcopy(func.body)
  gtypes = (
    coroutine_types_for(func, body) if is_coroutine else generator_types_for(func, body)
  )
  param_names = {a.arg for a in func.args.args}
  ref_param_names = {
    a.arg for a in func.args.args
    if a.arg != "self" and _param_should_store_ref(a)
  }
  hoisted = set(_collect_hoisted_names(body, param_names))
  host_class = _host_class_from_gen_name(gen_name, func.name)
  host_field = _field_name("self") if any(a.arg == "self" for a in func.args.args) else None
  body = _rewrite_params(body, param_names, host_field=host_field, ref_params=ref_param_names)
  body = _rewrite_hoisted(body, hoisted)
  body = _strip_hoisted_init_stmts(body, hoisted)
  body = _desugar_generator_yield_from_to_for(
    body,
    tr,
    host_class=host_class,
    current_gen=gen_name,
    ann_body=ann_body,
  )
  gen_cls = _make_generator_class(
    gen_name,
    func,
    body,
    ann_body=ann_body,
    hoisted=list(hoisted),
    gtypes=gtypes,
    tr=tr,
    is_coroutine=is_coroutine,
  )
  call_args = [ast.Name(id=a.arg) for a in func.args.args]
  if _parse_generator_ann(func.returns):
    ret_ann = func.returns
  else:
    ret_ann = ast.Name(id=gen_name)
  wrapper = ast.FunctionDef(
    name=func.name,
    args=func.args,
    body=_body_with_leading_docstring(
      func,
      [
        ast.Return(
          value=ast.Call(func=ast.Name(id=gen_name), args=call_args),
        ),
      ],
    ),
    decorator_list=func.decorator_list,
    returns=ret_ann,
    type_params=getattr(func, "type_params", None) or [],
  )
  ast.copy_location(wrapper, func)
  return wrapper, gen_cls


def _expand_yielding_function(
  tr: Translator,
  func: ast.FunctionDef,
  gen_name: str,
  *,
  is_coroutine: bool,
) -> tuple[ast.FunctionDef, ast.ClassDef]:
  wrapper, gen_cls = _transform_function(
    func, gen_name, tr, is_coroutine=is_coroutine,
  )
  return wrapper, gen_cls


def _sync_module_functions(tr: Translator) -> None:
  """``expand_generators`` 后同步顶层 ``def``（含原 ``async def`` 的包装函数）。"""
  from ..analysis.module_functions import partition_module_functions_from_asts

  partition_module_functions_from_asts(
    tr,
    runtime_pkg=RUNTIME_PKG,
    builtins_runtime_funcs=BUILTINS_CPP_RUNTIME_FUNCS,
    translation_only_funcs=_MODULE_FUNC_SKIP,
  )


def _is_decorator_or_context_factory(func: ast.FunctionDef) -> bool:
  """``@decorator`` / ``@context`` 工厂体内的 ``yield`` 由 ``expand_decorators`` 处理，勿生成器化。"""
  return is_decorator_definition(func) or is_context_definition(func)


def _append_gen_class_to_module(
  tr: Translator, module_path: str, gen_cls: ast.ClassDef,
) -> None:
  tree = tr.module_asts.get(module_path)
  if tree is None:
    return
  if any(isinstance(node, ast.ClassDef) and node.name == gen_cls.name for node in tree.body):
    return
  tree.body.append(gen_cls)
  ast.fix_missing_locations(tree)


_GENERATOR_PROTOCOL_METHODS = frozenset({
  "__resume", "__next__", "send", "__iter__", "__aiter__", "__anext__",
})


def _expand_classinfo_generators(tr: Translator) -> None:
  """混入等方法仅存在于 ``ClassInfo``、不在模块 AST 类体时，补做 generator 展开。"""
  for info in list(tr.classes.values()):
    if info.is_mixin or info.is_annotation or info.is_protocol:
      continue
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(info.module_path):
      continue
    if info.name.endswith(GENERATOR_SUFFIX) or info.name.endswith(COROUTINE_SUFFIX):
      continue
    for name in list(info.methods.keys()):
      if name in _GENERATOR_PROTOCOL_METHODS:
        continue
      method = info.methods[name]
      if not body_needs_resume_machine(method.body):
        continue
      if _is_decorator_or_context_factory(method):
        continue
      gen_name = f"{info.name}_{name}{GENERATOR_SUFFIX}"
      wrapper, gen_cls = _expand_yielding_function(
        tr, method, gen_name, is_coroutine=False,
      )
      if gen_name not in tr.classes:
        tr.classes[gen_name] = ClassInfo(gen_cls, info.module_path)
        _register_generator_host_friend(info, gen_cls)
        _append_gen_class_to_module(tr, info.module_path, gen_cls)
      info.methods[name] = wrapper
    for name, overloads in list(info.method_overloads.items()):
      new_overloads: list[ast.FunctionDef] = []
      gen_name = f"{info.name}_{name}{GENERATOR_SUFFIX}"
      for method in overloads:
        if name in _GENERATOR_PROTOCOL_METHODS:
          new_overloads.append(method)
          continue
        if not body_needs_resume_machine(method.body):
          new_overloads.append(method)
          continue
        if _is_decorator_or_context_factory(method):
          new_overloads.append(method)
          continue
        wrapper, gen_cls = _expand_yielding_function(
          tr, method, gen_name, is_coroutine=False,
        )
        tr.classes[gen_name] = ClassInfo(gen_cls, info.module_path)
        _register_generator_host_friend(info, gen_cls)
        _append_gen_class_to_module(tr, info.module_path, gen_cls)
        new_overloads.append(wrapper)
      if new_overloads:
        info.method_overloads[name] = new_overloads


def _register_generator_host_friend(
  host: ClassInfo | None, gen_cls: ast.ClassDef,
) -> None:
  """``Host_method_generator`` 须访问宿主 ``_…`` 成员（同 ``ListIterator`` 友元）。"""
  if host is None:
    return
  if gen_cls.name not in host.friend_classes:
    host.friend_classes.append(gen_cls.name)


def _auto_register_member_generator_friends(tr: Translator) -> None:
  """类成员 ``async def`` / generator 的状态机类自动成为宿主类友元。

  生成的 ``Host_method_coroutine`` / ``Host_method_generator`` 是宿主方法的
  C++ 实现细节，会读取 ``self._…`` 持久化字段；标准库/用户代码不应手写这类
  内部状态机类名到 ``friends=(...)``。
  """
  suffixes = (COROUTINE_SUFFIX, GENERATOR_SUFFIX)
  hosts = [
    info
    for info in tr.classes.values()
    if not (info.name.endswith(COROUTINE_SUFFIX) or info.name.endswith(GENERATOR_SUFFIX))
  ]
  for gen in tr.classes.values():
    if not gen.name.endswith(suffixes):
      continue
    best: ClassInfo | None = None
    best_len = -1
    for host in hosts:
      if host.module_path != gen.module_path:
        continue
      prefix = f"{host.name}_"
      if not gen.name.startswith(prefix):
        continue
      rest = gen.name[len(prefix):]
      meth = ""
      if rest.endswith(COROUTINE_SUFFIX):
        meth = rest[: -len(COROUTINE_SUFFIX)]
      elif rest.endswith(GENERATOR_SUFFIX):
        meth = rest[: -len(GENERATOR_SUFFIX)]
      if not meth:
        continue
      if meth not in host.methods and meth not in host.method_overloads:
        continue
      if len(host.name) > best_len:
        best = host
        best_len = len(host.name)
    if best is not None:
      _register_generator_host_friend(best, gen.node)


def expand_generators(tr: Translator) -> None:
  """``yield`` / ``yield from`` / ``async def`` → ``*_generator`` / ``*_coroutine``（在 ``@context`` 之前）。"""
  skip = getattr(tr, "skip_cached_analysis_module", None)
  for module_path, tree in list(tr.module_asts.items()):
    if skip is not None and skip(module_path):
      continue
    new_body: list[ast.stmt] = []
    inserts: list[ast.ClassDef] = []
    for stmt in tree.body:
      if isinstance(stmt, ast.AsyncFunctionDef):
        func = async_def_to_function(stmt)
        suffix = COROUTINE_SUFFIX
        gen_name = f"{func.name}{suffix}"
        wrapper, gen_cls = _expand_yielding_function(
          tr, func, gen_name, is_coroutine=True,
        )
        new_body.append(wrapper)
        inserts.append(gen_cls)
        tr.classes[gen_cls.name] = ClassInfo(gen_cls, module_path)
        continue
      if isinstance(stmt, ast.FunctionDef) and body_needs_resume_machine(
        stmt.body,
      ):
        if _is_decorator_or_context_factory(stmt):
          new_body.append(stmt)
          continue
        gen_name = f"{stmt.name}{GENERATOR_SUFFIX}"
        wrapper, gen_cls = _expand_yielding_function(
          tr, stmt, gen_name, is_coroutine=False,
        )
        new_body.append(wrapper)
        inserts.append(gen_cls)
        tr.classes[gen_cls.name] = ClassInfo(gen_cls, module_path)
        continue
      if isinstance(stmt, ast.ClassDef):
        new_cls_body: list[ast.stmt] = []
        cls_inserts: list[ast.ClassDef] = []
        host = tr.classes.get(stmt.name)
        skip_gen = host is not None and host.is_mixin
        for inner in stmt.body:
          if isinstance(inner, ast.AsyncFunctionDef):
            if skip_gen:
              new_cls_body.append(inner)
              continue
            func = async_def_to_function(inner)
            gen_name = f"{stmt.name}_{func.name}{COROUTINE_SUFFIX}"
            wrapper, gen_cls = _expand_yielding_function(
              tr, func, gen_name, is_coroutine=True,
            )
            new_cls_body.append(wrapper)
            cls_inserts.append(gen_cls)
            tr.classes[gen_cls.name] = ClassInfo(gen_cls, module_path)
            _register_generator_host_friend(host, gen_cls)
            if host is not None:
              host.methods[inner.name] = wrapper
          elif isinstance(inner, ast.FunctionDef) and body_needs_resume_machine(
            inner.body,
          ):
            if skip_gen:
              new_cls_body.append(inner)
              continue
            gen_name = f"{stmt.name}_{inner.name}{GENERATOR_SUFFIX}"
            wrapper, gen_cls = _expand_yielding_function(
              tr, inner, gen_name, is_coroutine=False,
            )
            new_cls_body.append(wrapper)
            cls_inserts.append(gen_cls)
            tr.classes[gen_cls.name] = ClassInfo(gen_cls, module_path)
            _register_generator_host_friend(host, gen_cls)
            if host is not None:
              host.methods[inner.name] = wrapper
          else:
            new_cls_body.append(inner)
        stmt.body = new_cls_body
        new_body.append(stmt)
        inserts.extend(cls_inserts)
        continue
      new_body.append(stmt)
    tree.body = new_body + inserts
    ast.fix_missing_locations(tree)

  _expand_classinfo_generators(tr)

  _auto_register_member_generator_friends(tr)

  _sync_module_functions(tr)

  tr.generator_methods = {
    (info.module_path, info.name, m.name)
    for info in tr.classes.values()
    for m in info.methods.values()
    if m.name == "__resume"
    and (
      body_needs_resume_machine(m.body)
      or info.name.endswith(COROUTINE_SUFFIX)
    )
  }
