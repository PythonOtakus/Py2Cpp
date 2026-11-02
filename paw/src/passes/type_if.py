"""泛型形参编译期 ``if T is int`` / ``T is not int`` / ``T in [int, str]`` / ``T not in {…}`` → C++ 分派 struct。"""
from __future__ import annotations

import ast
import copy
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ..analysis.type_emit import method_param_storage_cpp, sig_return_storage_cpp
from ..analysis.ir import (
  FunctionSig,
  MethodSig,
  cpp_param,
  format_fn_sig,
  is_stub_function_body,
)
from ..analysis.type_compat import split_cpp_template, type_node_from_cpp_string
from ..analysis.ir import collect_type_names_in_expr, typevar_default_is_capture, validate_capture_param_names
from ..analysis.type_node import TypeNode, structural_match_type_nodes

if TYPE_CHECKING:
  from ..translator import Translator

# 兼容旧 import：``from .passes.type_if import _split_cpp_template``
_split_cpp_template = split_cpp_template

_CALL_METHOD = "__call__"


def _stmt_contains(node: ast.AST, target: ast.AST) -> bool:
  if node is target:
    return True
  for child in ast.iter_child_nodes(node):
    if _stmt_contains(child, target):
      return True
  return False


def _prologue_stmts_before_type_if(
  func: ast.FunctionDef,
  head: ast.If,
) -> list[ast.stmt]:
  prologue: list[ast.stmt] = []
  for stmt in _strip_docstring(func.body):
    if stmt is head or _stmt_contains(stmt, head):
      break
    prologue.append(stmt)
  return prologue


@dataclass(frozen=True)
class TypePattern:
  cpp_type: str
  extra_template_params: tuple[str, ...] = ()
  """匹配后绑定到 C++ 类型实参的捕获形参名（如 ``_K``）。"""
  structural_wildcards: tuple[str, ...] | None = None
  """结构匹配时视为通配的模板位（含 ``...`` 替换出的 ``_Ty*``）；默认同 ``extra_template_params``。"""
  pattern_node: TypeNode | None = None
  """结构化模式（Phase 2）；缺省时由 ``cpp_type`` 解析。"""

  def wildcards_for_match(self) -> tuple[str, ...]:
    if self.structural_wildcards is not None:
      return self.structural_wildcards
    return self.extra_template_params


@dataclass(frozen=True)
class TypeIfClause:
  param: str
  kind: Literal["is", "is_not", "in", "not_in"]
  patterns: tuple[TypePattern, ...]


@dataclass
class TypeIfBranch:
  """``(A and B) or (C and D)`` → ``or_groups=[[A,B],[C,D]]``。"""

  or_groups: list[list[TypeIfClause]]
  body: list[ast.stmt]

  @property
  def clauses(self) -> list[TypeIfClause]:
    if len(self.or_groups) != 1:
      raise AttributeError("multi-disjunct type if branch")
    return self.or_groups[0]

  @property
  def kind(self) -> Literal["is", "is_not", "in", "not_in"]:
    if len(self.or_groups) != 1 or len(self.or_groups[0]) != 1:
      raise AttributeError("multi-clause type if branch")
    return self.or_groups[0][0].kind

  @property
  def patterns(self) -> list[TypePattern]:
    if len(self.or_groups) != 1 or len(self.or_groups[0]) != 1:
      raise AttributeError("multi-clause type if branch")
    return list(self.or_groups[0][0].patterns)


@dataclass
class TypeIfChain:
  type_param: str
  branches: list[TypeIfBranch]
  else_body: list[ast.stmt] | None
  head: ast.If


@dataclass
class TypeIfFunctionPlan:
  """整函数 type-if lowering：master 链生成分派特化，全部链在 emit 时剪枝。"""

  master_chain: TypeIfChain
  chains: tuple[TypeIfChain, ...]
  func: ast.FunctionDef


@dataclass(frozen=True)
class _ExactSpec:
  cpp_type: str


@dataclass(frozen=True)
class _PatternSpec:
  pattern: TypePattern


@dataclass(frozen=True)
class _IsNotEnableIfSpec:
  excluded: str


@dataclass(frozen=True)
class _NotInEnableIfSpec:
  patterns: tuple[TypePattern, ...]


@dataclass(frozen=True)
class _DefaultElseSpec:
  pass


_SpliceSpec = (
  _ExactSpec | _PatternSpec | _IsNotEnableIfSpec | _NotInEnableIfSpec | _DefaultElseSpec
)


def _is_type_wildcard(node: ast.expr) -> bool:
  if isinstance(node, ast.Constant) and node.value is Ellipsis:
    return True
  return isinstance(node, ast.Ellipsis)


def _reject_underscore_wildcard(node: ast.expr, *, loc: str) -> None:
  match node:
    case ast.Name(id="_"):
      raise ValueError(
        f"{loc}: 类型模式不支持 ``_``，未知类型参数请写 ``...``（如 ``list[...]``）"
      )
    case ast.Subscript(value=value, slice=sl):
      _reject_underscore_wildcard(value, loc=loc)
      if isinstance(sl, ast.Tuple):
        for i, elt in enumerate(sl.elts):
          _reject_underscore_wildcard(elt, loc=f"{loc} (实参 {i})")
      else:
        _reject_underscore_wildcard(sl, loc=loc)
    case ast.Attribute(value=value):
      _reject_underscore_wildcard(value, loc=loc)
    case _:
      return


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
  if (
    body
    and isinstance(body[0], ast.Expr)
    and isinstance(body[0].value, ast.Constant)
    and isinstance(body[0].value.value, str)
  ):
    return body[1:]
  return body


def _reject_not_is_form(test: ast.expr, loc: str) -> None:
  if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
    if isinstance(test.operand, ast.Compare):
      raise ValueError(
        f"{loc}: 类型 if 不支持 ``not T is int``，请写 ``T is not int``"
      )


def _reject_not_in_form(test: ast.expr, loc: str) -> None:
  if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
    opnd = test.operand
    if (
      isinstance(opnd, ast.Compare)
      and len(opnd.ops) == 1
      and isinstance(opnd.ops[0], ast.In)
      and isinstance(opnd.left, ast.Name)
    ):
      raise ValueError(
        f"{loc}: 类型 if 不支持 ``not T in {{…}}``，请写 ``T not in {{…}}``"
      )


def _is_type_if_compare(cmp: ast.Compare) -> bool:
  if len(cmp.ops) != 1 or not isinstance(cmp.left, ast.Name):
    return False
  return isinstance(cmp.ops[0], (ast.Is, ast.IsNot, ast.In, ast.NotIn))


def _flatten_and_compare(test: ast.expr) -> list[ast.Compare]:
  """``A and B and C`` → 各 ``Compare`` 子句（不含 ``or``）。"""
  if isinstance(test, ast.BoolOp):
    if not isinstance(test.op, ast.And):
      raise ValueError("expected AND-only subexpression")
    parts: list[ast.Compare] = []
    for v in test.values:
      parts.extend(_flatten_and_compare(v))
    return parts
  if isinstance(test, ast.Compare):
    return [test]
  return []


