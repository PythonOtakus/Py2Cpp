"""模板冻结子集（1A/2A）：生产展开只允许名称 / 字面量 / 简单算术 / range / if / 模板内 def。

越界须诊断；禁止依赖 CPython AST 解析 / eval / exec 解释任意表达式。
"""
from __future__ import annotations

import re

# 标识符、字面量、简单二元/比较、括号、逗号（range 实参）
_SAFE_EXPR_RE = re.compile(
  r"""^[\sA-Za-z0-9_."'\+\-\*/%<>=!&|(),]+$"""
)
_ATTR_RE = re.compile(r"\.[A-Za-z_]")
_IMPORT_RE = re.compile(r"\b(?:import|from)\b")
_COMPREHENSION_RE = re.compile(r"\bfor\b.+\bin\b")
_LAMBDA_RE = re.compile(r"\blambda\b")
_EXEC_CALL_RE = re.compile(
  r"^([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$",
  re.DOTALL,
)
_FOR_HEADER_RE = re.compile(
  r"^for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+)$",
)
_IF_HEADER_RE = re.compile(r"^(?:if|elif)\s+(.+)$")
_DEF_HEADER_RE = re.compile(
  r"^def\s+(fn_[A-Za-z0-9_]+)\s*\(([^)]*)\)\s*$",
)


class TemplateProfileError(ValueError):
  """模板子集越界。"""


def assert_safe_expr(expr: str, *, where: str) -> None:
  text = expr.strip()
  if not text:
    return
  if _IMPORT_RE.search(text) or _LAMBDA_RE.search(text):
    raise TemplateProfileError(f"模板子集禁止 import/lambda：{where}: {expr}")
  if _ATTR_RE.search(text) and not (
    text.startswith('"') or text.startswith("'")
  ):
    # 允许字符串字面量内的点；裸属性访问禁止
    if '"' not in text and "'" not in text:
      raise TemplateProfileError(f"模板子集禁止属性访问：{where}: {expr}")
  # 列表推导：`[` … `for` …
  if "[" in text and _COMPREHENSION_RE.search(text):
    raise TemplateProfileError(f"模板子集禁止推导式：{where}: {expr}")
  if not _SAFE_EXPR_RE.match(text):
    raise TemplateProfileError(f"模板子集不允许的表达式字符：{where}: {expr}")


def assert_safe_begin_header(header: str, *, where: str) -> None:
  text = header.strip().rstrip(":")
  if text in ("else",):
    return
  if text.startswith("def "):
    if not _DEF_HEADER_RE.match(text):
      raise TemplateProfileError(
        f"BEGIN(def) 须为 def fn_Name(in_Args…)：{where}: {header}"
      )
    return
  if text.startswith("for "):
    m = _FOR_HEADER_RE.match(text)
    if not m:
      raise TemplateProfileError(f"BEGIN(for) 仅单变量：{where}: {header}")
    assert_safe_expr(m.group(2), where=where)
    return
  if text.startswith("if ") or text.startswith("elif "):
    m = _IF_HEADER_RE.match(text)
    if not m:
      raise TemplateProfileError(f"BEGIN(if) 无法解析：{where}: {header}")
    assert_safe_expr(m.group(1), where=where)
    return
  raise TemplateProfileError(f"BEGIN 头不在冻结子集内：{where}: {header}")


def assert_safe_exec(stmt: str, *, where: str) -> None:
  text = stmt.strip()
  # 赋值 MARKER = 42
  if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=\s*.+$", text) and not text.startswith(
    "if "
  ):
    _, _, rhs = text.partition("=")
    assert_safe_expr(rhs, where=where)
    return
  # if k == 0: __py2cpp_echo('…')  — showcase 内嵌
  m_if = re.match(
    r"^if\s+(.+?)\s*:\s*__py2cpp_echo\((.+)\)\s*$",
    text,
  )
  if m_if:
    assert_safe_expr(m_if.group(1), where=where)
    arg = m_if.group(2).strip()
    if (arg.startswith("'") and arg.endswith("'")) or (
      arg.startswith('"') and arg.endswith('"')
    ):
      return
    assert_safe_expr(arg, where=where)
    return
  m = _EXEC_CALL_RE.match(text)
  if m:
    assert_safe_expr(m.group(2) or "0", where=where)
    return
  raise TemplateProfileError(f"EXEC 不在冻结子集内：{where}: {stmt}")


def parse_def_header(header: str) -> tuple[str, list[str]]:
  text = header.strip().rstrip(":")
  m = _DEF_HEADER_RE.match(text)
  if not m:
    raise TemplateProfileError(f"PY2CPP_BEGIN(def) 非法: {header}")
  name = m.group(1)
  args_raw = m.group(2).strip()
  if not args_raw:
    return name, []
  args = [a.strip() for a in args_raw.split(",") if a.strip()]
  for a in args:
    if not re.match(r"^in_[A-Za-z0-9_]+$", a):
      raise TemplateProfileError(f"BEGIN(def) 形参须 in_PascalCase：{a}")
  return name, args


def parse_for_header(header: str) -> tuple[str, str]:
  text = header.strip().rstrip(":")
  m = _FOR_HEADER_RE.match(text)
  if not m:
    raise TemplateProfileError(f"PY2CPP_BEGIN 非 for: {header}")
  return m.group(1), m.group(2).strip()


def parse_if_test(header: str) -> str | None:
  """返回条件表达式；``else`` 返回 ``None``。"""
  text = header.strip().rstrip(":")
  if text == "else":
    return None
  m = _IF_HEADER_RE.match(text)
  if not m:
    raise TemplateProfileError(f"PY2CPP_BEGIN 非 if/elif: {header}")
  return m.group(1).strip()
