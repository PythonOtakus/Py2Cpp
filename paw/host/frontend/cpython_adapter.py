"""CPython AST → SyntaxModule（legacy 单向入口；不得反向同步）。

完整声明重建在后续迭代补齐；当前按顶层语句切分为 Import / Function / Opaque，
使 Binder 与 MidIR 管道与 `.paw` 共用。
"""
from __future__ import annotations

import ast

from compiler.py.frontend.source import FileId, Span
from compiler.py.frontend.syntax_nodes import (
  FunctionDecl,
  ImportStmt,
  OpaqueStmt,
  SyntaxModule,
)


def from_cpython(
  tree: ast.Module,
  source: str,
  *,
  file_id: FileId,
) -> SyntaxModule:
  if not tree.body:
    return SyntaxModule(items=[], span=Span(file_id, 0, len(source)))

  lines = source.splitlines(keepends=True)
  items: list = []

  def span_for(node: ast.AST) -> Span:
    lineno = getattr(node, "lineno", 1) or 1
    end_lineno = getattr(node, "end_lineno", lineno) or lineno
    col = getattr(node, "col_offset", 0) or 0
    end_col = getattr(node, "end_col_offset", col) or col
    start = _offset(lines, lineno, col)
    end = _offset(lines, end_lineno, end_col)
    return Span(file_id, start, max(end, start))

  def source_for(node: ast.AST) -> str:
    sp = span_for(node)
    return source[sp.start : sp.end]

  for node in tree.body:
    sp = span_for(node)
    src = source_for(node)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
      items.append(ImportStmt(source=src, span=sp))
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
      deco = ""
      if node.decorator_list:
        d0 = span_for(node.decorator_list[0]).start
        # 装饰器到 def 之前
        def_line = node.lineno
        deco = source[_offset(lines, node.decorator_list[0].lineno, 0) : _offset(lines, def_line, 0)]
      params = ast.unparse(node.args) if hasattr(ast, "unparse") else ""
      ret = ast.unparse(node.returns) if node.returns is not None else None
      # body：从 suite 第一行到结束
      if node.body:
        b0 = span_for(node.body[0]).start
        body_src = source[b0:sp.end]
      else:
        body_src = "pass"
      items.append(
        FunctionDecl(
          name=node.name,
          decorators_source=deco,
          params_source=params,
          return_source=ret,
          body_source=body_src,
          is_async=isinstance(node, ast.AsyncFunctionDef),
          span=sp,
        )
      )
    else:
      items.append(OpaqueStmt(source=src, span=sp))

  start = items[0].span.start if items else 0
  end = items[-1].span.end if items else len(source)
  return SyntaxModule(
    items=items,
    span=Span(file_id, start, end),
  )


def _offset(lines: list[str], lineno: int, col: int) -> int:
  if lineno < 1:
    return 0
  off = 0
  for i, line in enumerate(lines, start=1):
    if i == lineno:
      return off + min(col, len(line))
    off += len(line)
  return off