def _type_if_dnf(test: ast.expr) -> list[list[ast.Compare]]:
  """类型 if 条件化为 DNF：外层 ``or``、内层 ``and``。"""
  if isinstance(test, ast.BoolOp):
    if isinstance(test.op, ast.Or):
      groups: list[list[ast.Compare]] = []
      for v in test.values:
        groups.extend(_type_if_dnf(v))
      return groups
    if isinstance(test.op, ast.And):
      acc: list[list[ast.Compare]] = [[]]
      for v in test.values:
        sub = _type_if_dnf(v)
        merged: list[list[ast.Compare]] = []
        for left in acc:
          for right in sub:
            merged.append(left + right)
        acc = merged
      return acc
  if isinstance(test, ast.Compare):
    return [[test]]
  return []


def _type_if_compares_flat(test: ast.expr) -> list[ast.Compare]:
  out: list[ast.Compare] = []
  for group in _type_if_dnf(test):
    out.extend(group)
  return out


def _func_capture_params(func: ast.FunctionDef) -> set[str]:
  out: set[str] = set()
  for tp in getattr(func, "type_params", None) or ():
    if isinstance(tp, ast.TypeVar) and typevar_default_is_capture(
      getattr(tp, "default_value", None),
    ):
      out.add(tp.name)
  return out


def _class_capture_params(class_node: ast.ClassDef) -> set[str]:
  out: set[str] = set()
  for tp in getattr(class_node, "type_params", None) or ():
    if isinstance(tp, ast.TypeVar) and typevar_default_is_capture(
      getattr(tp, "default_value", None),
    ):
      out.add(tp.name)
  return out


def _call_type_params(all_params: set[str], capture_params: set[str]) -> set[str]:
  return all_params - capture_params


def _ordered_type_param_names(node: ast.FunctionDef | ast.ClassDef) -> list[str]:
  names: list[str] = []
  for tp in getattr(node, "type_params", None) or ():
    if isinstance(tp, ast.TypeVar):
      names.append(tp.name)
  return names


def _substitute_capture_in_cpp(cpp: str, subst: dict[str, str]) -> str:
  base, args = split_cpp_template(cpp)
  if not args:
    return subst.get(cpp, cpp)
  new_args = [subst.get(a, a) for a in args]
  return f"{base}<{', '.join(new_args)}>"


def _branch_is_not(br: TypeIfBranch) -> bool:
  return (
    len(br.or_groups) == 1
    and len(br.or_groups[0]) == 1
    and br.or_groups[0][0].kind == "is_not"
  )


def _branch_not_in(br: TypeIfBranch) -> bool:
  return (
    len(br.or_groups) == 1
    and len(br.or_groups[0]) == 1
    and br.or_groups[0][0].kind == "not_in"
  )


def _branch_single_is(br: TypeIfBranch) -> TypeIfClause | None:
  if len(br.or_groups) == 1 and len(br.or_groups[0]) == 1:
    c = br.or_groups[0][0]
    if c.kind == "is":
      return c
  return None


def _branch_single_in(br: TypeIfBranch) -> TypeIfClause | None:
  if len(br.or_groups) == 1 and len(br.or_groups[0]) == 1:
    c = br.or_groups[0][0]
    if c.kind == "in":
      return c
  return None


def _collect_type_names(node: ast.expr) -> set[str]:
  names: set[str] = set()
  match node:
    case ast.Name(id=name):
      names.add(name)
    case ast.Subscript(value=value, slice=sl):
      names |= _collect_type_names(value)
      if isinstance(sl, ast.Tuple):
        for elt in sl.elts:
          names |= _collect_type_names(elt)
      else:
        names |= _collect_type_names(sl)
    case ast.Attribute(value=value):
      names |= _collect_type_names(value)
    case _:
      pass
  return names


def _contains_wildcard(node: ast.expr) -> bool:
  match node:
    case _ if _is_type_wildcard(node):
      return True
    case ast.Subscript(value=value, slice=sl):
      if _contains_wildcard(value):
        return True
      if isinstance(sl, ast.Tuple):
        return any(_contains_wildcard(elt) for elt in sl.elts)
      return _contains_wildcard(sl)
    case ast.Attribute(value=value):
      return _contains_wildcard(value)
    case _:
      return False


def _count_wildcards(node: ast.expr) -> int:
  match node:
    case _ if _is_type_wildcard(node):
      return 1
    case ast.Subscript(value=value, slice=sl):
      n = _count_wildcards(value)
      if isinstance(sl, ast.Tuple):
        n += sum(_count_wildcards(elt) for elt in sl.elts)
      else:
        n += _count_wildcards(sl)
      return n
    case ast.Attribute(value=value):
      return _count_wildcards(value)
    case _:
      return 0


def _substitute_wildcards(node: ast.expr, slots: list[str]) -> ast.expr:
  idx = 0

  def visit(n: ast.expr) -> ast.expr:
    nonlocal idx
    if _is_type_wildcard(n):
      name = slots[idx]
      idx += 1
      return ast.Name(id=name, ctx=ast.Load())
    match n:
      case ast.Subscript(value=value, slice=sl):
        new_sl: ast.expr
        if isinstance(sl, ast.Tuple):
          new_sl = ast.Tuple(
            elts=[visit(elt) for elt in sl.elts],
            ctx=sl.ctx,
          )
        else:
          new_sl = visit(sl)
        return ast.Subscript(value=visit(value), slice=new_sl, ctx=n.ctx)
      case ast.Attribute(value=value, attr=attr, ctx=ctx):
        return ast.Attribute(value=visit(value), attr=attr, ctx=ctx)
      case _:
        return copy.deepcopy(n)

  out = visit(node)
  if idx != len(slots):
    raise ValueError("类型模式 ``...`` 替换失败")
  return out


def _fresh_wildcard_slot_names(count: int, *, avoid: set[str]) -> list[str]:
  names: list[str] = []
  i = 0
  while len(names) < count:
    candidate = f"_Ty{i}"
    if candidate not in avoid:
      names.append(candidate)
    i += 1
  return names


def _validate_pattern_type_names(
  node: ast.expr,
  *,
  tparams: set[str],
  type_param: str,
  capture_params: set[str],
  loc: str,
) -> None:
  _reject_underscore_wildcard(node, loc=loc)
  if isinstance(node, ast.Name) and _is_type_wildcard(node):
    raise ValueError(f"{loc}: 类型 if 不支持 ``T is ...``，请写 ``T is list[...]`` 等容器模式")
  for name in _collect_type_names(node):
    if name in capture_params:
      continue
    if name == type_param:
      raise ValueError(
        f"{loc}: 类型模式不得使用泛型形参 ``{type_param}``，"
        "未知类型参数请写 ``...``（如 ``list[...]``）"
      )
    if name in tparams:
      raise ValueError(
        f"{loc}: 类型模式不得引用其它泛型形参 ``{name}``，"
        "未知类型参数请写 ``...``（如 ``list[...]``）"
      )


def _structural_type_match(
  concrete: str,
  pattern: str,
  wildcards: tuple[str, ...],
) -> bool:
  wild = frozenset(wildcards)
  conc_node = type_node_from_cpp_string(concrete)
  pat_node = type_node_from_cpp_string(pattern)
  if wild:
    return structural_match_type_nodes(conc_node, pat_node, wild) is not None
  conc_base, conc_args = split_cpp_template(concrete)
  pat_base, pat_args = split_cpp_template(pattern)
  if conc_base != pat_base or len(conc_args) != len(pat_args):
    return False
  for conc_arg, pat_arg in zip(conc_args, pat_args):
    if pat_arg in wild:
      continue
    if conc_arg != pat_arg:
      return False
  return True


