"""``ExcTypeUnion``（``@union.mro``）→ ``ExceptionGroup`` 头/实现：动态 ctx + 模板。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..analysis.ir import cpp_ident
from ..analysis.patterns import property_getter_method_for
from ..constant.stdlib_layout import EXCEPTIONS_NS
from .expand_py2cpp_template import expand_template

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator

_EXC_SLOT_NAME = "ExcTypeUnion"
_EXC_SLOT_CPP = cpp_ident(_EXC_SLOT_NAME)
_EXC_GROUP_CPP = cpp_ident("ExceptionGroup")


def _exc_slot_info(tr: Translator) -> ClassInfo | None:
  info = tr.classes.get(_EXC_SLOT_NAME)
  if info is None or not info.is_union_mro or not info.union_variants:
    return None
  return info


def _class_members(info: ClassInfo) -> list[tuple[str, str]]:
  out: list[tuple[str, str]] = []
  for member in info.union_enum_members:
    cls_name = info.union_mro_member_classes.get(member.name)
    if cls_name is None:
      continue
    out.append((member.name, cpp_ident(cls_name)))
  return out


def _mro_instance_pairs(tr: Translator, info: ClassInfo) -> list[tuple[str, str]]:
  from ..passes.mro_closure import is_subclass_of

  members = _class_members(info)
  pairs: list[tuple[str, str]] = []
  for slot_m, slot_cls in members:
    for match_m, match_cls in members:
      if slot_m == match_m:
        continue
      # union_mro_member_classes 存 Python 名；subclass 查询用原名
      slot_py = info.union_mro_member_classes.get(slot_m)
      match_py = info.union_mro_member_classes.get(match_m)
      if slot_py is None or match_py is None:
        continue
      slot_info = tr.classes.get(slot_py)
      if slot_info is None:
        continue
      if is_subclass_of(slot_info, match_py, tr):
        pairs.append((slot_m, match_m))
  return pairs


def _is_instance_body(qual_enum: str, pairs: list[tuple[str, str]]) -> str:
  body = "  if (slot == match)\n  {\n    return true;\n  }\n"
  by_match: dict[str, list[str]] = {}
  for slot_m, match_m in pairs:
    by_match.setdefault(match_m, []).append(slot_m)
  for match_m, slot_ms in sorted(by_match.items()):
    cond = " || ".join(f"slot == {qual_enum}::{s}" for s in slot_ms)
    body += f"  if (match == {qual_enum}::{match_m})\n  {{\n    return {cond};\n  }}\n"
  body += "  return false;"
  return body


def render_exception_group_header(tr: Translator) -> str:
  info = _exc_slot_info(tr)
  if info is None:
    return expand_template(
      "core/~exception_group_fallback_header.inl",
      apply_allman=False,
    ).strip()
  members = _class_members(info)
  append_decls = "\n".join(
    f"void append(const {cls}& e);"
    for _member, cls in members
  )
  return expand_template(
    "core/~exception_group_dynamic_header.inl",
    {"ctx_AppendDecls": append_decls},
    apply_allman=False,
  ).strip()


def render_exception_group_impl(tr: Translator) -> str:
  info = _exc_slot_info(tr)
  if info is None:
    return expand_template(
      "core/exception_group_fallback.inl",
      apply_allman=True,
    ).strip()
  qual_enum = f"{EXCEPTIONS_NS}::{_EXC_SLOT_CPP}::Enum"
  members = _class_members(info)
  pairs = _mro_instance_pairs(tr, info)
  enum_getter = property_getter_method_for("__enum__")
  append_impls = "\n\n".join(
    f"void {_EXC_GROUP_CPP}::append(const {cls}& e)\n"
    f"{{\n"
    f"  push_slot_impl({_EXC_SLOT_CPP}::{member}(e));\n"
    f"}}"
    for member, cls in members
  )
  from_single = "\n\n".join(
    f"{_EXC_GROUP_CPP} exception_group_from_single(const {cls}& e)\n"
    f"{{\n"
    f"  {_EXC_GROUP_CPP} g;\n"
    f"  g.append(e);\n"
    f"  return g;\n"
    f"}}"
    for _member, cls in members
  )
  return expand_template(
    "core/~exception_group_dynamic_impl.inl",
    {
      "module_rel": "core/exceptions",
      "ctx_EnumGetter": enum_getter,
      "ctx_IsInstanceBody": _is_instance_body(qual_enum, pairs),
      "ctx_AppendImpls": append_impls,
      "ctx_FromSingleImpls": from_single,
    },
    apply_allman=True,
  ).strip()
