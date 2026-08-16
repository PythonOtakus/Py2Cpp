"""``@union.mro`` 嵌套 ``Enum`` 的 ``of`` / ``create`` / ``str`` / ``repr`` / MRO 匹配。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..analysis.ir import format_cpp_int, quote_cpp_string
from ..analysis.module_namespace import qualify_symbol_in_module
from ..constant.stdlib_layout import cpp_exception_type, EXCEPTIONS_NS
from ..emit.enum_emit import _emit_enum_str_body
from ..analysis.patterns import property_getter_method_for

_CLASS_ID_GET = property_getter_method_for("__class_id__")
_ID_GET = property_getter_method_for("__id__")

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator


def _exc_base_cpp() -> str:
  return cpp_exception_type()


def _qual_union_mro_base_cpp(tr: Translator, info: ClassInfo) -> str:
  from .enum_mro_emit import _qual_mro_base_cpp

  return _qual_mro_base_cpp(tr, info.union_mro_base)


def union_mro_enum_cpp(info: ClassInfo) -> str:
  return f"{info.cpp_name()}::Enum"


def union_mro_enum_helper_name(info: ClassInfo) -> str:
  return f"{info.cpp_name()}EnumPyStr"


def emit_union_mro_inl(tr: Translator, info: ClassInfo) -> None:
  if not info.is_union_mro or not info.union_enum_members:
    return
  qual_enum = qualify_symbol_in_module(info.module_path, union_mro_enum_cpp(info))
  helper = union_mro_enum_helper_name(info)
  base_cpp = _qual_union_mro_base_cpp(tr, info)
  fn_of = f"{info.cpp_name()}_Enum_of"
  tr.write_line(f"inline {qual_enum} {fn_of}(PyInt cid)")
  tr.write_line("{")
  with tr._use_indent():
    for member in info.union_enum_members:
      cls_name = info.union_mro_member_classes.get(member.name)
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
  tr.write_line(f"inline {base_cpp} {info.cpp_name()}_Enum_create({qual_enum} k)")
  tr.write_line("{")
  with tr._use_indent():
    tr.write_line("switch (k)")
    tr.write_line("{")
    with tr._use_indent():
      for member in info.union_enum_members:
        cls_name = info.union_mro_member_classes.get(member.name)
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
  ps = "PyStr"
  cls_label = f"{info.name}.Enum"
  tr.write_line(f"struct {helper}")
  tr.write_line("{")
  with tr._use_indent():
    tr.write_line(f"{qual_enum} v;")
    tr.write_line(f"explicit {helper}({qual_enum} x) : v(x) {{}}")
    tr.write_line(f"explicit operator {ps}() const")
    tr.write_line("{")
    with tr._use_indent():
      tr.write_line(f"const PyInt u = static_cast<PyInt>(v);")
      for m in info.union_enum_members:
        mv = format_cpp_int(m.value)
        tr.write_line(f"if (u == ({mv}))")
        tr.write_line(f"  return {ps}({quote_cpp_string(f'{cls_label}.{m.name}')});")
      tr.write_line("char buf[96];")
      tr.write_line(f'snprintf(buf, sizeof(buf), "{cls_label}: %d", (int)u);')
      tr.write_line(f"return {ps}(buf);")
    tr.write_line("}")
  tr.write_line("};")
  tr.write_line()
  tr.write_line(f"inline {ps} repr({qual_enum} v)")
  tr.write_line("{")
  with tr._use_indent():
    tr.write_line(f"{ps} name = static_cast<{ps}>({helper}{{v}});")
    tr.write_line("char vbuf[32];")
    tr.write_line('snprintf(vbuf, sizeof(vbuf), "%d", (int)static_cast<PyInt>(v));')
    tr.write_line(
      f'return {ps}("<").__add__(name).__add__({ps}(": ")).__add__({ps}(vbuf)).__add__({ps}(">"));',
    )
  tr.write_line("}")
  tr.write_line()


def try_emit_union_mro_enum_call(tr: Translator, node) -> str | None:
  import ast

  if not isinstance(node, ast.Call):
    return None
  if not isinstance(node.func, ast.Attribute):
    return None
  if not isinstance(node.func.value, ast.Attribute):
    return None
  if node.func.value.attr != "Enum":
    return None
  if not isinstance(node.func.value.value, ast.Name):
    return None
  info = tr._class_info_for_ref(node.func.value.value.id)
  if info is None or not info.is_union_mro:
    return None
  method = node.func.attr
  if method == "of":
    if len(node.args) != 1:
      raise NotImplementedError(f"{info.name}.Enum.of 仅支持单参数")
    arg = tr.visit(node.args[0])
    return f"{info.cpp_name()}_Enum_of({arg}.{_CLASS_ID_GET}())"
  if method == "create":
    if len(node.args) != 1:
      raise NotImplementedError(f"{info.name}.Enum.create 仅支持单参数")
    arg = tr.visit(node.args[0])
    return f"{info.cpp_name()}_Enum_create({arg})"
  return None


def try_emit_union_mro_enum_member(tr: Translator, node: ast.Attribute) -> str | None:
  import ast

  if not isinstance(node, ast.Attribute):
    return None
  if not isinstance(node.value, ast.Attribute):
    return None
  if node.value.attr != "Enum":
    return None
  if not isinstance(node.value.value, ast.Name):
    return None
  info = tr._class_info_for_ref(node.value.value.id)
  if info is None or not info.is_union_mro:
    return None
  from ..passes.union_mro_expand import union_enum_member_names

  if node.attr not in union_enum_member_names(info):
    return None
  qual_enum = qualify_symbol_in_module(info.module_path, union_mro_enum_cpp(info))
  return f"{qual_enum}::{node.attr}"