def _parse_type_pattern(
  tr: Translator,
  node: ast.expr,
  *,
  tparams: set[str],
  type_param: str,
  capture_params: set[str],
  loc: str,
) -> TypePattern:
  _validate_pattern_type_names(
    node,
    tparams=tparams,
    type_param=type_param,
    capture_params=capture_params,
    loc=loc,
  )
  wildcard_count = _count_wildcards(node)
  avoid = tparams | capture_params | {type_param}
  slot_names = _fresh_wildcard_slot_names(wildcard_count, avoid=avoid)
  parse_node = _substitute_wildcards(node, slot_names) if slot_names else node
  extra: list[str] = []
  for name in collect_type_names_in_expr(node):
    if name in capture_params and name not in extra:
      extra.append(name)
  parse_tparams = set(tparams) | set(slot_names) | set(extra)
  cpp = tr._parse_type(parse_node, parse_tparams).strip()
  if not cpp:
    raise ValueError(f"无法解析类型模式: {ast.dump(node, annotate_fields=False)}")
  pattern_node = type_node_from_cpp_string(cpp, classes=tr.classes)
  structural = tuple(slot_names) + tuple(extra)
  if structural:
    emit_extra = tuple(extra) if extra else tuple(slot_names)
    return TypePattern(
      cpp,
      emit_extra,
      structural_wildcards=structural,
      pattern_node=pattern_node,
    )
  for name in collect_type_names_in_expr(node):
    if name in tparams and name not in capture_params:
      raise ValueError(
        f"{loc}: 类型模式须为具体类型或 ``...`` 占位，"
        f"不得引用泛型形参 {name}"
      )
  for name in re.findall(r"\b([A-Z][A-Za-z0-9_]*)\b", cpp):
    if name in tparams and name not in capture_params:
      raise ValueError(
        f"{loc}: 类型模式须为具体类型或 ``...`` 占位，"
        f"不得引用泛型形参 {name}"
      )
  return TypePattern(cpp, tuple(extra), pattern_node=pattern_node)


def _parse_type_expr_node(node: ast.expr, *, loc: str) -> None:
  match node:
    case ast.Name() | ast.Subscript() | ast.Attribute():
      return
    case _:
      raise ValueError(f"{loc}: 类型 if 右侧须为类型表达式（builtin / 类 / list[int] 等）")


def _parse_type_if_clause(
  tr: Translator,
  cmp: ast.Compare,
  *,
  loc: str,
  tparams: set[str],
  call_tparams: set[str],
  capture_params: set[str],
) -> TypeIfClause:
  if len(cmp.ops) != 1 or not isinstance(cmp.left, ast.Name):
    raise ValueError(f"{loc}: 类型 if 子句须为 ``Param is …`` / ``Param in […]`` 等形式")
  param = cmp.left.id
  allowed = call_tparams | capture_params
  if param not in allowed:
    raise ValueError(f"{loc}: ``{param}`` 不是当前函数/类的泛型形参")
  op = cmp.ops[0]
  comp = cmp.comparators[0]
  match op:
    case ast.Is():
      _parse_type_expr_node(comp, loc=loc)
      if param in capture_params and _contains_wildcard(comp):
        raise ValueError(f"{loc}: 捕获形参 ``{param} is …`` 须为具体类型")
      pat = _parse_type_pattern(
        tr,
        comp,
        tparams=tparams,
        type_param=param,
        capture_params=capture_params,
        loc=loc,
      )
      if param in capture_params and pat.extra_template_params:
        raise ValueError(f"{loc}: 捕获形参 ``{param} is …`` 须为具体类型")
      return TypeIfClause(param, "is", (pat,))
    case ast.IsNot():
      _parse_type_expr_node(comp, loc=loc)
      if _contains_wildcard(comp):
        raise ValueError(f"{loc}: ``T is not …`` 不支持 ``...`` 类型模式")
      pat = _parse_type_pattern(
        tr,
        comp,
        tparams=tparams,
        type_param=param,
        capture_params=capture_params,
        loc=loc,
      )
      return TypeIfClause(param, "is_not", (pat,))
    case ast.In():
      if not isinstance(comp, (ast.List, ast.Set)):
        raise ValueError(f"{loc}: ``{param} in …`` 须为 ``list[…]`` 或 ``{{…}}`` 字面量")
      if not comp.elts:
        raise ValueError(f"{loc}: ``{param} in …`` 容器不能为空")
      patterns: list[TypePattern] = []
      for i, elt in enumerate(comp.elts):
        _parse_type_expr_node(elt, loc=f"{loc} (元素 {i})")
        if _contains_wildcard(elt):
          raise ValueError(
            f"{loc} (元素 {i}): ``{param} in […]`` 元素须为具体类型，"
            "不支持 ``...`` 类型模式"
          )
        patterns.append(
          _parse_type_pattern(
            tr,
            elt,
            tparams=tparams,
            type_param=param,
            capture_params=capture_params,
            loc=f"{loc} (元素 {i})",
          )
        )
      return TypeIfClause(param, "in", tuple(patterns))
    case ast.NotIn():
      if not isinstance(comp, (ast.List, ast.Set)):
        raise ValueError(f"{loc}: ``{param} not in …`` 须为 ``list[…]`` 或 ``{{…}}`` 字面量")
      if not comp.elts:
        raise ValueError(f"{loc}: ``{param} not in …`` 容器不能为空")
      patterns = []
      for i, elt in enumerate(comp.elts):
        _parse_type_expr_node(elt, loc=f"{loc} (元素 {i})")
        if _contains_wildcard(elt):
          raise ValueError(
            f"{loc} (元素 {i}): ``{param} not in {{…}}`` 元素须为具体类型，"
            "不支持 ``...`` 类型模式"
          )
        patterns.append(
          _parse_type_pattern(
            tr,
            elt,
            tparams=tparams,
            type_param=param,
            capture_params=capture_params,
            loc=f"{loc} (元素 {i})",
          )
        )
      return TypeIfClause(param, "not_in", tuple(patterns))
    case _:
      raise ValueError(
        f"{loc}: 类型 if 仅支持 ``is`` / ``is not`` / ``in`` / ``not in``"
      )


def _parse_type_if_branch_test(
  tr: Translator,
  test: ast.expr,
  *,
  loc: str,
  tparams: set[str],
  call_tparams: set[str],
  capture_params: set[str],
) -> TypeIfBranch | None:
  _reject_not_is_form(test, loc)
  _reject_not_in_form(test, loc)
  dnf = _type_if_dnf(test)
  if not dnf:
    return None
  or_groups: list[list[TypeIfClause]] = []
  for group in dnf:
    if not all(_is_type_if_compare(cmp) for cmp in group):
      return None
    clauses: list[TypeIfClause] = []
    for cmp in group:
      clauses.append(
        _parse_type_if_clause(
          tr,
          cmp,
          loc=loc,
          tparams=tparams,
          call_tparams=call_tparams,
          capture_params=capture_params,
        )
      )
    if len(clauses) > 1:
      for c in clauses:
        if c.kind in ("is_not", "not_in"):
          raise ValueError(
            f"{loc}: ``and`` 组合不支持 ``is not`` / ``not in`` 子句"
          )
    or_groups.append(clauses)
  if len(or_groups) > 1:
    for group in or_groups:
      if len(group) > 1:
        raise ValueError(f"{loc}: ``or`` 组合中每项须为单一 ``T is …`` / ``T in […]``")
      if group[0].kind in ("is_not", "not_in"):
        raise ValueError(f"{loc}: ``or`` 组合不支持 ``is not`` / ``not in``")
  return TypeIfBranch(or_groups, [])


