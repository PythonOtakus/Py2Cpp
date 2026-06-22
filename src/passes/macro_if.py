"""``if "…" in __macro__`` / ``elif "…" not in __macro__`` → C 预编译指令。"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..translator import Translator

_MACRO_PROBE_NAME = "__macro__"
_MACRO_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class MacroIfBranch:
  macro: str
  positive: bool
  body: tuple[ast.stmt, ...]


@dataclass(frozen=True)
class MacroIfChain:
  branches: tuple[MacroIfBranch, ...]
  else_body: tuple[ast.stmt, ...] | None


def _macro_name_from_literal(left: ast.expr, *, loc: str) -> str:
  if not isinstance(left, ast.Constant) or not isinstance(left.value, str):
    raise ValueError(f"{loc}: __macro__ 检测左侧须为编译期字符串字面量")
  name = left.value
  if not _MACRO_NAME_RE.match(name):
    raise ValueError(f"{loc}: 无效的预编译宏名 {name!r}")
  return name


def _parse_macro_membership_compare(
  node: ast.Compare,
  *,
  loc: str,
) -> tuple[str, bool] | None:
  if len(node.ops) != 1 or len(node.comparators) != 1:
    return None
  op = node.ops[0]
  if isinstance(op, ast.In):
    positive = True
  elif isinstance(op, ast.NotIn):
    positive = False
  else:
    return None
  comp = node.comparators[0]
  if not (isinstance(comp, ast.Name) and comp.id == _MACRO_PROBE_NAME):
    return None
  name = _macro_name_from_literal(node.left, loc=loc)
  return name, positive


def parse_macro_if_test(test: ast.expr, *, loc: str = "") -> tuple[str, bool] | None:
  """``"X" in __macro__`` / ``"X" not in __macro__`` → ``(macro, positive)``；否则 ``None``。"""
  if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
    if isinstance(test.operand, ast.Compare):
      inner = _parse_macro_membership_compare(test.operand, loc=loc)
      if inner is not None and isinstance(test.operand.ops[0], ast.In):
        raise ValueError(
          f'{loc}: 不支持 `not "NAME" in __macro__`，请写 `"NAME" not in __macro__`',
        )
    return None
  if isinstance(test, ast.Compare):
    return _parse_macro_membership_compare(test, loc=loc)
  return None


def looks_like_macro_if_head(test: ast.expr) -> bool:
  if isinstance(test, ast.Compare):
    return _parse_macro_membership_compare(test, loc="") is not None
  if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
    if isinstance(test.operand, ast.Compare):
      return _parse_macro_membership_compare(test.operand, loc="") is not None
  return False


def collect_macro_if_chain(node: ast.If) -> MacroIfChain:
  """自 ``if "…" in __macro__`` 起收集整条 ``elif``/``else`` 链。"""
  loc = f"line {getattr(node, 'lineno', '?')}"
  first = parse_macro_if_test(node.test, loc=loc)
  if first is None:
    raise ValueError(f'{loc}: 非 `"NAME" in __macro__` 条件')
  macro, positive = first
  branches: list[MacroIfBranch] = [
    MacroIfBranch(macro, positive, tuple(node.body)),
  ]
  cur = node
  while cur.orelse:
    if len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
      elif_node = cur.orelse[0]
      eloc = f"line {getattr(elif_node, 'lineno', '?')}"
      parsed = parse_macro_if_test(elif_node.test, loc=eloc)
      if parsed is None:
        raise ValueError(
          f'{eloc}: macro if 链的 elif 须为 `"NAME" in __macro__` / `not in`，'
          "普通条件请改用独立 if 或放在分支体内",
        )
      macro, positive = parsed
      branches.append(MacroIfBranch(macro, positive, tuple(elif_node.body)))
      cur = elif_node
      continue
    return MacroIfChain(tuple(branches), tuple(cur.orelse))
  return MacroIfChain(tuple(branches), None)


def _emit_directive(tr: Translator, branch: MacroIfBranch, *, first: bool) -> None:
  if first:
    if branch.positive:
      tr.write_line(f"#ifdef {branch.macro}")
    else:
      tr.write_line(f"#ifndef {branch.macro}")
    return
  if branch.positive:
    tr.write_line(f"#elif defined({branch.macro})")
  else:
    tr.write_line(f"#elif !defined({branch.macro})")


def emit_macro_if_chain(tr: Translator, chain: MacroIfChain) -> None:
  for i, br in enumerate(chain.branches):
    _emit_directive(tr, br, first=(i == 0))
    tr._emit_body(list(br.body))
  if chain.else_body is not None:
    tr.write_line("#else")
    tr._emit_body(list(chain.else_body))
  tr.write_line("#endif")
