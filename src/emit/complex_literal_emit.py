"""``1.25j`` / ``3+4j`` 等复数字面量 → ``PyComplex`` 构造。"""
from __future__ import annotations

import ast

from ..analysis.type_pred import is_complex_type
from ..analysis.ir import format_cpp_complex_literal


def complex_literal_parts(node: ast.expr) -> tuple[float, float] | None:
  """将 AST 中的复数字面量解析为 (real, imag)；非字面量组合返回 ``None``。"""
  if isinstance(node, ast.Constant) and isinstance(node.value, complex):
    c = node.value
    return (float(c.real), float(c.imag))
  if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
    inner = complex_literal_parts(node.operand)
    if inner is None:
      return None
    return (-inner[0], -inner[1])
  if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
    return complex_literal_parts(node.operand)
  if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
    left = complex_literal_parts(node.left)
    right = complex_literal_parts(node.right)
    if left is not None and right is not None:
      if isinstance(node.op, ast.Add):
        return (left[0] + right[0], left[1] + right[1])
      return (left[0] - right[0], left[1] - right[1])
    if isinstance(node.op, ast.Add):
      if isinstance(node.left, ast.UnaryOp) and isinstance(node.left.op, ast.USub):
        if isinstance(node.left.operand, ast.Constant) and isinstance(
          node.left.operand.value, (int, float)
        ):
          rv = complex_literal_parts(node.right)
          if rv is not None:
            return (-float(node.left.operand.value) + rv[0], rv[1])
      if isinstance(node.left, ast.Constant) and isinstance(node.left.value, (int, float)):
        rv = complex_literal_parts(node.right)
        if rv is not None:
          return (float(node.left.value) + rv[0], rv[1])
      if isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float)):
        lv = complex_literal_parts(node.left)
        if lv is not None:
          return (lv[0] + float(node.right.value), lv[1])
    if isinstance(node.op, ast.Sub):
      if isinstance(node.left, ast.Constant) and isinstance(node.left.value, (int, float)):
        rv = complex_literal_parts(node.right)
        if rv is not None:
          return (float(node.left.value) - rv[0], -rv[1])
  return None


def try_emit_complex_literal_expr(
  node: ast.expr,
  cpp_type: str | None,
) -> str | None:
  if cpp_type is not None and not is_complex_type(cpp_type):
    return None
  parts = complex_literal_parts(node)
  if parts is None:
    return None
  return format_cpp_complex_literal(parts[0], parts[1], cpp_type)
