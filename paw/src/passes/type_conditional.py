"""``type A[T, U = …] = U if T is list[U] else T`` → C++ ``pick`` 分派 + 编译期展开。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import TypeAliasInfo, collect_type_names_in_expr, validate_capture_param_names
from ..analysis.type_extract import (
  ConditionalAliasPlan,
  ConditionalBranch,
  NEVER_CPP,
  evaluate_conditional_alias,
  is_never_cpp_type,
  resolve_type_arm,
)
from .type_if import (
  TypePattern,
  _count_wildcards,
  _fresh_wildcard_slot_names,
  _parse_type_expr_node,
  _reject_not_in_form,
  _reject_not_is_form,
  _substitute_wildcards,
)
from ..analysis.type_compat import split_cpp_template, type_node_from_cpp_string

if TYPE_CHECKING:
  from ..translator import Translator


def _pick_name(alias: TypeAliasInfo) -> str:
  from ..analysis.patterns import py2cpp_emit_symbol

  return py2cpp_emit_symbol("type_cond", alias.name, str(alias.lineno), "pick")


def _parse_conditional_pattern(
  tr: Translator,
  node: ast.expr,
  *,
  subject: str,
  capture_params: set[str],
  call_params: set[str],
  loc: str,
) -> TypePattern:
  _parse_type_expr_node(node, loc=loc)
  wildcard_count = _count_wildcards(node)
  avoid = capture_params | call_params | {subject}
  wildcard_slots = (
    _fresh_wildcard_slot_names(wildcard_count, avoid=avoid)
    if wildcard_count
    else []
  )
  parse_node = _substitute_wildcards(node, wildcard_slots) if wildcard_slots else node
  extra: list[str] = []
  for name in collect_type_names_in_expr(node):
    if name in capture_params:
      if name not in extra:
        extra.append(name)
    elif name in call_params and name != subject:
      raise ValueError(
        f"{loc}: 类型模式不得引用调用形参 ``{name}``（仅 ``{subject} is …`` 左侧可测）"
      )
  parse_tparams = set(wildcard_slots) | set(extra)
  cpp = tr._parse_type(parse_node, parse_tparams).strip()
  if not cpp:
    raise ValueError(f"无法解析类型模式: {ast.dump(node, annotate_fields=False)}")
  pattern_node = type_node_from_cpp_string(cpp, classes=tr.classes)
  structural = tuple(wildcard_slots) + tuple(extra)
  if structural:
    return TypePattern(cpp, tuple(extra), structural_wildcards=structural, pattern_node=pattern_node)
  for name in collect_type_names_in_expr(node):
    if name in call_params:
      raise ValueError(f"{loc}: 类型模式不得引用调用形参 ``{name}``")
  return TypePattern(cpp, (), pattern_node=pattern_node)


def _parse_is_test(
  tr: Translator,
  test: ast.expr,
  *,
  subject: str,
  capture_params: set[str],
  call_params: set[str],
  loc: str,
) -> TypePattern:
  _reject_not_is_form(test, loc)
  _reject_not_in_form(test, loc)
  if not isinstance(test, ast.Compare) or len(test.ops) != 1:
    raise ValueError(f"{loc}: 条件别名 RHS 须为 ``{subject} is Pattern``")
  if not isinstance(test.ops[0], ast.Is):
    raise ValueError(f"{loc}: 条件别名 RHS 仅支持 ``T is Pattern``，不支持 ``is not`` / ``in``")
  if not isinstance(test.left, ast.Name) or test.left.id != subject:
    raise ValueError(f"{loc}: 条件测试左侧须为别名调用形参 ``{subject}``")
  return _parse_conditional_pattern(
    tr,
    test.comparators[0],
    subject=subject,
    capture_params=capture_params,
    call_params=call_params,
    loc=loc,
  )


def _flatten_ifexp(value: ast.expr) -> tuple[list[tuple[ast.expr, ast.expr]], ast.expr]:
  arms: list[tuple[ast.expr, ast.expr]] = []
  node = value
  while isinstance(node, ast.IfExp):
    arms.append((node.test, node.body))
    node = node.orelse
  return arms, node


def plan_conditional_alias(tr: Translator, alias: TypeAliasInfo) -> ConditionalAliasPlan:
  if not alias.is_conditional:
    raise ValueError(f"{alias.name}: 非条件类型别名")
  if not alias.call_params:
    raise ValueError(f"{alias.name}: 条件别名须至少有一个非捕获形参")
  validate_capture_param_names(
    alias.capture_params, loc=f"type {alias.name}",
  )
  subject = alias.call_params[0]
  capture = set(alias.capture_params)
  call = set(alias.call_params)
  branches_raw, else_arm = _flatten_ifexp(alias.value)
  branches: list[ConditionalBranch] = []
  used_caps: set[str] = set()
  for test, arm in branches_raw:
    pat = _parse_is_test(
      tr,
      test,
      subject=subject,
      capture_params=capture,
      call_params=call,
      loc=f"type {alias.name}",
    )
    for slot in pat.extra_template_params:
      used_caps.add(slot)
    branches.append(ConditionalBranch(pat, arm))
  for cap in capture:
    if cap not in used_caps:
      raise ValueError(
        f"type {alias.name}: 捕获形参 ``{cap}`` 须在 RHS 模式中出现（``{cap} = ...``）"
      )
  return ConditionalAliasPlan(
    subject=subject,
    call_params=alias.call_params,
    capture_params=alias.capture_params,
    branches=tuple(branches),
    else_arm=else_arm,
  )


def validate_conditional_alias_call(
  alias: TypeAliasInfo,
  slice_node: ast.expr,
) -> None:
  """禁止显式传入捕获形参。"""
  cap = set(alias.capture_params)
  if not cap:
    return
  from ..analysis.analyzer import TypeParser

  nodes = TypeParser._slice_type_arg_nodes(slice_node)
  if len(nodes) != len(alias.call_params):
    return
  for node, param in zip(nodes, alias.type_params):
    if param in cap:
      raise ValueError(
        f"{alias.name}[…]: 不得显式传入捕获形参 ``{param}``"
      )


def instantiate_conditional_alias_subscript(
  tr: Translator,
  alias: TypeAliasInfo,
  slice_node: ast.expr,
  type_params: set[str],
  *,
  cpp_name: str | None = None,
) -> str:
  validate_conditional_alias_call(alias, slice_node)
  plan = plan_conditional_alias(tr, alias)
  from ..analysis.analyzer import TypeParser

  arg_nodes = TypeParser._slice_type_arg_nodes(slice_node)
  if len(arg_nodes) != len(alias.call_params):
    raise ValueError(
      f"{alias.name}[…]: 须传入 {len(alias.call_params)} 个类型实参，"
      f"得到 {len(arg_nodes)} 个"
    )
  bindings: dict[str, str] = {}
  for param, node in zip(alias.call_params, arg_nodes):
    bindings[param] = tr._parse_type(node, type_params)
  if bindings.get(plan.subject) in type_params:
    args = ", ".join(bindings[p] for p in alias.call_params)
    return f"{cpp_name or alias.name}<{args}>"
  cpp = evaluate_conditional_alias(tr, alias, plan, bindings, type_params)
  if is_never_cpp_type(cpp):
    raise ValueError(
      f"{alias.name}[{', '.join(alias.call_params)}]: 条件求值为 Never，"
      "该类型组合无效"
    )
  return cpp


def _arm_cpp_at_emit(
  tr: Translator,
  plan: ConditionalAliasPlan,
  arm: ast.expr,
  *,
  capture_slots: tuple[str, ...] = (),
) -> str:
  fake_bindings = {plan.subject: plan.subject}
  cap = {s: s for s in capture_slots}
  return resolve_type_arm(
    tr,
    arm,
    arg_bindings=fake_bindings,
    capture_bindings=cap,
    type_params=set(plan.call_params) | set(capture_slots),
  )


def emit_conditional_type_alias(
  tr: Translator,
  alias: TypeAliasInfo,
  plan: ConditionalAliasPlan,
) -> None:
  pick = _pick_name(alias)
  subject = plan.subject
  tr.write_line(f"template<typename {subject}, typename = void>")
  tr.write_line(f"struct {pick};")
  tr.write_line()
  for br in plan.branches:
    pat = br.pattern
    arm_cpp = _arm_cpp_at_emit(
      tr, plan, br.arm, capture_slots=pat.extra_template_params,
    )
    wild = pat.wildcards_for_match()
    if wild:
      tdecl = ", ".join(f"typename {p}" for p in wild)
      tr.write_line(f"template<{tdecl}>")
      tr.write_line(f"struct {pick}<{pat.cpp_type}, void> {{")
    elif pat.extra_template_params:
      tdecl = ", ".join(f"typename {p}" for p in pat.extra_template_params)
      tr.write_line(f"template<{tdecl}>")
      tr.write_line(f"struct {pick}<{pat.cpp_type}, void> {{")
    else:
      tr.write_line("template<>")
      tr.write_line(f"struct {pick}<{pat.cpp_type}, void> {{")
    tr.write_line(f"  using type = {arm_cpp};")
    tr.write_line("};")
    tr.write_line()
  if plan.else_arm is not None:
    else_cpp = _arm_cpp_at_emit(tr, plan, plan.else_arm)
    tr.write_line(f"template<typename {subject}>")
    tr.write_line(f"struct {pick}<{subject}, void> {{")
    tr.write_line(f"  using type = {else_cpp};")
    tr.write_line("};")
  else:
    tr.write_line(f"template<typename {subject}>")
    tr.write_line(f"struct {pick}<{subject}, void> {{")
    with tr._use_indent():
      tr.write_line(
        f'static_assert(sizeof({subject}) == 0, '
        f'"条件类型别名 {alias.name} 未覆盖该类型且无 else 分支");'
      )
    tr.write_line("};")
  tr.write_line()
  tr.write_line(f"template<typename {subject}>")
  tr.write_line(f"using {alias.name} = typename {pick}<{subject}>::type;")
  tr.write_line()


def conditional_alias_rhs_cpp(alias: TypeAliasInfo) -> str:
  p = alias.call_params[0]
  return f"typename {_pick_name(alias)}<{p}>::type"
