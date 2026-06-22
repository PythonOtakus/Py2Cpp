"""``@union`` / ``@variant``：Rust 式 ADT 元数据（构造仅 ``Self.<Variant>(…)``，判别仅 ``match``）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import (
  ClassInfo,
  UnionVariantInfo,
  class_base_name,
  cpp_ident,
  has_named_decorator,
)

if TYPE_CHECKING:
  from ..translator import Translator


def _is_variant_class(node: ast.ClassDef) -> bool:
  return has_named_decorator(node, "variant")


def _parse_variant_fields(node: ast.ClassDef) -> list[tuple[str, ast.expr]]:
  fields: list[tuple[str, ast.expr]] = []
  for stmt in node.body:
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
      if stmt.annotation is None:
        raise ValueError(f"@variant {node.name}: 字段 {stmt.target.id} 缺少类型注解")
      fields.append((stmt.target.id, stmt.annotation))
  return fields


def _direct_base_name(node: ast.ClassDef) -> str | None:
  names: list[str] = []
  for base in node.bases:
    n = class_base_name(base)
    if n:
      names.append(n)
  if len(names) > 1:
    raise ValueError(f"{node.name}: 仅支持单继承")
  return names[0] if names else None


def _merge_variant_fields(
  owner: str,
  base_fields: list[tuple[str, ast.expr]],
  own_fields: list[tuple[str, ast.expr]],
) -> list[tuple[str, ast.expr]]:
  seen = {n for n, _ in base_fields}
  for n, _ in own_fields:
    if n in seen:
      raise ValueError(f"{owner}: 字段 {n} 与基类重复")
    seen.add(n)
  return list(base_fields) + list(own_fields)


def _validate_generic_union_base(
  child: ClassInfo, parent: ClassInfo, base_expr: ast.expr,
) -> None:
  if not parent.type_params:
    if child.type_params and isinstance(base_expr, ast.Subscript):
      raise ValueError(
        f"{child.name}: 基类 {parent.name} 非泛型，勿写 {parent.name}[…]",
      )
    return
  if not child.type_params:
    raise ValueError(f"{child.name}: 继承泛型 union {parent.name} 须声明相同类形参")
  if child.type_params != parent.type_params:
    raise ValueError(
      f"{child.name}: 类形参 {child.type_params!r} 须与基类 {parent.name} "
      f"{parent.type_params!r} 一致",
    )
  if isinstance(base_expr, ast.Name):
    raise ValueError(
      f"{child.name}: 继承泛型 union 须写 {parent.name}[{', '.join(child.type_params)}]",
    )
  if not isinstance(base_expr, ast.Subscript):
    raise ValueError(f"{child.name}: 非法 union 基类 {ast.dump(base_expr)}")
  if not (
    isinstance(base_expr.value, ast.Name)
    and base_expr.value.id == parent.name
  ):
    raise ValueError(f"{child.name}: 基类须为 {parent.name}[…]")


def _mark_variant_mixins(tr: Translator) -> None:
  for info in tr.classes.values():
    if info.is_variant_mixin:
      info.variant_mixin_fields = _parse_variant_fields(info.node)


def _variant_mixin_fields(tr: Translator, base_name: str, owner: str) -> list[tuple[str, ast.expr]]:
  mixin = tr.classes.get(base_name)
  if mixin is None or not mixin.is_variant_mixin:
    raise ValueError(f"{owner}: 基类 {base_name} 须为模块级 @variant 字段模板")
  if not mixin.variant_mixin_fields:
    mixin.variant_mixin_fields = _parse_variant_fields(mixin.node)
  return list(mixin.variant_mixin_fields)


def _build_nested_variant(
  tr: Translator, union_info: ClassInfo, stmt: ast.ClassDef,
) -> UnionVariantInfo:
  own = _parse_variant_fields(stmt)
  merged: list[tuple[str, ast.expr]] = []
  for base in stmt.bases:
    bn = class_base_name(base)
    if not bn:
      raise ValueError(
        f"{union_info.name}.{stmt.name}: 变体基类须为 @variant 字段模板名",
      )
    merged = _merge_variant_fields(
      f"{union_info.name}.{stmt.name}",
      merged,
      _variant_mixin_fields(tr, bn, f"{union_info.name}.{stmt.name}"),
    )
  merged = _merge_variant_fields(
    f"{union_info.name}.{stmt.name}", merged, own,
  )
  return UnionVariantInfo(
    name=stmt.name,
    fields=[n for n, _ in merged],
    field_annotations=dict(merged),
  )


def _collect_union_variants(
  tr: Translator,
  info: ClassInfo,
  *,
  visiting: frozenset[str] = frozenset(),
) -> list[UnionVariantInfo]:
  if info.name in visiting:
    raise ValueError(f"@union {info.name}: 继承环")
  visiting = visiting | {info.name}
  variants: list[UnionVariantInfo] = []
  seen: set[str] = set()
  parent_name = _direct_base_name(info.node)
  if parent_name:
    parent = tr.classes.get(parent_name)
    if parent is None or not parent.is_union:
      raise ValueError(f"{info.name}: 基类 {parent_name} 须为 @union")
    base_expr = info.node.bases[0]
    _validate_generic_union_base(info, parent, base_expr)
    for v in _collect_union_variants(tr, parent, visiting=visiting):
      variants.append(v)
      seen.add(v.name)
  for stmt in info.node.body:
    if not isinstance(stmt, ast.ClassDef) or not _is_variant_class(stmt):
      continue
    if stmt.bases and len(stmt.bases) > 1:
      raise ValueError(f"{info.name}.{stmt.name}: 变体仅支持单继承")
    v = _build_nested_variant(tr, info, stmt)
    if v.name in seen:
      raise ValueError(f"{info.name}: 重复变体 {v.name}")
    seen.add(v.name)
    variants.append(v)
  return variants


def _collect_union_family(
  tr: Translator,
  info: ClassInfo,
  *,
  visiting: frozenset[str] = frozenset(),
) -> frozenset[str]:
  if info.name in visiting:
    raise ValueError(f"@union {info.name}: 继承环")
  visiting = visiting | {info.name}
  names: set[str] = {info.name}
  parent_name = _direct_base_name(info.node)
  if parent_name:
    parent = tr.classes.get(parent_name)
    if parent is None or not parent.is_union:
      raise ValueError(f"{info.name}: 基类 {parent_name} 须为 @union")
    names |= set(_collect_union_family(tr, parent, visiting=visiting))
  return frozenset(names)


def expand_union(tr: Translator) -> None:
  """解析 ``@union`` / ``@variant`` 继承；隐式 ``@copyable``。"""
  _mark_variant_mixins(tr)
  for info in tr.classes.values():
    if not info.is_union:
      continue
    if has_named_decorator(info.node, "boxing") or info.is_refcount:
      raise ValueError(f"{info.name}: @union 与 @boxing / @refcount 互斥")
    info.is_copyable = True
    if not info.is_union_mro:
      info.union_variants = _collect_union_variants(tr, info)
    elif not info.union_variants:
      raise ValueError(f"{info.name}: @union.mro 缺少变体")
    if not info.union_variants:
      raise ValueError(f"{info.name}: @union 须至少一个变体（含继承）")
    info.union_family_names = _collect_union_family(tr, info)


def resolve_union_field_cpp_types(tr: Translator) -> None:
  """分析后填充各变体字段的 C++ 类型。"""
  for info in tr.classes.values():
    if not info.is_union:
      continue
    tparams = set(info.type_params)
    prev_aliases: dict | None = None
    if tr.type_parser is not None and info.type_aliases:
      prev_aliases = dict(tr.type_parser._type_aliases)
      tr.type_parser.set_type_aliases(info.type_aliases, use_as_cpp_name=False)
    try:
      for variant in info.union_variants:
        for fname, ann in variant.field_annotations.items():
          cpp_t = tr._parse_type(ann, tparams)
          if not cpp_t:
            cpp_t = cpp_ident("int")
          variant.field_cpp_types[fname] = cpp_t
    finally:
      if prev_aliases is not None and tr.type_parser is not None:
        tr.type_parser.set_type_aliases(prev_aliases, use_as_cpp_name=True)


@dataclass(frozen=True)
class VariantCaseRef:
  union_name: str
  variant_name: str


def _variant_name_from_new_attr(node: ast.expr) -> str | None:
  if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
    if node.value.id == "new":
      return node.attr
  return None


def parse_union_case_pattern(
  pattern: ast.pattern,
  *,
  subject_union: ClassInfo | None = None,
) -> VariantCaseRef | None:
  """``case Message.Move(...)`` / ``case new.Move(...)`` / ``case Message.Quit``。"""
  if isinstance(pattern, ast.MatchClass):
    cls = pattern.cls
    if isinstance(cls, ast.Attribute) and isinstance(cls.value, ast.Name):
      if cls.value.id == "new":
        if subject_union is None:
          return None
        return VariantCaseRef(subject_union.name, cls.attr)
      return VariantCaseRef(cls.value.id, cls.attr)
    return None
  if isinstance(pattern, ast.MatchValue):
    val = pattern.value
    vn = _variant_name_from_new_attr(val)
    if vn is not None:
      if subject_union is None:
        return None
      return VariantCaseRef(subject_union.name, vn)
    if isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name):
      return VariantCaseRef(val.value.id, val.attr)
  return None


def union_info_for_class_name(classes: dict[str, ClassInfo], name: str) -> ClassInfo | None:
  info = classes.get(name)
  if info is not None and info.is_union:
    return info
  return None


def union_variant_names(info: ClassInfo) -> frozenset[str]:
  return frozenset(v.name for v in info.union_variants)


def union_accepts_case_union(info: ClassInfo, case_union_name: str) -> bool:
  family = info.union_family_names or frozenset({info.name})
  return case_union_name in family


def union_variant_param_cpp_types(info: ClassInfo, variant_name: str) -> list[str]:
  for v in info.union_variants:
    if v.name == variant_name:
      return [v.field_cpp_types.get(f, "PyInt") for f in v.fields]
  return []


def specialize_union_variant_param_cpp_types(
  info: ClassInfo,
  variant_name: str,
  context_cpp: str | None,
) -> list[str]:
  params = union_variant_param_cpp_types(info, variant_name)
  if not context_cpp:
    return params
  from ..analysis.ir import (
    cpp_template_base_and_args,
    specialize_cpp_template_placeholders,
  )

  if not info.type_params:
    return params
  recv = context_cpp.strip()
  parsed = cpp_template_base_and_args(recv)
  class_cpp = parsed[0] if parsed else info.cpp_name()
  return [
    specialize_cpp_template_placeholders(
      pt,
      class_cpp_name=class_cpp,
      type_params=list(info.type_params),
      recv_cpp=recv,
    )
    for pt in params
  ]


def union_ctor_target_info(
  tr: Translator,
  src_union_name: str,
  variant_name: str,
  context_cpp: str | None,
) -> ClassInfo | None:
  """``Core.Move`` + 注解 ``Message`` → 生成 ``Message::Move``。"""
  src = tr.classes.get(src_union_name)
  if src is None or not src.is_union or variant_name not in union_variant_names(src):
    return None
  if not context_cpp:
    return src
  ctx = tr._class_info_for_type(context_cpp)
  if (
    ctx is not None
    and ctx.is_union
    and variant_name in union_variant_names(ctx)
    and src_union_name in (ctx.union_family_names or frozenset({ctx.name}))
  ):
    return ctx
  return src


def _subject_basename(subject_cpp: str | None) -> str:
  if not subject_cpp:
    return ""
  s = subject_cpp.strip()
  lt = s.find("<")
  return s[:lt].strip() if lt >= 0 else s


def union_info_from_subject_cpp(
  tr: Translator, subject_cpp: str,
) -> ClassInfo | None:
  bare = _subject_basename(subject_cpp)
  for info in tr.classes.values():
    if not info.is_union:
      continue
    cpp = info.cpp_name()
    if bare == cpp or bare.endswith(f"::{cpp}") or bare == info.name:
      return info
  return None
