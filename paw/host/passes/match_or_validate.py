"""``MatchOr``：各支捕获名集合相同，且同名捕获的绑定 C++ 类型一致（不限制槽位顺序）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, cpp_ident

if TYPE_CHECKING:
  from ..translator import Translator
  from .match_case import PatternMatch


@dataclass(frozen=True)
class _CaptureSig:
  bind_cpp: str
  literal_type: str | None = None


def _literal_type_name(value: object) -> str:
  if value is None:
    return "none"
  if isinstance(value, bool):
    return "bool"
  if isinstance(value, int):
    return "int"
  if isinstance(value, str):
    return "str"
  if isinstance(value, bytes):
    return "bytes"
  return type(value).__name__


def _pattern_slot_meta(pat: ast.pattern) -> tuple[str | None, str | None]:
  if isinstance(pat, ast.MatchValue) and isinstance(pat.value, ast.Constant):
    return None, _literal_type_name(pat.value.value)
  if isinstance(pat, ast.MatchAs):
    capture = pat.name if pat.name and pat.name != "_" else None
    if pat.pattern is None:
      return capture, None
    if isinstance(pat.pattern, ast.MatchValue) and isinstance(pat.pattern.value, ast.Constant):
      return capture, _literal_type_name(pat.pattern.value.value)
  return None, None


def _collect_captures(
  slots: list[tuple[str, ast.pattern]],
  *,
  bind_cpp_for_slot: dict[str, str],
) -> dict[str, _CaptureSig]:
  out: dict[str, _CaptureSig] = {}
  for slot_key, pat in slots:
    capture, lit_ty = _pattern_slot_meta(pat)
    if not capture:
      continue
    bind_cpp = bind_cpp_for_slot[slot_key]
    prev = out.get(capture)
    if prev is not None and prev.bind_cpp != bind_cpp:
      raise ValueError(
        f"同一分支内捕获名 {capture!r} 绑定类型不一致：{prev.bind_cpp!r} vs {bind_cpp!r}",
      )
    out[capture] = _CaptureSig(bind_cpp, lit_ty)
  return out


def _field_bind_cpp(info: ClassInfo, fname: str) -> str:
  from ..analysis.type_emit import field_storage_cpp

  return field_storage_cpp(info, fname) or cpp_ident("int")


def _captures_new(pattern: ast.MatchClass, info: ClassInfo) -> dict[str, _CaptureSig]:
  bind_for: dict[str, str] = {}
  slots: list[tuple[str, ast.pattern]] = []
  for attr, pat in zip(pattern.kwd_attrs, pattern.kwd_patterns):
    bind_for[attr] = _field_bind_cpp(info, attr)
    slots.append((attr, pat))
  return _collect_captures(slots, bind_cpp_for_slot=bind_for)


def _captures_sequence(pattern: ast.MatchSequence, subject_cpp: str) -> dict[str, _CaptureSig]:
  from .sequence_mapping_match import (
    _slice_rest_type,
    _split_sequence_layout,
    sequence_match_elem_cpp,
  )

  elem_cpp = sequence_match_elem_cpp(subject_cpp) or cpp_ident("int")
  rest_cpp = _slice_rest_type(subject_cpp)
  layout = _split_sequence_layout(pattern.patterns)
  bind_for: dict[str, str] = {}
  slots: list[tuple[str, ast.pattern]] = []
  for i, pat in enumerate(layout.prefix):
    key = f"p:{i}"
    bind_for[key] = elem_cpp
    slots.append((key, pat))
  for j, pat in enumerate(layout.suffix):
    key = f"s:{j}"
    bind_for[key] = elem_cpp
    slots.append((key, pat))
  out = _collect_captures(slots, bind_cpp_for_slot=bind_for)
  if layout.star is not None:
    star_name = layout.star.name
    if star_name and star_name != "_":
      out[star_name] = _CaptureSig(rest_cpp, None)
  return out


def _mapping_key_slot_key(key_pat: ast.pattern) -> str:
  if isinstance(key_pat, ast.MatchValue) and isinstance(key_pat.value, ast.Constant):
    v = key_pat.value.value
    return f"k:{type(v).__name__}:{v!r}"
  if isinstance(key_pat, ast.Constant):
    return f"k:{type(key_pat.value).__name__}:{key_pat.value!r}"
  if isinstance(key_pat, ast.MatchSingleton):
    return f"k:singleton:{key_pat.value!r}"
  raise NotImplementedError(f"映射 MatchOr 键须为字面量: {ast.dump(key_pat)}")


def _captures_mapping(pattern: ast.MatchMapping, subject_cpp: str) -> dict[str, _CaptureSig]:
  from ..analysis.ir import mapping_match_key_value_cpp
  from .sequence_mapping_match import _mapping_rest_type

  kv = mapping_match_key_value_cpp(subject_cpp)
  val_cpp = kv[1] if kv is not None else cpp_ident("int")
  rest_cpp = _mapping_rest_type(subject_cpp)
  bind_for: dict[str, str] = {}
  slots: list[tuple[str, ast.pattern]] = []
  for key_pat, val_pat in zip(pattern.keys, pattern.patterns):
    key = _mapping_key_slot_key(key_pat)
    bind_for[key] = val_cpp
    slots.append((key, val_pat))
  out = _collect_captures(slots, bind_cpp_for_slot=bind_for)
  rest = pattern.rest
  if rest and rest != "_":
    out[rest] = _CaptureSig(rest_cpp, None)
  return out


def _branch_kind(pattern: ast.pattern) -> str | None:
  if isinstance(pattern, ast.MatchValue):
    if isinstance(pattern.value, ast.Constant):
      return "literal"
    return None
  if isinstance(pattern, ast.MatchSingleton):
    return "literal"
  if (
    isinstance(pattern, ast.MatchClass)
    and isinstance(pattern.cls, ast.Name)
    and pattern.cls.id == "new"
  ):
    return "new"
  if isinstance(pattern, ast.MatchSequence):
    return "sequence"
  if isinstance(pattern, ast.MatchMapping):
    return "mapping"
  return None


def _resolve_new_info(
  tr: Translator,
  subject_cpp: str,
  classes: dict[str, ClassInfo],
  at: ast.AST,
) -> ClassInfo:
  from ..analysis.ir import class_info_for_cpp_type
  from .kwargs_options import _skip_class

  info = class_info_for_cpp_type(subject_cpp, classes)
  if info is None or _skip_class(info) or info.is_union or info.is_enum:
    from ..translation_error import raise_translation_error

    raise_translation_error(tr, at, f"case new 主体类型 {subject_cpp!r} 不可用于 MatchOr")
  return info


def _captures_for_branch(
  tr: Translator,
  pattern: ast.pattern,
  *,
  subject_cpp: str,
  classes: dict[str, ClassInfo],
) -> dict[str, _CaptureSig]:
  kind = _branch_kind(pattern)
  if kind is None:
    raise NotImplementedError(
      f"MatchOr 各支须同为 new / 序列 / 映射模式，不支持: {ast.dump(pattern)}",
    )
  if kind == "literal":
    return {}
  if kind == "new":
    assert isinstance(pattern, ast.MatchClass)
    if pattern.patterns:
      raise ValueError("case new(...) 仅支持关键字参数，勿写位置参数")
    info = _resolve_new_info(tr, subject_cpp, classes, pattern)
    return _captures_new(pattern, info)
  if kind == "sequence":
    assert isinstance(pattern, ast.MatchSequence)
    return _captures_sequence(pattern, subject_cpp)
  assert isinstance(pattern, ast.MatchMapping)
  return _captures_mapping(pattern, subject_cpp)


def validate_match_or(
  tr: Translator,
  pattern: ast.MatchOr,
  *,
  subject_cpp: str,
  classes: dict[str, ClassInfo],
  at: ast.AST | None = None,
) -> None:
  if not pattern.patterns:
    from ..translation_error import raise_translation_error

    raise_translation_error(tr, at or pattern, "MatchOr 至少一个分支")
  kinds = {_branch_kind(p) for p in pattern.patterns}
  if None in kinds or len(kinds) != 1:
    from ..translation_error import raise_translation_error

    raise_translation_error(
      tr,
      at or pattern,
      "MatchOr 各支须同为 case new(...)、case [...] 或 case {...}，不可混用",
    )
  maps = [
    _captures_for_branch(tr, p, subject_cpp=subject_cpp, classes=classes)
    for p in pattern.patterns
  ]
  ref_names = set(maps[0].keys())
  for i, m in enumerate(maps[1:], start=1):
    names = set(m.keys())
    if names != ref_names:
      from ..translation_error import raise_translation_error

      raise_translation_error(
        tr,
        at or pattern,
        "MatchOr 各支绑定变量名集合须相同，"
        f"第 0 支为 {sorted(ref_names)!r}，第 {i} 支为 {sorted(names)!r}",
      )
  for name in ref_names:
    ref_ty = maps[0][name].bind_cpp
    for i, m in enumerate(maps[1:], start=1):
      if m[name].bind_cpp != ref_ty:
        from ..translation_error import raise_translation_error

        raise_translation_error(
          tr,
          at or pattern,
          f"MatchOr 捕获 {name!r} 的绑定类型须在各支一致，"
          f"第 0 支为 {ref_ty!r}，第 {i} 支为 {m[name].bind_cpp!r}",
        )


def _binding_layout_key(pm: PatternMatch) -> tuple[tuple[str, ...], tuple[str, ...]]:
  return (tuple(pm.prelude_lines), tuple(ast.dump(b) for b in pm.bindings))


def _assign_target_name(stmt: ast.stmt) -> str | None:
  if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
    return None
  tgt = stmt.targets[0]
  if isinstance(tgt, ast.Name):
    return tgt.id
  return None


def _or_binding_prelude_lines(
  tr: Translator,
  arms: list[tuple[str, PatternMatch]],
  decls: dict[str, str],
) -> list[str]:
  lines: list[str] = [f"{cpp} {name};" for name, cpp in sorted(decls.items())]
  for i, (arm_cond, arm) in enumerate(arms):
    kw = "if" if i == 0 else "else if"
    lines.append(f"{kw} ({arm_cond})")
    lines.append("{")
    for pl in arm.prelude_lines:
      lines.append(f"  {pl}")
    for b in arm.bindings:
      name = _assign_target_name(b)
      if name is None:
        raise NotImplementedError(f"MatchOr 绑定须为简单赋值: {ast.dump(b)}")
      val = tr.visit(b.value)
      lines.append(f"  {name} = {val};")
    lines.append("}")
  return lines


def merge_match_or_parts(
  tr: Translator,
  parts: list[PatternMatch],
  pattern: ast.MatchOr,
  *,
  subject_cpp: str,
  classes: dict[str, ClassInfo],
) -> PatternMatch:
  from .match_case import PatternMatch

  if not parts:
    return PatternMatch(condition="true")
  conds = [p.condition for p in parts if p.condition and p.condition != "true"]
  outer = "(" + " || ".join(conds) + ")" if conds else "true"
  ref_key = _binding_layout_key(parts[0])
  if all(_binding_layout_key(p) == ref_key for p in parts):
    return PatternMatch(
      condition=outer,
      bindings=list(parts[0].bindings),
      prelude_lines=list(parts[0].prelude_lines),
    )
  maps = [
    _captures_for_branch(tr, p, subject_cpp=subject_cpp, classes=classes)
    for p in pattern.patterns
  ]
  decls = {name: maps[0][name].bind_cpp for name in maps[0]}
  arms: list[tuple[str, PatternMatch]] = []
  for p in parts:
    arm_cond = p.condition if p.condition and p.condition != "true" else "true"
    arms.append((arm_cond, p))
  prelude = _or_binding_prelude_lines(tr, arms, decls)
  return PatternMatch(condition=outer, prelude_lines=prelude)
