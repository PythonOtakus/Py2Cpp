"""原生模板求值（无 CPython AST 解析 / eval / exec）。

仅支持 [template_profile] 冻结子集。
Paw 侧对位展开见 ``compiler/paw/codegen/template_expand.paw``（BEGIN/ECHO/EVAL 冻结子集）。
"""
from __future__ import annotations

import re
from typing import Any, Callable

from .template_profile import (
  TemplateProfileError,
  assert_safe_begin_header,
  assert_safe_exec,
  assert_safe_expr,
  parse_def_header,
  parse_for_header,
  parse_if_test,
)

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _python_value_to_cpp_literal(val: Any) -> str | None:
  from ..analysis.ir import bytes_cpp_from_literal, format_cpp_float, str_cpp_from_literal

  if isinstance(val, bool):
    return "true" if val else "false"
  if isinstance(val, int):
    return str(val)
  if isinstance(val, float):
    return format_cpp_float(val)
  if isinstance(val, str):
    return str_cpp_from_literal(val)
  if isinstance(val, bytes):
    return bytes_cpp_from_literal(val)
  return None


def _resolve_echo_string(text: str, type_registry: dict[str, str] | None) -> str:
  if type_registry and text in type_registry:
    return type_registry[text]
  return text


def format_echo_value(val: Any, type_registry: dict[str, str] | None = None) -> str:
  if val is None:
    return ""
  if isinstance(val, str):
    return _resolve_echo_string(val, type_registry)
  if isinstance(val, (list, tuple)):
    return "\n".join(
      _resolve_echo_string(item, type_registry)
      for item in val
      if isinstance(item, str)
    )
  raise TemplateProfileError(
    f"PY2CPP_ECHO 须返回 str 或 list[str]，得 {type(val).__name__}"
  )


class _Tok:
  __slots__ = ("kind", "value")

  def __init__(self, kind: str, value: Any = None) -> None:
    self.kind = kind
    self.value = value


def _tokenize(expr: str) -> list[_Tok]:
  s = expr.strip()
  out: list[_Tok] = []
  i = 0
  n = len(s)
  while i < n:
    ch = s[i]
    if ch.isspace():
      i += 1
      continue
    if ch in "()":
      out.append(_Tok(ch))
      i += 1
      continue
    if ch in "+-*/%<>=!,":
      # multi-char ops
      if s[i : i + 2] in ("==", "!=", "<=", ">=", "//"):
        out.append(_Tok(s[i : i + 2]))
        i += 2
        continue
      out.append(_Tok(ch))
      i += 1
      continue
    if ch in "\"'":
      quote = ch
      j = i + 1
      buf: list[str] = []
      while j < n:
        c = s[j]
        if c == "\\" and j + 1 < n:
          buf.append(s[j + 1])
          j += 2
          continue
        if c == quote:
          out.append(_Tok("str", "".join(buf)))
          i = j + 1
          break
        buf.append(c)
        j += 1
      else:
        raise TemplateProfileError(f"字符串未闭合: {expr}")
      continue
    if ch.isdigit() or (ch == "." and i + 1 < n and s[i + 1].isdigit()):
      j = i
      while j < n and (s[j].isdigit() or s[j] == "."):
        j += 1
      raw = s[i:j]
      if "." in raw:
        out.append(_Tok("num", float(raw)))
      else:
        out.append(_Tok("num", int(raw)))
      i = j
      continue
    m = _IDENT_RE.match(s, i)
    if m:
      name = m.group(0)
      if name in ("True", "False", "None"):
        out.append(
          _Tok(
            "lit",
            True if name == "True" else False if name == "False" else None,
          )
        )
      else:
        out.append(_Tok("name", name))
      i = m.end()
      continue
    raise TemplateProfileError(f"无法词法分析: {expr!r} at {i}")
  return out


