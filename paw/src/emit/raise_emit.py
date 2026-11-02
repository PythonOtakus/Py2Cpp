"""``raise`` / ``raise … from`` → C++ ``throw``。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import cpp_param
from ..analysis.type_emit import scope_has_type_binding, scope_storage_cpp
from ..analysis.patterns import temp_name
from ..constant.stdlib_layout import cpp_exception_type, EXCEPTIONS_NS

if TYPE_CHECKING:
  from ..translator import Translator

_GROUP_TY = cpp_exception_type('ExceptionGroup')
_STAR_GROUP_TYPES = frozenset({"ExceptionGroup", "BaseExceptionGroup"})


def _raise_bound_exc_ref(tr: Translator, name: str) -> str | None:
  """``raise e``：已绑定异常实例 → ``throw e``，勿 ``Exc()``。"""
  if not tr._is_local_declared(name):
    return None
  return cpp_param(name)


def _raise_exc_expr(tr: Translator, exc: ast.expr) -> str:
  """``raise Exc(...)`` / ``raise Exc`` → 可 throw 的 C++ 表达式。"""
  match exc:
    case ast.Call():
      return tr._visit_value_expr(exc)
    case ast.Name(id=name):
      bound = _raise_bound_exc_ref(tr, name)
      if bound is not None:
        return bound
      return tr._cpp_exception_ctor(name)
    case _:
      raise NotImplementedError(f"raise: {ast.dump(exc)}")


def _is_raise_from_none(cause: ast.expr | None) -> bool:
  return isinstance(cause, ast.Constant) and cause.value is None


def _cause_ptr_expr(tr: Translator, cause: ast.expr) -> str:
  match cause:
    case ast.Name(id=name):
      return f"&{cpp_param(name)}"
    case _:
      raise NotImplementedError(f"raise … from 须为异常绑定名或 None，得到 {ast.dump(cause)}")


def _is_exception_group_expr(tr: Translator, exc: ast.expr) -> bool:
  match exc:
    case ast.Call(func=ast.Name(id=exc_name)):
      return exc_name in _STAR_GROUP_TYPES
    case ast.Name(id=var_name):
      if tr.scope and scope_has_type_binding(tr.scope, var_name):
        vt = scope_storage_cpp(tr, var_name)
        return _GROUP_TY in vt or "BaseExceptionGroup" in vt
      return False
    case _:
      return False


def _raise_uses_temp_for_wrap(exc: ast.expr) -> bool:
  """非无参默认构造时 ``exception_group_from_single`` 须先绑定左值。"""
  return isinstance(exc, ast.Call) and len(exc.args) > 0


def _emit_try_star_wrap_throw(
  tr: Translator, exc_expr: str, exc_node: ast.expr,
) -> None:
  if _raise_uses_temp_for_wrap(exc_node):
    tmp = temp_name("exc_wrap")
    tr.write_line(f"auto {tmp} = {exc_expr};")
    tr.write_line(
      f"throw {EXCEPTIONS_NS}::exception_group_from_single({tmp});",
    )
    return
  tr.write_line(
    f"throw {EXCEPTIONS_NS}::exception_group_from_single({exc_expr});",
  )


def _emit_throw_with_optional_cause(
  tr: Translator,
  exc_expr: str,
  exc_node: ast.expr,
  *,
  cause: ast.expr | None,
  in_star: bool,
  is_group: bool,
) -> None:
  if cause is not None and not _is_raise_from_none(cause):
    tmp = temp_name("raised")
    cause_ptr = _cause_ptr_expr(tr, cause)
    tr.write_line(f"auto {tmp} = {exc_expr};")
    tr.write_line(f"{tmp}.__cause__ = {cause_ptr};")
    if in_star and not is_group:
      tr.write_line(
        f"throw {EXCEPTIONS_NS}::exception_group_from_single({tmp});",
      )
    else:
      tr.write_line(f"throw {tmp};")
    return
  if in_star and not is_group:
    _emit_try_star_wrap_throw(tr, exc_expr, exc_node)
  else:
    tr.write_line(f"throw {exc_expr};")


def _emit_exception_group_raise(tr: Translator, node: ast.Call) -> None:
  if len(node.args) != 2:
    raise NotImplementedError(
      f"ExceptionGroup 须为 ``ExceptionGroup(message, exceptions)``，得到 {ast.dump(node)}",
    )
  seq = node.args[1]
  if not isinstance(seq, ast.List):
    raise NotImplementedError(
      f"ExceptionGroup 第二参数须为 ``list`` 字面量，得到 {ast.dump(seq)}",
    )
  tmp = temp_name("eg")
  tr.write_line(f"{_GROUP_TY} {tmp};")
  tr.write_line(f"{tmp}.clear();")
  for elt in seq.elts:
    match elt:
      case ast.Call(func=ast.Name(id=exc_name)):
        tr.write_line(f"{tmp}.append({tr._cpp_exception_ctor(exc_name)});")
      case _:
        raise NotImplementedError(
          f"ExceptionGroup 元素须为 ``SomeError()``，得到 {ast.dump(elt)}",
        )
  tr.write_line(f"throw {tmp};")


def emit_raise(tr: Translator, node: ast.Raise) -> None:
  if node.exc is None:
    raise NotImplementedError("bare raise 暂不支持")
  if tr._in_noexcept_function() and not tr._try_stack:
    if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
      if node.exc.func.id == "ExceptionGroup":
        raise NotImplementedError("@noexcept 内不支持 raise ExceptionGroup")
    exc_expr = _raise_exc_expr(tr, node.exc)
    tr.write_line(f"return {tr._fault_err_return_expr(exc_expr)};")
    return
  if tr._in_next_method() and tr._is_stop_iteration_exc(node.exc):
    tr.write_line(f"return {tr._iter_result_return_expr()};")
    return

  if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
    if node.exc.func.id == "ExceptionGroup":
      _emit_exception_group_raise(tr, node.exc)
      return

  exc_expr = _raise_exc_expr(tr, node.exc)
  in_star = tr._in_try_star()
  is_group = _is_exception_group_expr(tr, node.exc)
  _emit_throw_with_optional_cause(
    tr, exc_expr, node.exc,
    cause=node.cause, in_star=in_star, is_group=is_group,
  )
