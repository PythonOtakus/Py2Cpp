"""``@union`` 的 ``match`` 模式解析（含 ``MatchOr``）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass

from ..analysis.ir import ClassInfo
from .union_expand import (
  VariantCaseRef,
  parse_union_case_pattern,
  union_accepts_case_union,
)


def _is_wildcard_pattern(pattern: ast.pattern) -> bool:
  if isinstance(pattern, ast.MatchValue):
    return pattern.value is None and pattern.kind is None
  if isinstance(pattern, ast.MatchAs):
    return pattern.name == "_" and pattern.pattern is None
  return False


@dataclass(frozen=True)
class UnionMatchArm:
  """一条 ``case`` 臂：单变体、多变体 ``|``、或同变体 guard 链。"""

  variant_names: tuple[str, ...]
  binding_pattern: ast.pattern
  cases: tuple[ast.match_case, ...]


def _binding_names_from_variant_pattern(pattern: ast.pattern) -> tuple[str, ...]:
  if isinstance(pattern, ast.MatchValue):
    return ()
  if not isinstance(pattern, ast.MatchClass):
    raise ValueError(f"@union 变体模式须为 Message.Variant(...) 或 Message.Quit：{ast.dump(pattern)}")
  names: list[str] = []
  for pat in pattern.patterns:
    if isinstance(pat, ast.MatchValue):
      continue
    if isinstance(pat, ast.MatchAs) and pat.name and pat.name != "_":
      if pat.pattern is not None and not (
        isinstance(pat.pattern, ast.MatchValue)
        and isinstance(pat.pattern.value, ast.Constant)
      ):
        raise NotImplementedError(f"@union 变体字段仅支持名称或字面量：{ast.dump(pat)}")
      names.append(pat.name)
  for attr, pat in zip(pattern.kwd_attrs, pattern.kwd_patterns):
    if isinstance(pat, ast.MatchValue):
      continue
    if isinstance(pat, ast.MatchAs) and pat.name and pat.name != "_":
      if pat.pattern is not None and not (
        isinstance(pat.pattern, ast.MatchValue)
        and isinstance(pat.pattern.value, ast.Constant)
      ):
        raise NotImplementedError(f"@union 变体字段仅支持名称或字面量：{ast.dump(pat)}")
      names.append(pat.name)
  return tuple(names)


def _pattern_for_union_case(pattern: ast.pattern) -> ast.pattern:
  if isinstance(pattern, ast.MatchOr):
    if not pattern.patterns:
      raise ValueError("MatchOr 至少一个分支")
    return pattern.patterns[0]
  return pattern


def collect_union_case_refs(
  pattern: ast.pattern,
  *,
  subject_union: ClassInfo | None = None,
) -> list[VariantCaseRef]:
  if isinstance(pattern, ast.MatchOr):
    refs: list[VariantCaseRef] = []
    for p in pattern.patterns:
      ref = parse_union_case_pattern(p, subject_union=subject_union)
      if ref is None:
        raise NotImplementedError(
          f"@union match 仅支持 case {pattern} 中各分支为 Class.Variant(...) 或 new.Variant(...)",
        )
      refs.append(ref)
    return refs
  ref = parse_union_case_pattern(pattern, subject_union=subject_union)
  if ref is None:
    raise NotImplementedError(f"@union match 不支持的 case 模式：{ast.dump(pattern)}")
  return [ref]


def validate_union_or_bindings(pattern: ast.pattern) -> None:
  if not isinstance(pattern, ast.MatchOr):
    return
  names: tuple[str, ...] | None = None
  for p in pattern.patterns:
    branch_names = _binding_names_from_variant_pattern(p)
    if names is None:
      names = branch_names
    elif names != branch_names:
      raise ValueError(
        "MatchOr 各分支绑定变量须一致（名称与顺序相同），"
        f"得到 {names!r} 与 {branch_names!r}",
      )


def partition_union_match_cases(
  info: ClassInfo, node: ast.Match,
) -> tuple[list[ast.stmt] | None, list[UnionMatchArm]]:
  wildcard_body: list[ast.stmt] | None = None
  by_arm: dict[tuple[str, str], list[ast.match_case]] = {}
  or_arms: list[UnionMatchArm] = []

  for case in node.cases:
    if _is_wildcard_pattern(case.pattern):
      wildcard_body = case.body
      continue
    refs = collect_union_case_refs(case.pattern, subject_union=info)
    validate_union_or_bindings(case.pattern)
    for ref in refs:
      if not union_accepts_case_union(info, ref.union_name):
        raise TypeError(
          f"match 主体为 {info.name}，不能与 {ref.union_name}.{ref.variant_name} 匹配",
        )
      if ref.variant_name not in {v.name for v in info.union_variants}:
        raise TypeError(
          f"match 主体为 {info.name}，无变体 {ref.variant_name}",
        )
    if isinstance(case.pattern, ast.MatchOr):
      or_arms.append(
        UnionMatchArm(
          variant_names=tuple(r.variant_name for r in refs),
          binding_pattern=_pattern_for_union_case(case.pattern),
          cases=(case,),
        ),
      )
    else:
      assert len(refs) == 1
      by_arm.setdefault(refs[0].variant_name, []).append(case)

  for variant_name, cases in by_arm.items():
    or_arms.append(
      UnionMatchArm(
        variant_names=(variant_name,),
        binding_pattern=_pattern_for_union_case(cases[0].pattern),
        cases=tuple(cases),
      ),
    )
  return wildcard_body, or_arms


def check_union_match_exhaustive(
  info: ClassInfo,
  arms: list[UnionMatchArm],
  has_wildcard: bool,
) -> None:
  covered: set[str] = set()
  for arm in arms:
    for vn in arm.variant_names:
      covered.add(vn)
  required = {v.name for v in info.union_variants}
  if not has_wildcard and covered != required:
    missing = ", ".join(sorted(required - covered))
    raise ValueError(f"match {info.name} 未覆盖变体且无 case _：{missing}")