class _Parser:
  def __init__(self, toks: list[_Tok], ns: dict[str, Any]) -> None:
    self.toks = toks
    self.i = 0
    self.ns = ns

  def _peek(self) -> _Tok | None:
    return self.toks[self.i] if self.i < len(self.toks) else None

  def _eat(self, kind: str | None = None) -> _Tok:
    t = self._peek()
    if t is None:
      raise TemplateProfileError("意外结尾")
    if kind is not None and t.kind != kind:
      raise TemplateProfileError(f"期望 {kind} 得 {t.kind}")
    self.i += 1
    return t

  def parse(self) -> Any:
    v = self._or()
    if self._peek() is not None:
      raise TemplateProfileError("表达式未完全消费")
    return v

  def _or(self) -> Any:
    # no or/and in subset beyond comparisons; fall through
    return self._cmp()

  def _cmp(self) -> Any:
    left = self._add()
    t = self._peek()
    if t and t.kind in ("==", "!=", "<", ">", "<=", ">="):
      op = self._eat().kind
      right = self._add()
      if op == "==":
        return left == right
      if op == "!=":
        return left != right
      if op == "<":
        return left < right
      if op == ">":
        return left > right
      if op == "<=":
        return left <= right
      return left >= right
    return left

  def _add(self) -> Any:
    left = self._mul()
    while True:
      t = self._peek()
      if t is None or t.kind not in ("+", "-"):
        return left
      op = self._eat().kind
      right = self._mul()
      if op == "+":
        left = left + right
      else:
        left = left - right

  def _mul(self) -> Any:
    left = self._unary()
    while True:
      t = self._peek()
      if t is None or t.kind not in ("*", "/", "%", "//"):
        return left
      op = self._eat().kind
      right = self._unary()
      if op == "*":
        left = left * right
      elif op == "//":
        left = left // right
      elif op == "/":
        left = left / right
      else:
        left = left % right

  def _unary(self) -> Any:
    t = self._peek()
    if t and t.kind == "-":
      self._eat()
      return -self._unary()
    if t and t.kind == "+":
      self._eat()
      return self._unary()
    if t and t.kind == "!":
      self._eat()
      return not self._unary()
    return self._primary()

  def _primary(self) -> Any:
    t = self._peek()
    if t is None:
      raise TemplateProfileError("缺表达式")
    if t.kind == "num" or t.kind == "str" or t.kind == "lit":
      self._eat()
      return t.value
    if t.kind == "name":
      self._eat()
      name = t.value
      # call?
      if self._peek() and self._peek().kind == "(":
        self._eat("(")
        args: list[Any] = []
        if self._peek() and self._peek().kind != ")":
          args.append(self._or())
          while self._peek() and self._peek().kind == ",":
            self._eat(",")
            args.append(self._or())
        self._eat(")")
        fn = self.ns.get(name)
        if not callable(fn):
          raise TemplateProfileError(f"未知调用: {name}")
        return fn(*args)
      if name not in self.ns:
        raise TemplateProfileError(f"未知名称: {name}")
      return self.ns[name]
    if t.kind == "(":
      self._eat("(")
      v = self._or()
      self._eat(")")
      return v
    raise TemplateProfileError(f"意外 token: {t.kind}")


def eval_expr(expr: str, ns: dict[str, Any], *, where: str = "EVAL") -> Any:
  assert_safe_expr(expr, where=where)
  toks = _tokenize(expr)
  if not toks:
    return None
  return _Parser(toks, ns).parse()


def eval_echo(
  expr: str,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
  *,
  type_registry: dict[str, str] | None = None,
) -> str:
  expr = expr.strip()
  if not expr:
    return ""
  assert_safe_expr(expr, where="ECHO")
  ns = dict(helpers)
  ns.update(ctx)
  # bare name: prefer ctx value (may be C++ fragment string)
  if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", expr):
    if expr in ns:
      return format_echo_value(ns[expr], type_registry)
    if type_registry and expr in type_registry:
      return type_registry[expr]
    raise TemplateProfileError(f"PY2CPP_ECHO({expr}) 未知名称")
  try:
    val = eval_expr(expr, ns, where="ECHO")
  except Exception as exc:
    raise TemplateProfileError(f"PY2CPP_ECHO({expr}) 求值失败: {exc}") from exc
  return format_echo_value(val, type_registry)


def eval_to_cpp_slot(expr: str, ctx: dict[str, Any]) -> str:
  """``PY2CPP_EVAL`` → C++ 字面量或回退为标识符/原文。"""
  assert_safe_expr(expr, where="EVAL")
  text = expr.strip()
  safe_ns = {
    k: v
    for k, v in ctx.items()
    if isinstance(v, (int, bool, str, float, bytes)) or callable(v)
  }
  # Prefer literal / known name without requiring full eval success for C++ idents
  try:
    toks = _tokenize(text)
    if len(toks) == 1 and toks[0].kind == "name":
      name = toks[0].value
      if name in ctx:
        val = ctx[name]
        # ctx 字符串 = C++ 片段/标识符（与旧 f-string `{name}` 一致）；字面量表达式才走 PyStr
        if isinstance(val, str):
          return val
        lit = _python_value_to_cpp_literal(val)
        if lit is not None:
          return lit
      return name
    if len(toks) == 1 and toks[0].kind in ("num", "str", "lit"):
      lit = _python_value_to_cpp_literal(toks[0].value)
      if lit is not None:
        return lit
    val = eval_expr(text, safe_ns, where="EVAL")
    if isinstance(val, str):
      return val
    lit = _python_value_to_cpp_literal(val)
    if lit is not None:
      return lit
  except TemplateProfileError:
    return text
  return text