def _resolve_chain_type_param(test: ast.expr, call_tparams: set[str]) -> str | None:
  for cmp in _type_if_compares_flat(test):
    if isinstance(cmp.left, ast.Name) and cmp.left.id in call_tparams:
      return cmp.left.id
  return None


def _looks_like_type_if_head(
  test: ast.expr,
  call_tparams: set[str],
  *,
  capture_params: set[str] | None = None,
) -> bool:
  _reject_not_is_form(test, "类型 if")
  _reject_not_in_form(test, "类型 if")
  allowed = call_tparams | (capture_params or set())
  for group in _type_if_dnf(test):
    for cmp in group:
      if not _is_type_if_compare(cmp):
        continue
      if isinstance(cmp.left, ast.Name) and cmp.left.id in allowed:
        if cmp.left.id in call_tparams:
          return True
  return False


def _collect_type_if_chain(
  tr: Translator,
  head: ast.If,
  *,
  tparams: set[str],
  call_tparams: set[str],
  capture_params: set[str],
) -> TypeIfChain:
  if isinstance(head.test, ast.UnaryOp) and isinstance(head.test.op, ast.Not):
    _reject_not_is_form(head.test, "类型 if")
    _reject_not_in_form(head.test, "类型 if")
  for cmp in _type_if_compares_flat(head.test):
    left = cmp.left
    if (
      isinstance(left, ast.UnaryOp)
      and isinstance(left.op, ast.Not)
      and isinstance(left.operand, ast.Name)
      and left.operand.id in call_tparams
    ):
      raise ValueError(
        "类型 if 不支持 ``not T is int``（Python 解析为 ``(not T) is int``），"
        "请写 ``T is not int``"
      )
  type_param = _resolve_chain_type_param(head.test, call_tparams)
  if type_param is None:
    raise ValueError("类型 if 条件须包含对调用形参（非捕获形参）的类型测试")
  first = _parse_type_if_branch_test(
    tr,
    head.test,
    loc="类型 if",
    tparams=tparams,
    call_tparams=call_tparams,
    capture_params=capture_params,
  )
  if first is None:
    raise ValueError(
      f"类型 if 条件须为 ``{type_param} is …`` / "
      f"``{type_param} is not …`` / ``{type_param} in […]`` / "
      f"``{type_param} not in {{…}}``（可用 ``and`` / ``or`` 组合）"
    )
  branches: list[TypeIfBranch] = []
  node: ast.If | None = head
  while node is not None:
    br = _parse_type_if_branch_test(
      tr,
      node.test,
      loc="类型 if",
      tparams=tparams,
      call_tparams=call_tparams,
      capture_params=capture_params,
    )
    if br is None:
      raise ValueError("类型 if ``elif`` 链中不得混入值条件")
    br.body = list(node.body)
    branches.append(br)
    if not node.orelse:
      return TypeIfChain(type_param, branches, None, head)
    if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
      node = node.orelse[0]
      continue
    return TypeIfChain(type_param, branches, list(node.orelse), head)
  raise ValueError("类型 if 链解析失败")


def _scan_stmt_list_for_chains(
  tr: Translator,
  stmts: list[ast.stmt],
  *,
  tparams: set[str],
  capture_params: set[str],
  out: list[TypeIfChain],
) -> None:
  call_tparams = _call_type_params(tparams, capture_params)
  for stmt in stmts:
    if isinstance(stmt, ast.If):
      if _looks_like_type_if_head(
        stmt.test, call_tparams, capture_params=capture_params,
      ):
        out.append(
          _collect_type_if_chain(
            tr,
            stmt,
            tparams=tparams,
            call_tparams=call_tparams,
            capture_params=capture_params,
          )
        )
      else:
        _scan_stmt_list_for_chains(
          tr, stmt.body, tparams=tparams, capture_params=capture_params, out=out,
        )
        _scan_stmt_list_for_chains(
          tr, stmt.orelse, tparams=tparams, capture_params=capture_params, out=out,
        )
    elif isinstance(stmt, (ast.For, ast.While, ast.With)):
      _scan_stmt_list_for_chains(
        tr, stmt.body, tparams=tparams, capture_params=capture_params, out=out,
      )
      _scan_stmt_list_for_chains(
        tr, stmt.orelse, tparams=tparams, capture_params=capture_params, out=out,
      )
    elif isinstance(stmt, (ast.Try, ast.TryStar)):
      _scan_stmt_list_for_chains(
        tr, stmt.body, tparams=tparams, capture_params=capture_params, out=out,
      )
      for h in stmt.handlers:
        _scan_stmt_list_for_chains(
          tr, h.body, tparams=tparams, capture_params=capture_params, out=out,
        )
      _scan_stmt_list_for_chains(
        tr, stmt.orelse, tparams=tparams, capture_params=capture_params, out=out,
      )
      _scan_stmt_list_for_chains(
        tr, stmt.finalbody, tparams=tparams, capture_params=capture_params, out=out,
      )
    elif isinstance(stmt, ast.Match):
      for case in stmt.cases:
        _scan_stmt_list_for_chains(
          tr, case.body, tparams=tparams, capture_params=capture_params, out=out,
        )


def find_type_if_chains(
  tr: Translator,
  body: list[ast.stmt],
  *,
  tparams: set[str],
  capture_params: set[str] | None = None,
) -> list[TypeIfChain]:
  cap = capture_params or set()
  chains: list[TypeIfChain] = []
  _scan_stmt_list_for_chains(
    tr, _strip_docstring(body), tparams=tparams, capture_params=cap, out=chains,
  )
  return chains


def _stmt_list_contains_type_if_head(
  stmts: list[ast.stmt],
  *,
  tparams: set[str],
  capture_params: set[str] | None = None,
) -> bool:
  cap = capture_params or set()
  call_tparams = _call_type_params(tparams, cap)
  for stmt in stmts:
    if isinstance(stmt, ast.If):
      if _looks_like_type_if_head(stmt.test, call_tparams, capture_params=cap):
        return True
      if _stmt_list_contains_type_if_head(
        stmt.body, tparams=tparams, capture_params=cap,
      ):
        return True
      if _stmt_list_contains_type_if_head(
        stmt.orelse, tparams=tparams, capture_params=cap,
      ):
        return True
    elif isinstance(stmt, (ast.For, ast.While, ast.With)):
      if _stmt_list_contains_type_if_head(
        stmt.body, tparams=tparams, capture_params=cap,
      ):
        return True
      if _stmt_list_contains_type_if_head(
        stmt.orelse, tparams=tparams, capture_params=cap,
      ):
        return True
    elif isinstance(stmt, (ast.Try, ast.TryStar)):
      if _stmt_list_contains_type_if_head(
        stmt.body, tparams=tparams, capture_params=cap,
      ):
        return True
      for h in stmt.handlers:
        if _stmt_list_contains_type_if_head(
          h.body, tparams=tparams, capture_params=cap,
        ):
          return True
      if _stmt_list_contains_type_if_head(
        stmt.orelse, tparams=tparams, capture_params=cap,
      ):
        return True
      if _stmt_list_contains_type_if_head(
        stmt.finalbody, tparams=tparams, capture_params=cap,
      ):
        return True
    elif isinstance(stmt, ast.Match):
      for case in stmt.cases:
        if _stmt_list_contains_type_if_head(
          case.body, tparams=tparams, capture_params=cap,
        ):
          return True
  return False


