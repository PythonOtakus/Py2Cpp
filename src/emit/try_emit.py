"""``try`` / ``except`` / ``else`` / ``finally`` → C++ ``try`` / ``catch``。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..constant.stdlib_layout import cpp_exception_type, EXCEPTIONS_NS
from ..analysis.ir import cpp_ident, cpp_param
from ..analysis.module_namespace import qualify_symbol_in_module
from ..analysis.patterns import temp_name
from ..translation_error import TranslationError, location_from_node
from ..analysis.type_emit import bind_scope_var

if TYPE_CHECKING:
  from ..translator import Translator, _TryFrame

_GROUP_TY = cpp_exception_type('ExceptionGroup')
_KIND_TY = f"{EXCEPTIONS_NS}::ExcTypeUnion::Enum"
_FORBIDDEN_STAR_TYPES = frozenset({"BaseExceptionGroup", "ExceptionGroup"})


def _exc_cpp_type(exc_name: str) -> str:
  return cpp_exception_type(exc_name)


def _pybool_cast(expr: str) -> str:
  """与 ``_truthiness_condition_from_cpp`` 一致：经 ``operator PyBool`` 求值。"""
  pb = cpp_ident("bool")
  return f"static_cast<{pb}>({expr})"


def _parse_handler_types(handler: ast.ExceptHandler) -> list[str | None]:
  """返回异常名列表；``[None]`` 表示 bare ``except:``。"""
  if handler.type is None:
    return [None]
  if isinstance(handler.type, ast.Name):
    return [handler.type.id]
  if isinstance(handler.type, ast.Tuple):
    out: list[str | None] = []
    for elt in handler.type.elts:
      if isinstance(elt, ast.Name):
        out.append(elt.id)
      else:
        raise NotImplementedError(
          f"except 元组元素须为异常类名，得到 {ast.dump(elt)}",
        )
    return out or [None]
  raise NotImplementedError(
    f"except 类型须为异常类名或 ``(A, B)``，得到 {ast.dump(handler.type)}",
  )


def _class_info_for_exception_name(tr: Translator, name: str):
  binding = tr._effective_import_bindings().get(name)
  if binding is not None and binding.kind == "class":
    tr._ensure_class_indexes()
    assert tr._classes_by_module is not None
    for info in tr._classes_by_module.get(binding.module_path, ()):
      if info.name == binding.symbol:
        return info
  mp = tr._active_module_path()
  tr._ensure_class_indexes()
  assert tr._classes_by_module is not None
  for info in tr._classes_by_module.get(mp, ()):
    if info.name == name:
      return info
  return None


def _is_exception_class(tr: Translator, info) -> bool:
  if info.name == "Exception":
    return True
  from ..passes.mro_closure import is_subclass_of

  return is_subclass_of(info, "Exception", tr)


def _resolve_exception_cpp_type(
  tr: Translator,
  name: str,
  handler: ast.ExceptHandler,
) -> str:
  from ..analysis.runtime_symbols import CPP_EXCEPTION_TYPES

  if name in CPP_EXCEPTION_TYPES:
    return _exc_cpp_type(name)
  info = _class_info_for_exception_name(tr, name)
  if info is not None and _is_exception_class(tr, info):
    return f"::{qualify_symbol_in_module(info.module_path, info.cpp_name())}"
  raise TranslationError(
    f"未知异常类型 ``{name}``（须为当前作用域可见的 ``Exception`` 子类）",
    location=location_from_node(tr, handler),
  )


def _validate_star_type(tr: Translator, name: str, handler: ast.ExceptHandler) -> None:
  if name in _FORBIDDEN_STAR_TYPES:
    raise TranslationError(
      f"``except* {name}`` 语义歧义（对齐 Python 3.13 ``TypeError``）",
      location=location_from_node(tr, handler),
    )
  _resolve_exception_cpp_type(tr, name, handler)


def _has_bare_except(handlers: list[ast.ExceptHandler]) -> bool:
  return any(h.type is None for h in handlers)


def _emit_except_star_kind_table(types: list[str]) -> tuple[str, str]:
  arr = temp_name("exc_kinds")
  elems = ", ".join(f"{_KIND_TY}::{n}" for n in types)
  return arr, f"static const {_KIND_TY} {arr}[] = {{ {elems} }};"


def _emit_handler_catches(
  tr: Translator,
  handler: ast.ExceptHandler,
  *,
  ok_flag: str | None,
) -> None:
  types = _parse_handler_types(handler)
  for exc_name in types:
    catch_var = temp_name("exc")
    if exc_name is None:
      if handler.name is not None:
        raise NotImplementedError("bare except ... as name 暂不支持")
      header = "catch (...)"
    else:
      exc_cpp = _resolve_exception_cpp_type(tr, exc_name, handler)
      header = f"catch (const {exc_cpp}& {catch_var})"
    with tr._use_block(header):
      if ok_flag is not None:
        tr.write_line(f"{ok_flag} = false;")
      if handler.name is not None and exc_name is not None:
        from ..translator import NameContext

        pname = cpp_param(handler.name)
        if tr._try_declare(handler.name) and tr.scope:
          tr.scope.vars[handler.name] = NameContext.Variable
          bind_scope_var(tr.scope, handler.name, _exc_cpp_type(exc_name), classes=tr.classes)
        tr.write_line(f"auto& {pname} = {catch_var};")
      tr._emit_body(handler.body)


def _emit_star_handler_body(
  tr: Translator,
  handler: ast.ExceptHandler,
  *,
  active: str,
  matched: str,
  rest: str,
  ok_flag: str | None,
) -> None:
  types = _parse_handler_types(handler)
  if not types or types[0] is None:
    raise NotImplementedError("``except*:`` 须指定异常类型")
  for name in types:
    _validate_star_type(tr, name, handler)
  kind_arr, kind_init = _emit_except_star_kind_table([t for t in types if t])
  tr.write_line(kind_init)
  tr.write_line(
    f"{EXCEPTIONS_NS}::exception_group_split_except_star("
    f"{active}, {kind_arr}, {len(types)}, {matched}, {rest});",
  )
  with tr._use_block(f"if ({_pybool_cast(matched)})"):
    if ok_flag is not None:
      tr.write_line(f"{ok_flag} = false;")
    if handler.name is not None:
      from ..translator import NameContext

      pname = cpp_param(handler.name)
      if tr._try_declare(handler.name) and tr.scope:
        tr.scope.vars[handler.name] = NameContext.Variable
        bind_scope_var(tr.scope, handler.name, _GROUP_TY, classes=tr.classes)
      tr.write_line(f"const {_GROUP_TY}& {pname} = {matched};")
    tr._emit_body(handler.body)
  tr.write_line(f"{active}.copyFrom({rest});")


def emit_try(tr: Translator, node: ast.Try) -> None:
  """对齐 CPython 3.13：``else`` 仅无异常时；``finally`` 必执行且仅一次。"""
  ok_flag: str | None = None
  if node.orelse:
    ok_flag = temp_name("try_ok")
    tr.write_line(f"bool {ok_flag} = true;")

  from ..translator import _TryFrame

  frame = _TryFrame(finally_body=list(node.finalbody))
  tr._try_stack.append(frame)
  try:
    with tr._use_block("try"):
      tr._emit_body(node.body)
    for handler in node.handlers:
      _emit_handler_catches(tr, handler, ok_flag=ok_flag)
    if not _has_bare_except(node.handlers):
      with tr._use_block("catch (...)"):
        if ok_flag is not None:
          tr.write_line(f"{ok_flag} = false;")
        tr._emit_try_finally_body(frame)
        tr.write_line("throw;")
    if ok_flag is not None:
      with tr._use_block(f"if ({ok_flag})"):
        tr._emit_body(node.orelse)
    tr._emit_try_finally(frame)
  finally:
    tr._try_stack.pop()


def emit_try_star(tr: Translator, node: ast.TryStar) -> None:
  """PEP 654 / Python 3.13：``except*`` 按 ``split`` 顺序处理异常组。"""
  if node.handlers and any(h.type is None for h in node.handlers):
    raise NotImplementedError("``except*:`` 须指定异常类型")

  ok_flag: str | None = None
  if node.orelse:
    ok_flag = temp_name("try_ok")
    tr.write_line(f"bool {ok_flag} = true;")

  from ..translator import _TryFrame

  frame = _TryFrame(finally_body=list(node.finalbody))
  active = temp_name("eg_active")
  matched = temp_name("eg_match")
  rest = temp_name("eg_rest")
  eg_in = temp_name("eg_in")

  tr._try_stack.append(frame)
  tr._try_star_depth += 1
  try:
    with tr._use_block("try"):
      tr._emit_body(node.body)
    with tr._use_block(f"catch (const {_GROUP_TY}& {eg_in})"):
      tr.write_line(f"{_GROUP_TY} {active};")
      tr.write_line(f"{active}.copyFrom({eg_in});")
      tr.write_line(f"{_GROUP_TY} {matched};")
      tr.write_line(f"{_GROUP_TY} {rest};")
      for handler in node.handlers:
        _emit_star_handler_body(
          tr, handler,
          active=active, matched=matched, rest=rest, ok_flag=ok_flag,
        )
      with tr._use_block(f"if ({_pybool_cast(active)})"):
        tr.write_line(f"{EXCEPTIONS_NS}::throw_exception_group_propagate({active});")
    with tr._use_block("catch (...)"):
      if ok_flag is not None:
        tr.write_line(f"{ok_flag} = false;")
      tr._emit_try_finally_body(frame)
      tr.write_line("throw;")
    if ok_flag is not None:
      with tr._use_block(f"if ({ok_flag})"):
        tr._emit_body(node.orelse)
    tr._emit_try_finally(frame)
  finally:
    tr._try_star_depth -= 1
    tr._try_stack.pop()