def _parse_range_call(iter_expr: str, ctx: dict[str, Any]) -> tuple[Any, Any, Any] | None:
  text = iter_expr.strip()
  if not text.startswith("range(") or not text.endswith(")"):
    return None
  inner = text[6:-1].strip()
  # split args by comma at depth 0
  parts: list[str] = []
  depth = 0
  cur: list[str] = []
  for ch in inner:
    if ch == "(":
      depth += 1
      cur.append(ch)
    elif ch == ")":
      depth -= 1
      cur.append(ch)
    elif ch == "," and depth == 0:
      parts.append("".join(cur).strip())
      cur = []
    else:
      cur.append(ch)
  if cur:
    parts.append("".join(cur).strip())
  if len(parts) == 1:
    start, stop, step = "0", parts[0], "1"
  elif len(parts) == 2:
    start, stop, step = parts[0], parts[1], "1"
  elif len(parts) == 3:
    start, stop, step = parts[0], parts[1], parts[2]
  else:
    return None

  def bound(ex: str) -> int | str | None:
    ex = ex.strip()
    try:
      v = eval_expr(ex, {k: v for k, v in ctx.items() if isinstance(v, (int, bool, str))}, where="range")
    except TemplateProfileError:
      if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ex):
        return ex
      return None
    if isinstance(v, bool):
      return int(v)
    if isinstance(v, int):
      return v
    if isinstance(v, str):
      return v
    return None

  return bound(start), bound(stop), bound(step)


EmitLine = Callable[[str, dict[str, Any]], str]


_EXEC_LINE_RE = re.compile(r"^\s*PY2CPP_EXEC\s*\(\s*(.*)\s*\)\s*$")


def _expand_macro_calls(text: str, macro: str, handler: Callable[[str], str]) -> str:
  marker = f"PY2CPP_{macro}("
  out: list[str] = []
  i = 0
  while i < len(text):
    idx = text.find(marker, i)
    if idx < 0:
      out.append(text[i:])
      break
    out.append(text[i:idx])
    start = idx + len(marker)
    depth = 1
    j = start
    while j < len(text):
      ch = text[j]
      if ch == "(":
        depth += 1
      elif ch == ")":
        depth -= 1
        if depth == 0:
          expr = text[start:j].strip()
          out.append(handler(expr))
          i = j + 1
          break
      j += 1
    else:
      raise TemplateProfileError(f"PY2CPP_{macro} 括号不匹配")
  return "".join(out)


def emit_template_line(
  line: str,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
  *,
  type_registry: dict[str, str] | None = None,
) -> str:
  """展开一行内的 EVAL/ECHO；若为 EXEC 行则执行副作用并返回文本。"""
  m_exec = _EXEC_LINE_RE.match(line)
  if m_exec:
    return run_exec(m_exec.group(1).strip(), ctx, helpers)

  def echo_handler(expr: str) -> str:
    return eval_echo(expr, ctx, helpers, type_registry=type_registry)

  def eval_handler(expr: str) -> str:
    return eval_to_cpp_slot(expr, ctx)

  text = _expand_macro_calls(line, "ECHO", echo_handler)
  text = _expand_macro_calls(text, "EVAL", eval_handler)
  return text


def expand_for_block(
  header: str,
  body_lines: list[str],
  ctx: dict[str, Any],
  helpers: dict[str, Any],
  *,
  type_registry: dict[str, str] | None = None,
  where: str = "for",
) -> str:
  assert_safe_begin_header(header, where=where)
  var, iter_expr = parse_for_header(header)
  assert_safe_expr(iter_expr, where=where)

  # name list in ctx
  if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", iter_expr):
    val = ctx.get(iter_expr)
    if isinstance(val, (list, tuple)) and all(isinstance(x, str) for x in val):
      out: list[str] = []
      local = dict(ctx)
      for item in val:
        local[var] = item
        for ln in body_lines:
          if not ln.strip():
            continue
          out.append(
            emit_template_line(ln, local, helpers, type_registry=type_registry)
          )
      return "\n".join(out)

  bounds = _parse_range_call(iter_expr, ctx)
  if bounds is None:
    raise TemplateProfileError(
      f"PY2CPP_BEGIN(for) 仅支持 range(...) 或 ctx 名称列表: {header}"
    )
  start_b, stop_b, step_b = bounds
  if all(isinstance(b, int) for b in bounds):
    out = []
    local = dict(ctx)
    for i in range(start_b, stop_b, step_b):  # type: ignore[arg-type]
      local[var] = i
      for ln in body_lines:
        if not ln.strip():
          continue
        out.append(
          emit_template_line(ln, local, helpers, type_registry=type_registry)
        )
    return "\n".join(out)

  # C++ fallback while
  if not isinstance(start_b, int) or not isinstance(step_b, int):
    raise TemplateProfileError(f"range 回退要求 start/step 为编译期 int: {header}")
  if not isinstance(stop_b, str):
    raise TemplateProfileError(f"range 回退要求 stop 为 C++ 标识符: {header}")
  indent = "  "
  out = [f"int {var} = {start_b};", f"while (({var} < {stop_b}))", "{"]
  for ln in body_lines:
    if ln.strip():
      out.append(
        indent
        + emit_template_line(ln, ctx, helpers, type_registry=type_registry)
      )
  if step_b == 1:
    out.append(f"{indent}{var} = ({var} + 1);")
  else:
    out.append(f"{indent}{var} = ({var} + {step_b});")
  out.append("}")
  return "\n".join(out)