def _validate_single_type_if_chain(
  chain: TypeIfChain,
  *,
  tparams: set[str],
  capture_params: set[str] | None = None,
) -> None:
  cap = capture_params or set()
  for br in chain.branches:
    if _stmt_list_contains_type_if_head(br.body, tparams=tparams, capture_params=cap):
      raise ValueError(
        "暂不支持类型 if 链嵌套：请勿在类型 if 分支体内再写类型 if/elif 链，"
        "多路分派请合并为一条 if/elif/else"
      )
  if chain.else_body and _stmt_list_contains_type_if_head(
    chain.else_body, tparams=tparams, capture_params=cap,
  ):
    raise ValueError(
      "暂不支持类型 if 链嵌套：请勿在类型 if 的 else 内再写类型 if/elif 链，"
      "多路分派请合并为一条 if/elif/else"
    )


def parse_type_if_chain_from_body(
  tr: Translator,
  body: list[ast.stmt],
  *,
  tparams: set[str],
) -> TypeIfChain | None:
  chains = find_type_if_chains(tr, body, tparams=tparams)
  return chains[0] if chains else None


def _validate_chain(chain: TypeIfChain) -> None:
  seen_exact: set[str] = set()
  seen_wildcard: set[tuple[str, int]] = set()
  for i, br in enumerate(chain.branches):
    if _branch_is_not(br):
      if i > 0:
        raise ValueError(
          "``T is not …`` 仅支持作为首分支，或与 ``else`` 配对"
        )
      if chain.else_body is None:
        raise ValueError("``T is not …`` 作为首分支时须配合 ``else``")
    if _branch_not_in(br):
      c = br.or_groups[0][0]
      for pat in c.patterns:
        if pat.extra_template_params:
          raise ValueError(
            "``T not in {…}`` 元素须为具体类型，不支持 ``...`` 类型模式"
          )
    for group in br.or_groups:
      for c in group:
        if c.kind == "in" and c.param == chain.type_param:
          for pat in c.patterns:
            if pat.extra_template_params:
              raise ValueError(
                "``T in […]`` 元素须为具体类型，不支持 ``...`` 类型模式"
              )
    for pat in branch_emit_patterns(br, chain.type_param):
      if pat.extra_template_params:
        base, args = _split_cpp_template(pat.cpp_type)
        key = (base, len(args))
        if key in seen_wildcard:
          raise ValueError(f"类型 if 分支重复: {pat.cpp_type}")
        seen_wildcard.add(key)
        continue
      if pat.cpp_type in seen_exact:
        raise ValueError(f"类型 if 分支重复: {pat.cpp_type}")
      seen_exact.add(pat.cpp_type)


def _collect_used_captures_in_chain(
  chain: TypeIfChain,
  *,
  capture_params: set[str],
) -> set[str]:
  used: set[str] = set()
  for br in chain.branches:
    for group in br.or_groups:
      for c in group:
        if c.param in capture_params:
          used.add(c.param)
        for pat in c.patterns:
          used.update(pat.extra_template_params)
  return used


def _expand_and_group(
  clauses: list[TypeIfClause],
  chain_type_param: str,
) -> list[TypePattern]:
  """单条 ``and`` 组展开为 C++ 特化模式。"""
  if len(clauses) == 1:
    c = clauses[0]
    if c.kind == "is":
      return [c.patterns[0]]
    if c.kind == "in":
      return list(c.patterns)
    return []
  capture_constraints: dict[str, list[str]] = {}
  primary_patterns: list[TypePattern] = []
  defer_expand = False
  for c in clauses:
    if c.param == chain_type_param:
      if c.kind == "is":
        primary_patterns.append(c.patterns[0])
      elif c.kind == "in":
        primary_patterns.extend(c.patterns)
      else:
        raise ValueError("``and`` 组合不支持主形参 ``is not`` / ``not in``")
    else:
      if c.kind == "is":
        capture_constraints.setdefault(c.param, []).append(c.patterns[0].cpp_type)
      elif c.kind == "in":
        capture_constraints.setdefault(c.param, []).extend(
          p.cpp_type for p in c.patterns
        )
      else:
        defer_expand = True
  if not primary_patterns:
    raise ValueError("``and`` 组合须包含对主形参 ``T is …`` / ``T in …``")
  if defer_expand and not capture_constraints:
    return primary_patterns
  from itertools import product

  out: list[TypePattern] = []
  cap_names = sorted(capture_constraints.keys())
  cap_lists = [capture_constraints[n] for n in cap_names]
  for primary in primary_patterns:
    caps = set(primary.extra_template_params)
    if not caps and not capture_constraints:
      out.append(primary)
      continue
    if not capture_constraints:
      out.append(primary)
      continue
    missing = caps - set(capture_constraints.keys())
    if missing and not defer_expand:
      names = ", ".join(sorted(missing))
      raise ValueError(
        f"捕获形参 {names} 须在 ``and`` 后续子句中用 ``in […]`` / ``is …`` 约束"
      )
    if missing and defer_expand:
      out.append(primary)
      continue
    combos = product(*cap_lists) if cap_lists else [()]
    for combo in combos:
      subst = dict(zip(cap_names, combo))
      cpp = primary.cpp_type
      for name, val in subst.items():
        cpp = _substitute_capture_in_cpp(cpp, {name: val})
      out.append(TypePattern(cpp, ()))
  return out


def branch_emit_patterns(br: TypeIfBranch, chain_type_param: str) -> list[TypePattern]:
  """分支对应的 C++ 特化模式（``or`` 各选支 ``and`` 展开后去重）。"""
  if _branch_is_not(br) or _branch_not_in(br):
    return []
  seen: set[tuple[str, tuple[str, ...]]] = set()
  out: list[TypePattern] = []
  for group in br.or_groups:
    for pat in _expand_and_group(group, chain_type_param):
      key = (pat.cpp_type, pat.extra_template_params)
      if key in seen:
        continue
      seen.add(key)
      out.append(pat)
  return out


def _apply_type_if_clause(
  bindings: dict[str, str],
  clause: TypeIfClause,
) -> dict[str, str] | None:
  from ..analysis.type_extract import try_match_pattern

  val = bindings.get(clause.param)
  if val is None:
    return None
  match clause.kind:
    case "is":
      new_binds = try_match_pattern(val, clause.patterns[0])
      if new_binds is None:
        return None
      merged = dict(bindings)
      for k, v in new_binds.items():
        if k in merged and merged[k] != v:
          return None
        merged[k] = v
      return merged
    case "in":
      if not any(_type_matches_pattern(val, p) for p in clause.patterns):
        return None
      return bindings
    case "is_not":
      if _type_matches_pattern(val, clause.patterns[0]):
        return None
      return bindings
    case "not_in":
      if any(_type_matches_pattern(val, p) for p in clause.patterns):
        return None
      return bindings
  return None


