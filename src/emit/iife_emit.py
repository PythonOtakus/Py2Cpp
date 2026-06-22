"""``[&]() -> T { … }()`` 表达式格式化（Allman 换行 + 缩进）。"""
from __future__ import annotations

import re


def emit_iife(ret_type: str | None, stmts: list[str]) -> str:
  """将语句列表格式化为立即调用的 lambda 表达式（Allman；``{``/``}`` 与 ``[&]()`` 行同级缩进）。"""
  body = format_block_body(stmts, indent="  ")
  sig = f"[&]() -> {ret_type}" if ret_type else "[&]()"
  return f"({sig}\n{{\n{body}\n}})()"


def format_block_body(stmts: list[str], *, indent: str = "") -> str:
  """格式化语句块（用于 IIFE 体或其它内联块）。"""
  lines: list[str] = []
  for stmt in stmts:
    lines.extend(_format_statement(stmt, indent))
  return "\n".join(lines)


def _format_statement(stmt: str, indent: str) -> list[str]:
  s = stmt.strip()
  if not s:
    return []
  open_idx = s.find("{")
  if open_idx >= 0:
    header = s[:open_idx].rstrip()
    if _header_allows_brace_block(header) and not re.search(r"=\s*\{", header):
      matched = _match_brace_block(s, open_idx)
      if matched is not None:
        inner, close_idx = matched
        lines = [f"{indent}{header}", f"{indent}{{"]
        inner_indent = indent + "  "
        for part in _split_top_level_semicolons(inner):
          lines.extend(_format_statement(part, inner_indent))
        lines.append(f"{indent}}}")
        rest = s[close_idx + 1 :].strip()
        if rest:
          lines.extend(_format_statement(rest, indent))
        return lines
  if "\n" in s:
    lines = s.split("\n")
    last = lines[-1].rstrip()
    if last and not last.endswith(";"):
      lines[-1] = f"{last};"
    return [f"{indent}{ln}" for ln in lines]
  if not s.endswith(";"):
    s = f"{s};"
  return [f"{indent}{s}"]


def _header_allows_brace_block(header: str) -> bool:
  if "[&]()" in header:
    return False
  return bool(
    re.search(r"\bfor\s*\(", header)
    or re.search(r"\b(if|while)\s*\(", header)
    or re.search(r"\belse\s*$", header)
  )


def _match_brace_block(text: str, open_idx: int) -> tuple[str, int] | None:
  depth = 0
  for i in range(open_idx, len(text)):
    ch = text[i]
    if ch == "{":
      depth += 1
    elif ch == "}":
      depth -= 1
      if depth == 0:
        return text[open_idx + 1 : i], i
  return None


def _split_top_level_semicolons(text: str) -> list[str]:
  """按顶层 ``;`` 切分；忽略 ``for``/``if`` 条件及嵌套块内的分号。"""
  parts: list[str] = []
  brace = paren = 0
  start = 0
  for i, ch in enumerate(text):
    if ch == "{":
      brace += 1
    elif ch == "}":
      brace -= 1
    elif ch == "(":
      paren += 1
    elif ch == ")":
      paren -= 1
    elif ch == ";" and brace == 0 and paren == 0:
      part = text[start:i].strip()
      if part:
        parts.append(part)
      start = i + 1
  tail = text[start:].strip()
  if tail:
    parts.append(tail)
  return parts
