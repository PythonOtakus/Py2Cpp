"""用户类默认 ``__repr__`` / ``__str__``（``<module.Class object at 0x…>``）。"""
from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING

from ..analysis.type_emit import sig_return_full_cpp
from ..analysis.ir import ClassInfo, cpp_ident

if TYPE_CHECKING:
  from ..translator import Translator


def _skip_class(info: ClassInfo) -> bool:
  return (
    info.is_protocol
    or info.is_descriptor
    or info.is_mixin
    or info.is_annotation
    or info.name == "str"
  )


def repr_module_name(info: ClassInfo, entry_module_path: str) -> str:
  if info.module_path == entry_module_path:
    return "__main__"
  return info.module_path.replace("\\", "/").replace("/", ".")


def needs_default_repr(info: ClassInfo) -> bool:
  return "__repr__" not in info.methods and not info.repr_aliases_str


def needs_default_str(info: ClassInfo) -> bool:
  return "__str__" not in info.methods


def has_effective_str(info: ClassInfo, tr: Translator) -> bool:
  return "__str__" in info.methods or (needs_default_str(info) and should_emit(info, tr))


def has_effective_bool(info: ClassInfo) -> bool:
  """类实现 ``__bool__`` 时生成 ``operator PyBool()``（供 ``if x`` / ``assertTrue(x)`` 等）。"""
  return "__bool__" in info.methods


def has_effective_int(info: ClassInfo) -> bool:
  """类实现 ``__int__`` 时生成 ``operator PyInt()``（供 ``int(x)`` → ``static_cast<PyInt>``）。"""
  return "__int__" in info.methods


def has_effective_float(info: ClassInfo) -> bool:
  return "__float__" in info.methods


def has_effective_complex(info: ClassInfo) -> bool:
  return "__complex__" in info.methods


def complex_operator_cpp_type(info: ClassInfo) -> str | None:
  """``operator PyComplex<…>() const`` 的 C++ 返回类型（与 ``__complex__`` 一致）。"""
  sig = info.method_sigs.get("__complex__")
  if sig is None:
    return None
  return sig_return_full_cpp(sig)


def should_emit(info: ClassInfo, tr: Translator) -> bool:
  """仅为用户模块类合成默认表示（标准库自行实现或不需要）。"""
  if _skip_class(info):
    return False
  if info.is_refcount:
    return False
  if info.class_type_if_plan is not None:
    return False
  if tr._is_stdlib_module(info.module_path):
    return False
  return needs_default_repr(info) or needs_default_str(info)


def _emit_ctx(tr: Translator, info: ClassInfo):
  if info.is_template():
    return tr._use_module_inl(info.module_path)
  if tr._is_stdlib_module(info.module_path):
    return tr._use_module_source(info.module_path)
  return nullcontext()


def _qual(tr: Translator, info: ClassInfo) -> str:
  if hasattr(tr, "_class_method_qualifier"):
    return tr._class_method_qualifier(info)
  return info.cpp_specialization() if info.is_template() else info.cpp_name()


def _virtual_prefix(info: ClassInfo) -> str:
  return "virtual " if info.has_virtual_methods else ""


def emit_default_object_repr_decls(tr: Translator, info: ClassInfo) -> None:
  if not should_emit(info, tr):
    return
  ps = cpp_ident("str")
  if needs_default_repr(info):
    mrepr = info.cpp_member_name("__repr__")
    tr.write_line(f"{_virtual_prefix(info)}{ps} {mrepr}() const;")
  if needs_default_str(info):
    mstr = info.cpp_member_name("__str__")
    tr.write_line(f"{_virtual_prefix(info)}{ps} {mstr}() const;")


def emit_default_object_repr_impls(tr: Translator, info: ClassInfo) -> None:
  if not should_emit(info, tr):
    return
  from ..analysis.ir import quote_cpp_string

  mod = repr_module_name(info, tr.entry_module_path)
  cls = info.name
  ps = cpp_ident("str")
  qual = _qual(tr, info)
  mod_cpp = quote_cpp_string(mod)
  cls_cpp = quote_cpp_string(cls)
  mrepr = info.cpp_member_name("__repr__")

  with _emit_ctx(tr, info), tr._use_source():
    if info.is_template():
      tr._emit_template_prefix(info)
    if needs_default_repr(info):
      with tr._use_block(f"{ps} {qual}::{mrepr}() const"):
        tr.write_line("char buf[128];")
        tr.write_line(
          f'snprintf(buf, sizeof(buf), "<%s.%s object at 0x%llx>", '
          f"{mod_cpp}, {cls_cpp}, "
          f"(unsigned long long)(size_t)(const void*)(this));"
        )
        tr.write_line(f"return {ps}(buf);")
      tr.write_line()
    if needs_default_str(info):
      if info.is_template():
        tr._emit_template_prefix(info)
      mstr = info.cpp_member_name("__str__")
      with tr._use_block(f"{ps} {qual}::{mstr}() const"):
        tr.write_line(f"return this->{mrepr}();")
      tr.write_line()