def _group_matches_concrete(
  group: list[TypeIfClause],
  concrete: str,
  *,
  chain_type_param: str,
) -> bool:
  bindings: dict[str, str] = {chain_type_param: concrete}
  for clause in group:
    next_bindings = _apply_type_if_clause(bindings, clause)
    if next_bindings is None:
      return False
    bindings = next_bindings
  return True


def _group_exact_match(
  group: list[TypeIfClause],
  concrete: str,
  *,
  chain_type_param: str,
) -> bool:
  if len(group) != 1:
    return False
  c = group[0]
  match c.kind:
    case "is":
      pat = c.patterns[0]
      return not pat.extra_template_params and pat.cpp_type == concrete
    case "in":
      return any(
        not p.extra_template_params and p.cpp_type == concrete for p in c.patterns
      )
    case _:
      return False


def _branch_exact_match(
  br: TypeIfBranch,
  concrete: str,
  *,
  chain_type_param: str,
) -> bool:
  return any(
    _group_exact_match(group, concrete, chain_type_param=chain_type_param)
    for group in br.or_groups
  )


def _branch_matches_concrete(
  br: TypeIfBranch,
  concrete: str,
  *,
  chain_type_param: str,
) -> bool:
  return any(
    _group_matches_concrete(group, concrete, chain_type_param=chain_type_param)
    for group in br.or_groups
  )


def _select_body_for_concrete(chain: TypeIfChain, concrete: str) -> list[ast.stmt]:
  tp = chain.type_param
  for br in chain.branches:
    if _branch_exact_match(br, concrete, chain_type_param=tp):
      return list(br.body)
  for br in chain.branches:
    if _branch_matches_concrete(br, concrete, chain_type_param=tp):
      return list(br.body)
  if chain.else_body is not None:
    return list(chain.else_body)
  return []


def _select_body_for_spec(chain: TypeIfChain, spec: _SpliceSpec) -> list[ast.stmt]:
  match spec:
    case _ExactSpec(cpp_type=cpp_type):
      return _select_body_for_concrete(chain, cpp_type)
    case _PatternSpec(pattern=pat):
      for br in chain.branches:
        single = _branch_single_is(br)
        if single is not None and single.patterns[0] == pat:
          return list(br.body)
        single_in = _branch_single_in(br)
        if single_in is not None and pat in single_in.patterns:
          return list(br.body)
        for ep in branch_emit_patterns(br, chain.type_param):
          if ep.cpp_type == pat.cpp_type and ep.extra_template_params == pat.extra_template_params:
            return list(br.body)
      if chain.else_body is not None:
        return list(chain.else_body)
      return []
    case _IsNotEnableIfSpec(excluded=excluded):
      if (
        chain.branches
        and _branch_is_not(chain.branches[0])
        and chain.branches[0].or_groups[0][0].patterns[0].cpp_type == excluded
      ):
        return list(chain.branches[0].body)
      if chain.else_body is not None:
        return list(chain.else_body)
      return []
    case _NotInEnableIfSpec(patterns=patterns):
      for br in chain.branches:
        if _branch_not_in(br) and br.or_groups[0][0].patterns == patterns:
          return list(br.body)
      excluded = {p.cpp_type for p in patterns}
      for br in chain.branches:
        single = _branch_single_is(br)
        if single is not None and single.patterns[0].cpp_type in excluded:
          continue
        single_in = _branch_single_in(br)
        if single_in is not None and all(p.cpp_type in excluded for p in single_in.patterns):
          continue
      if chain.else_body is not None:
        return list(chain.else_body)
      return []
    case _DefaultElseSpec():
      if chain.else_body is not None:
        return list(chain.else_body)
      return []
  return []


def _func_template_params(func: ast.FunctionDef) -> set[str]:
  out: set[str] = set()
  for tp in getattr(func, "type_params", None) or ():
    if isinstance(tp, ast.TypeVar):
      out.add(tp.name)
  return out


def _dispatch_pick_name(func: ast.FunctionDef) -> str:
  from ..analysis.patterns import py2cpp_emit_symbol

  safe = "".join(c if c.isalnum() else "_" for c in func.name)
  return py2cpp_emit_symbol("type_if", safe, str(func.lineno), "pick")


def _type_if_instance_receiver(
  tr: Translator,
  func: ast.FunctionDef,
  sig: FunctionSig | MethodSig,
) -> tuple[str, str, str | None]:
  """返回静态分派 helper 所需的显式实例接收者。

  ``type if`` 的分支体会移入嵌套静态 helper，不能再引用外围成员函数的
  ``this``。实例方法因此将当前对象作为 ``self`` 指针传入；模块函数与
  静态方法保持原有无接收者调用约定。
  """
  if (
    not isinstance(sig, MethodSig)
    or sig.is_static
    or not func.args.args
    or func.args.args[0].arg != "self"
    or tr.class_info is None
  ):
    return "", "", None
  const_prefix = "const " if sig.is_const else ""
  return f"{const_prefix}{tr.class_info.cpp_specialization()}* self", "this", "self"


def _call_params(
  tr: Translator,
  func: ast.FunctionDef,
  sig: FunctionSig | MethodSig,
) -> tuple[str, str, str | None]:
  receiver_impl, receiver_call, receiver_cpp = _type_if_instance_receiver(
    tr, func, sig,
  )
  skip = frozenset({"self", "cls"})
  parts_impl: list[str] = []
  parts_call: list[str] = []
  if receiver_impl:
    parts_impl.append(receiver_impl)
    parts_call.append(receiver_call)
  for arg in func.args.args:
    if arg.arg in skip:
      continue
    pt = method_param_storage_cpp(sig, arg.arg)
    pname = cpp_param(arg.arg)
    parts_impl.append(f"{pt} {pname}")
    parts_call.append(pname)
  return ", ".join(parts_impl), ", ".join(parts_call), receiver_cpp


def _template_params_for(tr: Translator, func: ast.FunctionDef) -> set[str]:
  tparams = _func_template_params(func)
  if tr.class_info:
    tparams |= set(tr.class_info.type_params)
  return tparams


def _concrete_params_impl(
  func: ast.FunctionDef,
  sig: FunctionSig | MethodSig,
  type_param: str,
  concrete: str,
) -> str:
  skip = frozenset({"self", "cls"})
  parts: list[str] = []
  for arg in func.args.args:
    if arg.arg in skip:
      continue
    pt = method_param_storage_cpp(sig, arg.arg)
    if pt == type_param:
      pt = concrete
    parts.append(f"{pt} {cpp_param(arg.arg)}")
  return ", ".join(parts)


def _type_matches_pattern(concrete: str, pat: TypePattern) -> bool:
  if pat.pattern_node is not None:
    from ..analysis.type_compat import type_node_from_cpp_string
    from ..analysis.type_node import structural_match_type_nodes, type_nodes_equal

    conc_node = type_node_from_cpp_string(concrete)
    wild = frozenset(pat.wildcards_for_match())
    if pat.extra_template_params or wild:
      all_wild = wild | frozenset(pat.extra_template_params)
      return structural_match_type_nodes(
        conc_node, pat.pattern_node, all_wild,
      ) is not None
    return type_nodes_equal(conc_node, pat.pattern_node)
  if pat.extra_template_params:
    return _structural_type_match(
      concrete, pat.cpp_type, pat.extra_template_params,
    )
  return pat.cpp_type == concrete