def _static_bool(test: str, ctx: dict[str, Any]) -> bool | None:
  safe = {k: v for k, v in ctx.items() if isinstance(v, (int, bool, str, float))}
  try:
    return bool(eval_expr(test, safe, where="if"))
  except TemplateProfileError:
    return None


def expand_if_chain(
  chunks: list[tuple[str, list[str]]],
  ctx: dict[str, Any],
  helpers: dict[str, Any],
  *,
  type_registry: dict[str, str] | None = None,
  where: str = "if",
) -> str:
  tests: list[tuple[str | None, list[str]]] = []
  for header, body in chunks:
    assert_safe_begin_header(header, where=where)
    tests.append((parse_if_test(header), body))

  static_results: list[bool | None] = []
  all_static = True
  for test, _ in tests:
    if test is None:
      static_results.append(None)
      continue
    r = _static_bool(test, ctx)
    if r is None:
      all_static = False
      static_results.append(None)
    else:
      static_results.append(r)

  if all_static:
    picked: list[str] | None = None
    for i, (test, body) in enumerate(tests):
      if test is None:
        picked = body
        break
      if static_results[i]:
        picked = body
        break
    if picked is None:
      return ""
    out: list[str] = []
    for ln in picked:
      if not ln.strip():
        continue
      out.append(
        emit_template_line(ln, ctx, helpers, type_registry=type_registry)
      )
    return "\n".join(out)

  indent = "  "
  out: list[str] = []
  for i, (test, body) in enumerate(tests):
    if test is None:
      out.append("else")
    elif i == 0:
      out.append(f"if (({test}))")
    else:
      out.append(f"else if (({test}))")
    out.append("{")
    for ln in body:
      if ln.strip():
        out.append(
          indent
          + emit_template_line(ln, ctx, helpers, type_registry=type_registry)
        )
    out.append("}")
  return "\n".join(out)


def register_template_def(
  header: str,
  body_lines: list[str],
  expand_fragment: Callable[[str, dict[str, Any], dict[str, Any]], str],
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> None:
  assert_safe_begin_header(header, where="def")
  name, arg_names = parse_def_header(header)

  def invoke(*args: Any) -> str:
    if len(args) != len(arg_names):
      raise TemplateProfileError(
        f"{name} 参数个数不匹配: {len(arg_names)} != {len(args)}"
      )
    local: dict[str, Any] = dict(ctx)
    for an, av in zip(arg_names, args):
      local[an] = av
    return expand_fragment("\n".join(body_lines), local, helpers)

  helpers[name] = invoke
  ctx[name] = invoke


def run_exec(stmt: str, ctx: dict[str, Any], helpers: dict[str, Any]) -> str:
  assert_safe_exec(stmt, where="EXEC")
  text = stmt.strip()
  ns = dict(helpers)
  ns.update(ctx)

  # assignment
  m_asg = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", text)
  if m_asg and not text.startswith("if "):
    name, rhs = m_asg.group(1), m_asg.group(2)
    val = eval_expr(rhs, ns, where="EXEC")
    helpers[name] = val
    ctx[name] = val
    return ""

  # if …: __py2cpp_echo('…')  — limited showcase form
  m_if = re.match(
    r"^if\s+(.+?)\s*:\s*__py2cpp_echo\((.+)\)\s*$",
    text,
  )
  if m_if:
    cond = m_if.group(1)
    arg = m_if.group(2).strip()
    if _static_bool(cond, ns):
      # string literal or expr
      if (arg.startswith("'") and arg.endswith("'")) or (
        arg.startswith('"') and arg.endswith('"')
      ):
        return arg[1:-1]
      return str(eval_expr(arg, ns, where="EXEC"))
    return ""

  # call → maybe returns str
  try:
    val = eval_expr(text, ns, where="EXEC")
    if isinstance(val, str):
      return val
  except TemplateProfileError:
    pass
  raise TemplateProfileError(f"EXEC 无法原生求值: {stmt}")
