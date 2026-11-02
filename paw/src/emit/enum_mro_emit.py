"""``@enum.mro`` 的 ``of`` / ``create`` emit（写入模块 ``.inl``）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..analysis.module_namespace import qualify_symbol_in_module
from ..constant.stdlib_layout import cpp_exception_type, EXCEPTIONS_NS
from ..analysis.patterns import property_getter_method_for

_CLASS_ID_GET = property_getter_method_for("__class_id__")
_ID_GET = property_getter_method_for("__id__")

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator


def _exc_base_cpp() -> str:
  return cpp_exception_type()


def _qual_mro_base_cpp(tr: Translator, base_name: str | None) -> str:
  if not base_name:
    return _exc_base_cpp()
  base_info = tr.classes.get(base_name)
  if base_info is None:
    return base_name
  return qualify_symbol_in_module(base_info.module_path, base_info.cpp_name())


def emit_enum_mro_inl(tr: Translator, info: ClassInfo) -> None:
  if not info.is_enum_mro or not info.enum_members:
    return
  cpp = info.cpp_name()
  qual_enum = qualify_symbol_in_module(info.module_path, cpp)
  base_cpp = _qual_mro_base_cpp(tr, info.enum_mro_base)
  tr.write_line(f"inline {qual_enum} {cpp}_of(PyInt cid)")
  tr.write_line("{")
  with tr._use_indent():
    for member in info.enum_members:
      cls_name = info.enum_mro_member_classes.get(member.name)
      if cls_name is None:
        continue
      cls_info = tr.classes.get(cls_name)
      if cls_info is None:
        continue
      qual = qualify_symbol_in_module(cls_info.module_path, cls_info.cpp_name())
      tr.write_line(
        f"if (cid == {qual}::{_ID_GET}()) return {qual_enum}::{member.name};",
      )
    tr.write_line(f"return static_cast<{qual_enum}>(cid);")
  tr.write_line("}")
  tr.write_line()
  tr.write_line(f"inline {base_cpp} {cpp}_create({qual_enum} k)")
  tr.write_line("{")
  with tr._use_indent():
    tr.write_line("switch (k)")
    tr.write_line("{")
    with tr._use_indent():
      for member in info.enum_members:
        cls_name = info.enum_mro_member_classes.get(member.name)
        if cls_name is None:
          continue
        cls_info = tr.classes.get(cls_name)
        if cls_info is None:
          continue
        qual = qualify_symbol_in_module(cls_info.module_path, cls_info.cpp_name())
        tr.write_line(f"case {qual_enum}::{member.name}:")
        with tr._use_indent():
          tr.write_line(f"return {base_cpp}({qual}());")
      tr.write_line(f"default: return {base_cpp}();")
    tr.write_line("}")
  tr.write_line("}")
  tr.write_line()


def try_emit_enum_mro_static_call(tr: Translator, node) -> str | None:
  import ast

  if not isinstance(node, ast.Call):
    return None
  if not isinstance(node.func, ast.Attribute):
    return None
  if not isinstance(node.func.value, ast.Name):
    return None
  info = tr._class_info_for_ref(node.func.value.id)
  if info is None or not info.is_enum_mro:
    return None
  method = node.func.attr
  cpp = info.cpp_name()
  if method == "of":
    if len(node.args) != 1:
      raise NotImplementedError(f"{info.name}.of 仅支持单参数")
    arg = tr.visit(node.args[0])
    return f"{cpp}_of({arg}.{_CLASS_ID_GET}())"
  if method == "create":
    if len(node.args) != 1:
      raise NotImplementedError(f"{info.name}.create 仅支持单参数")
    arg = tr.visit(node.args[0])
    return f"{cpp}_create({arg})"
  return None


def emit_user_module_mro_inl(tr: Translator) -> None:
  """用户模块 ``@enum.mro`` / ``@union.mro`` 的 ``of`` / ``create`` 写入各模块 ``.inl``。"""
  from .union_mro_emit import emit_union_mro_inl

  modules: set[str] = set()
  for info in tr.classes.values():
    if info.is_enum_mro or info.is_union_mro:
      modules.add(info.module_path)
  for module_path in sorted(modules):
    if tr._is_stdlib_module(module_path):
      continue
    with (
      tr._use_module_inl(module_path),
      tr._use_source(),
      tr._use_import_bindings(module_path),
      tr._use_inl_namespace(module_path),
    ):
      for info in tr.classes.values():
        if info.module_path != module_path:
          continue
        if info.is_enum_mro:
          emit_enum_mro_inl(tr, info)
        if info.is_union_mro:
          emit_union_mro_inl(tr, info)