def _substitute_chains_in_stmts(
  stmts: list[ast.stmt],
  chains_by_head: dict[int, TypeIfChain],
  spec: _SpliceSpec,
) -> list[ast.stmt]:
  out: list[ast.stmt] = []
  for stmt in stmts:
    if isinstance(stmt, ast.If) and id(stmt) in chains_by_head:
      chain = chains_by_head[id(stmt)]
      selected = _select_body_for_spec(chain, spec)
      out.extend(copy.deepcopy(selected))
      continue
    new_stmt = copy.deepcopy(stmt)
    if isinstance(new_stmt, ast.If):
      new_stmt.body = _substitute_chains_in_stmts(
        stmt.body, chains_by_head, spec,
      )
      new_stmt.orelse = _substitute_chains_in_stmts(
        stmt.orelse, chains_by_head, spec,
      )
    elif isinstance(new_stmt, (ast.For, ast.While, ast.With)):
      new_stmt.body = _substitute_chains_in_stmts(
        stmt.body, chains_by_head, spec,
      )
      new_stmt.orelse = _substitute_chains_in_stmts(
        stmt.orelse, chains_by_head, spec,
      )
    elif isinstance(new_stmt, (ast.Try, ast.TryStar)):
      new_stmt.body = _substitute_chains_in_stmts(
        stmt.body, chains_by_head, spec,
      )
      for orig_h, new_h in zip(stmt.handlers, new_stmt.handlers):
        new_h.body = _substitute_chains_in_stmts(
          orig_h.body, chains_by_head, spec,
        )
      new_stmt.orelse = _substitute_chains_in_stmts(
        stmt.orelse, chains_by_head, spec,
      )
      new_stmt.finalbody = _substitute_chains_in_stmts(
        stmt.finalbody, chains_by_head, spec,
      )
    elif isinstance(new_stmt, ast.Match):
      for orig_case, new_case in zip(stmt.cases, new_stmt.cases):
        new_case.body = _substitute_chains_in_stmts(
          orig_case.body, chains_by_head, spec,
        )
    out.append(new_stmt)
  return out


def _spliced_function_body(
  func: ast.FunctionDef,
  chains: tuple[TypeIfChain, ...],
  spec: _SpliceSpec,
) -> list[ast.stmt]:
  chains_by_head = {id(c.head): c for c in chains}
  return _substitute_chains_in_stmts(
    _strip_docstring(func.body), chains_by_head, spec,
  )


def _concrete_ret_for_spec(spec: _SpliceSpec, *, type_param: str) -> str | None:
  match spec:
    case _ExactSpec(cpp_type=cpp_type):
      return cpp_type
    case _PatternSpec(pattern=pat):
      return pat.cpp_type
    case _DefaultElseSpec():
      return type_param
    case _:
      return None


def _emit_call_body(
  tr: Translator,
  body: list[ast.stmt],
  *,
  extra_tparams: tuple[str, ...],
  type_param: str,
  concrete_bind: str | None = None,
  self_cpp: str | None = None,
) -> None:
  prev_extra = set(tr._type_if_extra_params)
  prev_bind = tr._type_if_concrete_bind
  prev_self = tr._type_if_self_cpp
  tr._type_if_extra_params |= set(extra_tparams)
  if concrete_bind is not None:
    tr._type_if_concrete_bind = (type_param, concrete_bind)
  tr._type_if_self_cpp = self_cpp
  try:
    tr._emit_body(body)
  finally:
    tr._type_if_extra_params = prev_extra
    tr._type_if_concrete_bind = prev_bind
    tr._type_if_self_cpp = prev_self


def _emit_struct_with_call(
  tr: Translator,
  header_lines: list[str],
  *,
  ret_lead: str,
  ret_trail: str,
  params_impl: str,
  body: list[ast.stmt],
  extra_tparams: tuple[str, ...],
  type_param: str,
  concrete_bind: str | None = None,
  self_cpp: str | None = None,
) -> None:
  for line in header_lines:
    tr.write_line(line)
  tr.write_line("{")
  if concrete_bind is not None and ret_lead == type_param:
    ret = concrete_bind
  else:
    ret = ret_lead
  sig = f"static {format_fn_sig(ret, ret_trail, _CALL_METHOD, params_impl)}"
  with tr._use_indent():
    with tr._use_block(sig):
      _emit_call_body(
        tr,
        body,
        extra_tparams=extra_tparams,
        type_param=type_param,
        concrete_bind=concrete_bind,
        self_cpp=self_cpp,
      )
  tr.write_line("};")
  tr.write_line()


def _emit_spliced_call(
  tr: Translator,
  plan: TypeIfFunctionPlan,
  sig: FunctionSig | MethodSig,
  *,
  header_lines: list[str],
  splice_spec: _SpliceSpec,
  params_impl: str,
  extra_tparams: tuple[str, ...] = (),
  self_cpp: str | None = None,
) -> None:
  body = _spliced_function_body(plan.func, plan.chains, splice_spec)
  type_param = plan.master_chain.type_param
  concrete_bind = _concrete_ret_for_spec(splice_spec, type_param=type_param)
  _emit_struct_with_call(
    tr,
    header_lines,
    ret_lead=sig_return_storage_cpp(sig),
    ret_trail=sig.ret_trail,
    params_impl=params_impl,
    body=body,
    extra_tparams=extra_tparams,
    type_param=type_param,
    concrete_bind=concrete_bind,
    self_cpp=self_cpp,
  )

def _emit_concrete_specialization(
  tr: Translator,
  pick: str,
  pat: TypePattern,
  *,
  plan: TypeIfFunctionPlan,
  sig: FunctionSig | MethodSig,
  params_impl: str,
  self_cpp: str | None = None,
) -> None:
  concrete_params = _concrete_params_impl(
    plan.func, sig, plan.master_chain.type_param, pat.cpp_type,
  )
  if self_cpp is not None:
    const_prefix = "const " if sig.is_const else ""
    receiver = f"{const_prefix}{tr.class_info.cpp_specialization()}* {self_cpp}"
    concrete_params = f"{receiver}, {concrete_params}" if concrete_params else receiver
  if pat.extra_template_params:
    tdecl = ", ".join(f"typename {p}" for p in pat.extra_template_params)
    header = [
      f"template<{tdecl}>",
      f"struct {pick}<{pat.cpp_type}, void>",
    ]
    splice_spec: _SpliceSpec = _PatternSpec(pat)
  else:
    header = [
      "template<>",
      f"struct {pick}<{pat.cpp_type}, void>",
    ]
    splice_spec = _ExactSpec(pat.cpp_type)
  _emit_spliced_call(
    tr,
    plan,
    sig,
    header_lines=header,
    splice_spec=splice_spec,
    params_impl=concrete_params,
    extra_tparams=pat.extra_template_params,
    self_cpp=self_cpp,
  )


