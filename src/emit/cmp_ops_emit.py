"""由 ``__cmp__`` 生成 C++ 六个比较运算符（返回 ``PyInt``：负/零/正）。"""
from __future__ import annotations

from ..analysis.ir import cpp_ident


def emit_cmp_operator_overloads(cpp: str, *, has_eq: bool = False, indent: str = "  ") -> list[str]:
  """``__cmp__(other)`` → ``operator==`` … ``operator>=``；若另有 ``__eq__``，``==``/``!=`` 走 ``__eq__``。"""
  other = f"const {cpp}& other"
  pi = cpp_ident("int")
  lines: list[str] = []
  for op, test in (
    ("==", "== 0"),
    ("!=", "!= 0"),
    ("<", "< 0"),
    ("<=", "<= 0"),
    (">", "> 0"),
    (">=", ">= 0"),
  ):
    if has_eq and op in ("==", "!="):
      lines.append(f"bool operator{op}({other}) const")
      lines.append("{")
      if op == "==":
        lines.append(f"{indent}return __eq__(other);")
      else:
        lines.append(f"{indent}return !__eq__(other);")
      lines.append("}")
      continue
    lines.append(f"bool operator{op}({other}) const")
    lines.append("{")
    lines.append(f"{indent}{pi} c = __cmp__(other);")
    lines.append(f"{indent}return (c {test});")
    lines.append("}")
  return lines
