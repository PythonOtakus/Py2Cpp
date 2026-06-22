"""合成 ``__id__`` / ``__class_id__`` C++ emit。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..analysis.ir import format_cpp_int
from ..analysis.patterns import property_getter_method_for

_CLASS_ID_GET = property_getter_method_for("__class_id__")
_ID_GET = property_getter_method_for("__id__")

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator


def _skip_entity_base(info: ClassInfo | None) -> bool:
  if info is None:
    return True
  return info.is_protocol or info.is_mixin or info.is_annotation


def _base_has_virtual_class_id(tr: Translator, info: ClassInfo) -> bool:
  """实体基类链上是否已有虚 ``__class_id____get``（基类含其它虚函数，或链上已声明 virtual）。"""
  for base_name in info.bases:
    base_info = tr.classes.get(base_name)
    if _skip_entity_base(base_info):
      continue
    if base_info is not None and base_info.inject_type_id:
      if base_info.force_virtual_class_id or base_info.has_virtual_methods:
        return True
      if _base_has_virtual_class_id(tr, base_info):
        return True
  return False


def class_id_is_virtual(tr: Translator, info: ClassInfo) -> bool:
  """``__class_id____get`` 是否为虚函数（``@enum.mro`` / ``@union.mro`` 基类或类内其它虚函数）。"""
  if info.force_virtual_class_id:
    return True
  return info.has_virtual_methods


def type_id_class_id_decl_parts(tr: Translator, info: ClassInfo) -> tuple[str, str]:
  """``__class_id____get`` 声明前后缀：虚基链上 ``override``，否则首个虚函数处 ``virtual``。"""
  if _base_has_virtual_class_id(tr, info):
    return ("", " override")
  if class_id_is_virtual(tr, info):
    return ("virtual ", "")
  return ("", "")


def emit_type_id_decls(tr: Translator, info: ClassInfo) -> None:
  if not info.inject_type_id or info.class_id is None:
    return
  vprefix, vsuffix = type_id_class_id_decl_parts(tr, info)
  tr.write_line("static const PyInt __py2cpp_class_id__;")
  tr.write_line(f"static PyInt {_ID_GET}();")
  tr.write_line(f"{vprefix}PyInt {_CLASS_ID_GET}() const{vsuffix};")


def emit_type_id_impls(tr: Translator, info: ClassInfo) -> None:
  if not info.inject_type_id or info.class_id is None:
    return
  qual = tr._class_method_qualifier(info)
  cid = format_cpp_int(info.class_id)
  if info.is_template():
    tr._emit_template_prefix(info)
  tr.write_line(f"const PyInt {qual}::__py2cpp_class_id__ = {cid};")
  tr.write_line()
  if info.is_template():
    tr._emit_template_prefix(info)
  tr.write_line(f"PyInt {qual}::{_CLASS_ID_GET}() const")
  tr.write_line("{")
  with tr._use_indent():
    tr.write_line("return __py2cpp_class_id__;")
  tr.write_line("}")
  tr.write_line()
  if info.is_template():
    tr._emit_template_prefix(info)
  tr.write_line(f"PyInt {qual}::{_ID_GET}()")
  tr.write_line("{")
  with tr._use_indent():
    tr.write_line("return __py2cpp_class_id__;")
  tr.write_line("}")
  tr.write_line()