def _emit_is_not_specialization(
  tr: Translator,
  pick: str,
  pat: TypePattern,
  *,
  plan: TypeIfFunctionPlan,
  sig: FunctionSig | MethodSig,
  params_impl: str,
  self_cpp: str | None = None,
) -> None:
  if pat.extra_template_params:
    raise ValueError("``T is not …`` 不支持形参化类型模式")
  tp = plan.master_chain.type_param
  cond = f"!std::is_same<{tp}, {pat.cpp_type}>::value"
  header = [
    f"template<typename {tp}>",
    f"struct {pick}<{tp}, typename std::enable_if<{cond}, void>::type>",
  ]
  _emit_spliced_call(
    tr,
    plan,
    sig,
    header_lines=header,
    splice_spec=_IsNotEnableIfSpec(pat.cpp_type),
    params_impl=params_impl,
    self_cpp=self_cpp,
  )


def _not_in_enable_if_cond(patterns: list[TypePattern], type_param: str) -> str:
  parts = [f"std::is_same<{type_param}, {p.cpp_type}>::value" for p in patterns]
  inner = " || ".join(parts)
  return f"!({inner})"


def _emit_not_in_specialization(
  tr: Translator,
  pick: str,
  patterns: list[TypePattern],
  *,
  plan: TypeIfFunctionPlan,
  sig: FunctionSig | MethodSig,
  params_impl: str,
  self_cpp: str | None = None,
) -> None:
  for pat in patterns:
    if pat.extra_template_params:
      raise ValueError("``T not in …`` 不支持形参化类型模式")
  tp = plan.master_chain.type_param
  cond = _not_in_enable_if_cond(patterns, tp)
  header = [
    f"template<typename {tp}>",
    f"struct {pick}<{tp}, typename std::enable_if<{cond}, void>::type>",
  ]
  _emit_spliced_call(
    tr,
    plan,
    sig,
    header_lines=header,
    splice_spec=_NotInEnableIfSpec(tuple(patterns)),
    params_impl=params_impl,
    self_cpp=self_cpp,
  )


def emit_type_if_dispatch(
  tr: Translator,
  plan: TypeIfFunctionPlan,
  sig: FunctionSig | MethodSig,
) -> str:
  chain = plan.master_chain
  _validate_chain(chain)
  allowed = _template_params_for(tr, plan.func)
  if chain.type_param not in allowed:
    raise ValueError(f"``{chain.type_param}`` 不是当前函数/类的泛型形参")
  for extra in plan.chains[1:]:
    if extra.type_param != chain.type_param:
      raise ValueError("同一函数内多条类型 if 链须使用相同泛型形参")
    _validate_chain(extra)

  pick = _dispatch_pick_name(plan.func)
  params_impl, _, self_cpp = _call_params(tr, plan.func, sig)
  tp = chain.type_param
  tr.write_line(f"template<typename {tp}, typename = void>")
  tr.write_line(f"struct {pick};")
  tr.write_line()
  for br in chain.branches:
    if _branch_is_not(br):
      _emit_is_not_specialization(
        tr,
        pick,
        br.or_groups[0][0].patterns[0],
        plan=plan,
        sig=sig,
        params_impl=params_impl,
        self_cpp=self_cpp,
      )
      continue
    if _branch_not_in(br):
      _emit_not_in_specialization(
        tr,
        pick,
        list(br.or_groups[0][0].patterns),
        plan=plan,
        sig=sig,
        params_impl=params_impl,
        self_cpp=self_cpp,
      )
      continue
    for pat in branch_emit_patterns(br, chain.type_param):
      _emit_concrete_specialization(
        tr,
        pick,
        pat,
        plan=plan,
        sig=sig,
        params_impl=params_impl,
        self_cpp=self_cpp,
      )
  header = [
    f"template<typename {tp}>",
    f"struct {pick}<{tp}, void>",
  ]
  if chain.else_body is not None:
    if len(chain.branches) == 1 and _branch_is_not(chain.branches[0]):
      _emit_concrete_specialization(
        tr,
        pick,
        chain.branches[0].or_groups[0][0].patterns[0],
        plan=plan,
        sig=sig,
        params_impl=params_impl,
        self_cpp=self_cpp,
      )
    elif len(chain.branches) == 1 and _branch_not_in(chain.branches[0]):
      for pat in chain.branches[0].or_groups[0][0].patterns:
        _emit_concrete_specialization(
          tr,
          pick,
          pat,
          plan=plan,
          sig=sig,
          params_impl=params_impl,
          self_cpp=self_cpp,
        )
    else:
      _emit_spliced_call(
        tr,
        plan,
        sig,
        header_lines=header,
        splice_spec=_DefaultElseSpec(),
        params_impl=params_impl,
        self_cpp=self_cpp,
      )
  else:
    for line in header:
      tr.write_line(line)
    tr.write_line("{")
    sig_call = (
      f"static {format_fn_sig(sig_return_storage_cpp(sig), sig.ret_trail, _CALL_METHOD, params_impl)}"
    )
    with tr._use_indent():
      with tr._use_block(sig_call):
        tr.write_line(
          f'static_assert(sizeof({tp}) == 0, "类型 if 未覆盖该 {tp} 且无 else 分支");'
        )
    tr.write_line("};")
    tr.write_line()
  return pick


def validate_function_type_args(
  func: ast.FunctionDef,
  slice_node: ast.expr,
) -> None:
  """禁止显式传入 ``_U = …`` 捕获形参。"""
  capture = _func_capture_params(func)
  if not capture:
    return
  from ..analysis.analyzer import TypeParser

  ordered = _ordered_type_param_names(func)
  nodes = TypeParser._slice_type_arg_nodes(slice_node)
  for param, _node in zip(ordered, nodes):
    if param in capture:
      raise ValueError(
        f"{func.name}[…]: 不得显式传入捕获形参 ``{param}``"
      )


def plan_type_if_chain(
  tr: Translator,
  func: ast.FunctionDef,
) -> TypeIfFunctionPlan | None:
  tparams = _template_params_for(tr, func)
  capture = _func_capture_params(func)
  if tr.class_info:
    capture |= set(tr.class_info.capture_params)
  if not tparams or is_stub_function_body(func.body):
    return None
  validate_capture_param_names(tuple(capture), loc=f"def {func.name}")
  chains = find_type_if_chains(
    tr, func.body, tparams=tparams, capture_params=capture,
  )
  if not chains:
    return None
  if len(chains) > 1:
    raise ValueError(
      "暂不支持同一函数内多条类型 if 链（平行）；"
      "多路分派请合并为一条 if/elif/else"
    )
  _validate_single_type_if_chain(
    chains[0], tparams=tparams, capture_params=capture,
  )
  used_caps = _collect_used_captures_in_chain(chains[0], capture_params=capture)
  for cap in capture:
    if cap not in used_caps:
      raise ValueError(
        f"def {func.name}: 捕获形参 ``{cap}`` 须在 type if 条件中出现"
      )
  return TypeIfFunctionPlan(chains[0], (chains[0],), func)


def emit_type_if_return(
  tr: Translator,
  func: ast.FunctionDef,
  sig: FunctionSig | MethodSig,
  plan: TypeIfFunctionPlan,
  pick: str,
) -> None:
  _, call_args, _ = _call_params(tr, func, sig)
  tp = plan.master_chain.type_param
  prologue = _prologue_stmts_before_type_if(func, plan.master_chain.head)
  if prologue:
    tr._emit_body(prologue)
  if call_args:
    tr.write_line(f"return {pick}<{tp}, void>::{_CALL_METHOD}({call_args});")
  else:
    tr.write_line(f"return {pick}<{tp}, void>::{_CALL_METHOD}();")
