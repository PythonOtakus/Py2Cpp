"""构建期展开 ``templates/**`` 中的 ``PY2CPP_*`` 宏（BEGIN/END、EVAL、EXEC、ECHO、INCLUDE、TYPE）。"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Callable

from ..constant.stdlib_layout import cpp_stdlib_class, EXCEPTIONS_NS
from ..passes.inline_range import _const_int_expr
from ..passes.static_reflect import _const_compare_result
from .brace_style import kr_to_allman
from .template_scope import namespace_close_lines, namespace_open_lines, namespace_qualifier_for_module_rel

_TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates"

_BEGIN_RE = re.compile(r"^\s*PY2CPP_BEGIN\s*\(\s*(.*?)\s*\)\s*$")
_END_RE = re.compile(r"^\s*PY2CPP_END\s*$")
_INJECT_CLASS_RE = re.compile(r"^\s*PY2CPP_INJECT_CLASS\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$")
_IGNORE_RE = re.compile(r"^\s*PY2CPP_IGNORE\s*$")
_BEGIN_SCOPE_RE = re.compile(r"^\s*PY2CPP_BEGIN_SCOPE\s*$")
_END_SCOPE_RE = re.compile(r"^\s*PY2CPP_END_SCOPE\s*$")
_INCLUDE_RE = re.compile(r"^\s*PY2CPP_INCLUDE\s*\(\s*\"([^\"]+)\"\s*\)\s*$")
_EXEC_RE = re.compile(r"^\s*PY2CPP_EXEC\s*\(\s*(.*)\s*\)\s*$")
_TYPE_RE = re.compile(r"PY2CPP_TYPE\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)")
_TYPE_TOKEN_RE = re.compile(r"\bPY2CPP_TYPE_([A-Za-z_][A-Za-z0-9_]*)\b")
_FORBIDDEN_TYPE_EVAL_RE = re.compile(r"PY2CPP_TYPE\s*\(\s*PY2CPP_EVAL\s*\(")
_FORBIDDEN_DYNAMIC_TYPE_RE = re.compile(r"PY2CPP_DYNAMIC_TYPE\s*\(")

# C++ 标准库容器（编码规范禁止；``std::enable_if`` / ``std::declval`` / ``std::forward`` 等 traits 允许，含 ``<utility>``）
_STL_CONTAINER_NAMES: tuple[str, ...] = (
  "array",
  "deque",
  "forward_list",
  "list",
  "map",
  "multimap",
  "multiset",
  "pair",
  "priority_queue",
  "queue",
  "set",
  "stack",
  "tuple",
  "unordered_map",
  "unordered_multimap",
  "unordered_set",
  "unordered_multiset",
  "vector",
)
_STL_CONTAINER_ALT = "|".join(_STL_CONTAINER_NAMES)
_FORBIDDEN_STL_CONTAINER_INCLUDE_RE = re.compile(
  rf"#\s*include\s*<\s*(?:{_STL_CONTAINER_ALT})\s*>",
  re.IGNORECASE,
)
_FORBIDDEN_STL_CONTAINER_TYPE_RE = re.compile(
  rf"\bstd::(?:{_STL_CONTAINER_ALT})\s*<",
  re.IGNORECASE,
)

_PY_TYPES = frozenset(
  {
    "PyChar",
    "PyByte",
    "PyInt",
    "PyFloat",
    "PyBool",
    "PyInt64",
    "PyUInt",
    "PyUInt64",
    "PyUPtr",
    "PyFloat64",
  }
)

_STD_TYPES = {
  "PyStr": cpp_stdlib_class("text/str", "PyStr"),
  "PyBytes": cpp_stdlib_class("text/bytes", "PyBytes"),
  "PyList": cpp_stdlib_class("util/list", "PyList"),
  "PyDeque": cpp_stdlib_class("util/deque", "PyDeque"),
  "PyDict": cpp_stdlib_class("util/dict", "PyDict"),
  "PyArray": cpp_stdlib_class("util/array", "PyArray"),
  "PyArray2D": cpp_stdlib_class("util/array", "PyArray2D"),
  "PyArray3D": cpp_stdlib_class("util/array", "PyArray3D"),
  "PyIterResult": cpp_stdlib_class("core/iter_result", "PyIterResult"),
  "PyNone": cpp_stdlib_class("core/none", "PyNone"),
  "PyCoroutine": cpp_stdlib_class("core/coroutine", "PyCoroutine"),
  "PyOptional": cpp_stdlib_class("core/optional", "PyOptional"),
}


def template_root() -> Path:
  return _TEMPLATE_ROOT


def _assert_no_forbidden_type_eval(text: str, where: str) -> None:
  if _FORBIDDEN_TYPE_EVAL_RE.search(text):
    raise ValueError(
      f"禁止 PY2CPP_TYPE(PY2CPP_EVAL(...))；请用 IGNORE #define ctx_* + PY2CPP_ECHO(ctx_*)：{where}"
    )


def _assert_no_forbidden_dynamic_type(text: str, where: str) -> None:
  if _FORBIDDEN_DYNAMIC_TYPE_RE.search(text):
    raise ValueError(
      f"PY2CPP_DYNAMIC_TYPE 已删除；行内动态 C++ 片段请用 IGNORE #define ctx_* + PY2CPP_ECHO(ctx_*)：{where}"
    )


def _find_forbidden_stl_container_lines(text: str) -> list[tuple[int, str, str]]:
  """``(行号, 类别, 语句)``；类别为 ``include`` 或 ``type``。"""
  hits: list[tuple[int, str, str]] = []
  for lineno, line in enumerate(text.splitlines(), start=1):
    stmt = line.rstrip()
    if _FORBIDDEN_STL_CONTAINER_INCLUDE_RE.search(line):
      hits.append((lineno, "include", stmt))
    elif _FORBIDDEN_STL_CONTAINER_TYPE_RE.search(line):
      hits.append((lineno, "type", stmt))
  return hits


def _format_forbidden_stl_container_message(
  where: str,
  hits: list[tuple[int, str, str]],
) -> str:
  kind_hint = {
    "include": "STL 容器头（如 <vector>、<map>）",
    "type": "std:: 容器类型（如 std::vector<…>、std::map<…>）",
  }
  lines = [
    "模板禁止使用 STL 容器；请用 PyList / PyDict 或定长数组："
    f"{where}",
  ]
  for lineno, kind, stmt in hits:
    lines.append(f"  {where}:{lineno} [{kind_hint[kind]}]: {stmt}")
  return "\n".join(lines)


def _assert_no_forbidden_stl_containers(text: str, where: str) -> None:
  hits = _find_forbidden_stl_container_lines(text)
  if hits:
    raise ValueError(_format_forbidden_stl_container_message(where, hits))


def collect_forbidden_dynamic_type_violations() -> list[str]:
  from .template_conventions import collect_forbidden_dynamic_type_violations as _collect

  return _collect()


def collect_forbidden_type_eval_violations() -> list[str]:
  from .template_conventions import collect_forbidden_type_eval_violations as _collect

  return _collect()


def collect_forbidden_stl_container_violations() -> list[str]:
  from .template_conventions import collect_forbidden_stl_container_violations as _collect

  return _collect()


def _type_registry() -> dict[str, str]:
  from ..analysis.stubs.class_stubs import load_stdlib_exception_types
  from ..constant.language import default_py_class_cpp_name
  from ..constant.stdlib_layout import cpp_exception_type

  out = dict(_STD_TYPES)
  for name in _PY_TYPES:
    out.setdefault(name, name)
  for name in load_stdlib_exception_types():
    cpp = default_py_class_cpp_name(name)
    out[name] = cpp_exception_type(name)
    out[cpp] = cpp_exception_type(name)
  return out


def clangd_macro_expansion_stub_lines() -> list[str]:
  """``~macro/*.h`` 中 ``PY2CPP_EVAL`` / ``PY2CPP_TYPE`` 的 clangd 可展开桩（与 ``_type_registry`` 同步）。"""
  lines = [
    "#define PY2CPP_EVAL(...) __VA_ARGS__",
    "#define PY2CPP_ECHO(...) __VA_ARGS__",
  ]
  for key, qual in sorted(_type_registry().items()):
    lines.append(f"#define PY2CPP_TYPE_{key} {qual}")
  lines.append("#define PY2CPP_TYPE(Type) PY2CPP_TYPE_##Type")
  return lines


def _resolve_include_path(include_rel: str, base_dir: Path) -> Path:
  norm = include_rel.replace("\\", "/")
  path = (base_dir / norm).resolve()
  root = _TEMPLATE_ROOT.resolve()
  if not str(path).startswith(str(root)):
    raise ValueError(f"PY2CPP_INCLUDE 路径越界: {include_rel}")
  if not path.is_file():
    raise FileNotFoundError(f"模板 INCLUDE 不存在: {include_rel}")
  return path


def _replace_py2cpp_type(text: str) -> str:
  registry = _type_registry()

  def repl_token(m: re.Match[str]) -> str:
    key = m.group(1)
    if key not in registry:
      raise KeyError(f"PY2CPP_TYPE 未注册: {key}")
    return registry[key]

  def repl_paren(m: re.Match[str]) -> str:
    key = m.group(1)
    if key not in registry:
      raise KeyError(f"PY2CPP_TYPE 未注册: {key}")
    return registry[key]

  prev = None
  cur = text
  while prev != cur:
    prev = cur
    cur = _TYPE_TOKEN_RE.sub(repl_token, cur)
    cur = _TYPE_RE.sub(repl_paren, cur)
  return cur


def _extract_paren_arg(line: str, prefix: str) -> str | None:
  marker = f"PY2CPP_{prefix}("
  idx = line.find(marker)
  if idx < 0:
    return None
  start = idx + len(marker)
  depth = 1
  i = start
  while i < len(line):
    ch = line[i]
    if ch == "(":
      depth += 1
    elif ch == ")":
      depth -= 1
      if depth == 0:
        return line[start:i].strip()
    i += 1
  return None


def _escape_fstring_literal(chunk: str) -> str:
  return chunk.replace("\\", "\\\\").replace("{", "{{").replace("}", "}}")


def _cpp_line_to_emit_stmt(line: str) -> str:
  m_exec = _EXEC_RE.match(line)
  if m_exec:
    return m_exec.group(1).strip()
  out: list[str] = []
  i = 0
  while i < len(line):
    eval_at = line.find("PY2CPP_EVAL(", i)
    echo_at = line.find("PY2CPP_ECHO(", i)
    candidates = [(eval_at, "eval"), (echo_at, "echo")]
    candidates = [(pos, kind) for pos, kind in candidates if pos >= 0]
    if not candidates:
      out.append(_escape_fstring_literal(line[i:]))
      break
    pos, kind = min(candidates, key=lambda x: x[0])
    out.append(_escape_fstring_literal(line[i:pos]))
    if kind == "eval":
      expr = _extract_paren_arg(line[pos:], "EVAL")
      if expr is None:
        raise ValueError(f"PY2CPP_EVAL 括号不匹配: {line}")
      consumed = len("PY2CPP_EVAL(") + len(expr) + 1
      out.append(f"{{{expr}}}")
      i = pos + consumed
      continue
    expr = _extract_paren_arg(line[pos:], "ECHO")
    if expr is None:
      raise ValueError(f"PY2CPP_ECHO 括号不匹配: {line}")
    consumed = len("PY2CPP_ECHO(") + len(expr) + 1
    out.append(f"{{__py2cpp_echo_val({expr!r})}}")
    i = pos + consumed
  body = "".join(out)
  return f"__py2cpp_echo(f'{body}')"


def _expand_macro_calls(
  text: str,
  macro: str,
  handler: Callable[[str], str],
) -> str:
  """按括号平衡展开 ``PY2CPP_{macro}(…)``（参数可含嵌套括号）。"""
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
      raise ValueError(f"PY2CPP_{macro} 括号不匹配")
  return "".join(out)


def _resolve_echo_string(text: str) -> str:
  registry = _type_registry()
  if text in registry:
    return registry[text]
  return text


def _format_echo_value(val: Any) -> str:
  if val is None:
    return ""
  if isinstance(val, str):
    return _resolve_echo_string(val)
  if isinstance(val, (list, tuple)):
    return "\n".join(
      _resolve_echo_string(item) for item in val if isinstance(item, str)
    )
  raise ValueError(
    f"PY2CPP_ECHO 须返回 str 或 list[str]，得 {type(val).__name__}"
  )


def _eval_echo_expr(
  expr: str,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> str:
  """``PY2CPP_ECHO(expr)``：构建期 CPython 表达式 → 原样粘贴的 C++ 文本。"""
  expr = expr.strip()
  if not expr:
    return ""
  ns: dict[str, Any] = dict(helpers)
  ns.update(ctx)
  try:
    val = eval(expr, {"__builtins__": {}}, ns)
  except Exception as exc:
    raise ValueError(f"PY2CPP_ECHO({expr}) 求值失败: {exc}") from exc
  return _format_echo_value(val)


def _python_value_to_cpp_literal(val: Any) -> str | None:
  """构建期 Python 常量 → 与译器 ``ir`` 一致的 C++ 字面量。"""
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


def _eval_cpp_slot(expr: str, ctx: dict[str, Any]) -> str:
  try:
    tree = ast.parse(expr, mode="eval")
  except SyntaxError:
    return expr
  body = tree.body
  if isinstance(body, ast.Constant):
    lit = _python_value_to_cpp_literal(body.value)
    if lit is not None:
      return lit
  lit = _const_int_expr(body)
  if lit is not None:
    return str(lit)
  if isinstance(body, ast.Name) and body.id in ctx:
    val = ctx[body.id]
    if isinstance(val, str):
      if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
        return val
    lit = _python_value_to_cpp_literal(val)
    if lit is not None:
      return lit
  safe_ctx = {k: v for k, v in ctx.items() if isinstance(v, (int, bool, str, float, bytes))}
  try:
    val = eval(expr, {"__builtins__": {}}, safe_ctx)
    lit = _python_value_to_cpp_literal(val)
    if lit is not None:
      return lit
  except Exception:
    pass
  return ast.unparse(body)


def _transform_line_for_cpp_fallback(line: str, ctx: dict[str, Any]) -> str:
  line = _expand_macro_calls(
    line,
    "ECHO",
    lambda expr: _eval_echo_expr(expr, ctx, {}),
  )

  def repl_eval(m: re.Match[str]) -> str:
    expr = m.group(1).strip()
    return _eval_cpp_slot(expr, ctx)

  return re.sub(r"PY2CPP_EVAL\s*\(\s*(.*?)\s*\)", repl_eval, line)


def _bind_py2cpp_echo_val(
  loc: dict[str, Any],
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> None:
  def __py2cpp_echo_val(expr: str) -> str:
    return _eval_echo_expr(expr, loc, helpers)

  loc["__py2cpp_echo_val"] = __py2cpp_echo_val


def _parse_range_bounds(iter_node: ast.expr, ctx: dict[str, Any]) -> tuple[Any, Any, Any] | None:
  if not isinstance(iter_node, ast.Call):
    return None
  func = iter_node.func
  if not isinstance(func, ast.Name) or func.id != "range":
    return None
  args = iter_node.args
  if len(args) == 1:
    start, stop, step = ast.Constant(value=0), args[0], ast.Constant(value=1)
  elif len(args) == 2:
    start, stop, step = args[0], args[1], ast.Constant(value=1)
  elif len(args) == 3:
    start, stop, step = args[0], args[1], args[2]
  else:
    return None

  def bound(expr: ast.expr) -> int | str | None:
    lit = _const_int_expr(expr)
    if lit is not None:
      return lit
    if isinstance(expr, ast.Name):
      if expr.id in ctx and isinstance(ctx[expr.id], int):
        return ctx[expr.id]
      if expr.id in ctx and isinstance(ctx[expr.id], str):
        return ctx[expr.id]
      return expr.id
    return None

  return bound(start), bound(stop), bound(step)


def _builtin_template_ctx() -> dict[str, Any]:
  from ..analysis.stubs.class_stubs import load_stdlib_exception_types
  from ..constant.language import default_py_class_cpp_name

  skip = frozenset({"Exception", "ExcTypeUnion"})
  fwd_skip = frozenset({"Exception", "ExcTypeUnion"})
  return {
    "exception_type_names": sorted(
      default_py_class_cpp_name(n)
      for n in load_stdlib_exception_types()
      if n not in skip
    ),
    "exception_forward_decl_names": sorted(
      default_py_class_cpp_name(n)
      for n in load_stdlib_exception_types()
      if n not in fwd_skip
    ),
  }


def exception_pystr_ctor_base(name: str) -> str:
  """``name`` 为 Python 或已加 ``Py`` 的 C++ 异常类名。"""
  from ..constant.language import default_py_class_cpp_name

  py = name[2:] if name.startswith("Py") and len(name) > 2 and name[2].isupper() else name
  if py in ("StatisticsError", "LinAlgError"):
    return default_py_class_cpp_name("ValueError")
  if py in ("FileNotFoundError", "FileExistsError"):
    return default_py_class_cpp_name("OSError")
  return default_py_class_cpp_name("Exception")


_EXCEPTION_PYSTR_CTOR_SKIP = frozenset({
  "Exception",
  "PyException",
  "BaseExceptionGroup",
  "PyBaseExceptionGroup",
  "ExceptionGroup",
  "PyExceptionGroup",
  "ExcTypeUnion",
  "PyExcTypeUnion",
})


def _parse_for_iter_names(for_node: ast.For, ctx: dict[str, Any]) -> list[str] | None:
  if not isinstance(for_node.iter, ast.Name):
    return None
  val = ctx.get(for_node.iter.id)
  if not isinstance(val, (list, tuple)):
    return None
  if not all(isinstance(x, str) for x in val):
    return None
  return list(val)


def _range_length(start: int, stop: int, step: int) -> int:
  if step == 0:
    raise ValueError("range step 不能为 0")
  if step > 0:
    n = max(0, (stop - start + step - 1) // step)
  else:
    n = max(0, (start - stop - step - 1) // (-step))
  return n


def _expand_for_block(header: str, body_lines: list[str], ctx: dict[str, Any]) -> str:
  stmt = f"{header.strip()}: pass"
  for_node = ast.parse(stmt).body[0]
  if not isinstance(for_node, ast.For):
    raise ValueError(f"PY2CPP_BEGIN 非 for: {header}")
  loop_var = for_node.target
  if not isinstance(loop_var, ast.Name):
    raise ValueError("PY2CPP_BEGIN(for) 仅支持单变量")
  var = loop_var.id
  emit_stmts = [_cpp_line_to_emit_stmt(ln) for ln in body_lines if ln.strip()]

  list_items = _parse_for_iter_names(for_node, ctx)
  if list_items is not None:
    lines_out: list[str] = []
    loc: dict[str, Any] = dict(ctx)
    loc["__py2cpp_code"] = lines_out
    loc["__py2cpp_echo"] = lines_out.append
    _bind_py2cpp_echo_val(loc, ctx, helpers={})
    emit_src = "\n".join(emit_stmts)
    for item in list_items:
      loc[var] = item
      exec(emit_src, loc)
    return "\n".join(lines_out)

  bounds = _parse_range_bounds(for_node.iter, ctx)

  if bounds is None:
    raise ValueError(f"PY2CPP_BEGIN(for) 仅支持 range(...) 或 ctx 中的名称列表: {header}")

  start_b, stop_b, step_b = bounds
  static = all(isinstance(b, int) for b in bounds)
  if static:
    start_i, stop_i, step_i = start_b, stop_b, step_b
    lines_out: list[str] = []
    loc: dict[str, Any] = dict(ctx)
    loc["__py2cpp_code"] = lines_out
    loc["__py2cpp_echo"] = lines_out.append
    _bind_py2cpp_echo_val(loc, ctx, helpers={})
    emit_src = "\n".join(emit_stmts)
    for i in range(start_i, stop_i, step_i):
      loc[var] = i
      exec(emit_src, loc)
    return "\n".join(lines_out)

  if not isinstance(start_b, int) or not isinstance(step_b, int):
    raise ValueError(f"range 回退要求 start/step 为编译期 int: {header}")
  if not isinstance(stop_b, str):
    raise ValueError(f"range 回退要求 stop 为 C++ 标识符: {header}")

  indent = "  "
  out: list[str] = []
  out.append(f"int {var} = {start_b};")
  out.append(f"while (({var} < {stop_b}))")
  out.append("{")
  for ln in body_lines:
    if ln.strip():
      out.append(indent + _transform_line_for_cpp_fallback(ln, ctx))
  if step_b == 1:
    out.append(f"{indent}{var} = ({var} + 1);")
  else:
    out.append(f"{indent}{var} = ({var} + {step_b});")
  out.append("}")
  return "\n".join(out)


def _if_test_expr(header: str) -> ast.expr:
  text = header.strip()
  if text.startswith("if "):
    text = text[3:]
  elif text.startswith("elif "):
    text = text[5:]
  else:
    raise ValueError(f"PY2CPP_BEGIN 非 if/elif: {header}")
  if text.endswith(":"):
    text = text[:-1]
  return ast.parse(text, mode="eval").body


def _static_bool(test: ast.expr, ctx: dict[str, Any]) -> bool | None:
  if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
    r = _const_compare_result(test.left, test.ops[0], test.comparators[0])
    if r is not None:
      return r
  safe = {k: v for k, v in ctx.items() if isinstance(v, (int, bool))}
  try:
    return bool(eval(ast.unparse(test), {"__builtins__": {}}, safe))
  except Exception:
    return None


def _expand_if_chain(chunks: list[tuple[str, list[str]]], ctx: dict[str, Any]) -> str:
  tests: list[tuple[ast.expr | None, list[str]]] = []
  for header, body in chunks:
    h = header.strip()
    if h == "else" or h == "else:":
      tests.append((None, body))
    else:
      tests.append((_if_test_expr(header), body))

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
    lines_out: list[str] = []
    loc: dict[str, Any] = dict(ctx)
    loc["__py2cpp_code"] = lines_out
    loc["__py2cpp_echo"] = lines_out.append
    _bind_py2cpp_echo_val(loc, ctx, helpers={})
    emit_src = "\n".join([_cpp_line_to_emit_stmt(ln) for ln in picked if ln.strip()])
    exec(emit_src, loc)
    return "\n".join(lines_out)

  indent = "  "
  out: list[str] = []
  for i, (test, body) in enumerate(tests):
    if test is None:
      out.append("else")
    elif i == 0:
      out.append(f"if (({ast.unparse(test)}))")
    else:
      out.append(f"else if (({ast.unparse(test)}))")
    out.append("{")
    for ln in body:
      if ln.strip():
        out.append(indent + _transform_line_for_cpp_fallback(ln, ctx))
    out.append("}")
  return "\n".join(out)


def _is_def_header(header: str) -> bool:
  return header.strip().startswith("def ")


def _run_exec(stmt: str, ctx: dict[str, Any], helpers: dict[str, Any]) -> str:
  """构建期 ``exec`` / ``eval``；模板 ``def`` 调用返回 C++ 文本时内联到调用点。"""
  ns: dict[str, Any] = dict(helpers)
  ns.update(ctx)
  text = stmt.strip()
  try:
    tree = ast.parse(text, mode="eval")
    val = eval(compile(tree, "<py2cpp exec>", "eval"), {"__builtins__": {}}, ns)
    if isinstance(val, str):
      return val
  except SyntaxError:
    pass
  exec(text, ns)
  for key, val in ns.items():
    if key.startswith("__"):
      continue
    helpers[key] = val
    ctx[key] = val
  return ""


def _expand_template_fragment(
  fragment: str,
  base_dir: Path,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> str:
  text = _expand_blocks_in_text(fragment, ctx, helpers)
  text = _expand_echo(text, ctx, helpers)
  module_rel = ctx.get("module_rel")
  rel_str = module_rel if isinstance(module_rel, str) else None
  return _expand_namespace_macro(text, rel_str)


def _register_template_def(
  header: str,
  body_lines: list[str],
  base_dir: Path,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> None:
  stmt = f"{header.strip()}: pass"
  tree = ast.parse(stmt).body[0]
  if not isinstance(tree, ast.FunctionDef):
    raise ValueError(f"PY2CPP_BEGIN(def) 非法: {header}")
  name = tree.name
  arg_names = [a.arg for a in tree.args.args]

  def invoke(*args: Any) -> str:
    if len(args) != len(arg_names):
      raise ValueError(f"{name} 参数个数不匹配: {len(arg_names)} != {len(args)}")
    local: dict[str, Any] = dict(ctx)
    for an, av in zip(arg_names, args):
      local[an] = av
    return _expand_template_fragment("\n".join(body_lines), base_dir, local, helpers)

  helpers[name] = invoke
  ctx[name] = invoke


def _scan_def_blocks(lines: list[str]) -> list[_Block]:
  """``def`` 块整段抓取（体内嵌套 ``BEGIN/END`` 保留为原文，供模板 helper 展开）。"""
  blocks: list[_Block] = []
  i = 0
  while i < len(lines):
    m_begin = _BEGIN_RE.match(lines[i])
    if m_begin is None or not _is_def_header(m_begin.group(1)):
      i += 1
      continue
    header = m_begin.group(1)
    start = i
    i += 1
    depth = 1
    body_lines: list[str] = []
    while i < len(lines) and depth > 0:
      if _BEGIN_RE.match(lines[i]):
        depth += 1
        body_lines.append(lines[i])
        i += 1
        continue
      if _END_RE.match(lines[i]):
        depth -= 1
        if depth > 0:
          body_lines.append(lines[i])
        i += 1
        continue
      body_lines.append(lines[i])
      i += 1
    if depth != 0:
      raise ValueError(f"PY2CPP_BEGIN(def) 缺少 PY2CPP_END: {header}")
    blocks.append(_Block(header, body_lines, start, i - 1))
  return blocks


def _strip_and_register_def_blocks(
  text: str,
  base_dir: Path,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> str:
  lines = text.splitlines()
  blocks = _scan_def_blocks(lines)
  if not blocks:
    return text
  replacements: list[tuple[int, int, str]] = []
  for b in blocks:
    _register_template_def(b.header, b.body_lines, base_dir, ctx, helpers)
    replacements.append((b.start, b.end, ""))
  for start, end, repl in sorted(replacements, key=lambda x: x[0], reverse=True):
    lines[start:end + 1] = [repl] if repl else []
  return "\n".join(lines)


class _Block:
  def __init__(self, header: str, body_lines: list[str], start: int, end: int) -> None:
    self.header = header
    self.body_lines = body_lines
    self.start = start
    self.end = end


def _scan_blocks(lines: list[str]) -> list[_Block]:
  blocks: list[_Block] = []
  stack: list[tuple[str, list[str], int]] = []
  i = 0
  while i < len(lines):
    line = lines[i]
    if _INJECT_CLASS_RE.match(line):
      i += 1
      while i < len(lines) and not _END_RE.match(lines[i]):
        i += 1
      if i >= len(lines):
        raise ValueError("PY2CPP_INJECT_CLASS 缺少 PY2CPP_END")
      i += 1
      continue
    m_begin = _BEGIN_RE.match(line)
    if m_begin:
      stack.append((m_begin.group(1), [], i))
      i += 1
      continue
    if _END_RE.match(line):
      if not stack:
        raise ValueError(f"PY2CPP_END 无匹配 BEGIN（行 {i + 1}）")
      header, body, start = stack.pop()
      blocks.append(_Block(header, body, start, i))
      i += 1
      continue
    if stack:
      stack[-1][1].append(line)
    i += 1
  if stack:
    raise ValueError("PY2CPP_BEGIN 缺少 PY2CPP_END")
  return blocks


def _merge_if_chains(blocks: list[_Block]) -> list[tuple[str, list[_Block]]]:
  if not blocks:
    return []
  groups: list[tuple[str, list[_Block]]] = []
  i = 0
  while i < len(blocks):
    b = blocks[i]
    h = b.header.strip()
    if h.startswith("if ") or h.startswith("if:"):
      chain = [b]
      j = i + 1
      while j < len(blocks):
        nh = blocks[j].header.strip()
        if nh.startswith("elif ") or nh == "else" or nh == "else:":
          chain.append(blocks[j])
          j += 1
        else:
          break
      groups.append(("if_chain", chain))
      i = j
    else:
      groups.append(("single", [b]))
      i += 1
  return groups


def _expand_blocks_in_text(text: str, ctx: dict[str, Any], helpers: dict[str, Any]) -> str:
  lines = text.splitlines()
  blocks = _scan_blocks(lines)
  if not blocks:
    return text

  for block in blocks:
    block.body_lines = _expand_blocks_in_text(
      "\n".join(block.body_lines), ctx, helpers
    ).splitlines()

  groups = _merge_if_chains(blocks)
  replacements: list[tuple[int, int, str]] = []
  for kind, group in groups:
    if kind == "if_chain":
      chunks = [(b.header, b.body_lines) for b in group]
      repl = _expand_if_chain(chunks, ctx)
      replacements.append((group[0].start, group[-1].end, repl))
    else:
      b = group[0]
      if b.header.strip().startswith("for "):
        repl = _expand_for_block(b.header, b.body_lines, ctx)
      else:
        repl = _expand_if_chain([(b.header, b.body_lines)], ctx)
      replacements.append((b.start, b.end, repl))

  for start, end, repl in sorted(replacements, key=lambda x: x[0], reverse=True):
    lines[start:end + 1] = [repl] if repl else []

  return "\n".join(lines)


def _expand_includes_and_exec(
  text: str,
  base_dir: Path,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> str:
  lines = text.splitlines()
  out: list[str] = []
  begin_depth = 0
  for line in lines:
    if _BEGIN_RE.match(line):
      begin_depth += 1
      out.append(line)
      continue
    if _END_RE.match(line) and begin_depth > 0:
      begin_depth -= 1
      out.append(line)
      continue
    if begin_depth > 0:
      out.append(line)
      continue
    m = _INCLUDE_RE.match(line)
    if m:
      inc_path = _resolve_include_path(m.group(1), base_dir)
      inc_text = inc_path.read_text(encoding="utf-8")
      expanded = _expand_template_text(inc_text, inc_path.parent, ctx, helpers)
      if expanded:
        out.append(expanded)
      continue
    m_exec = _EXEC_RE.match(line)
    if m_exec:
      emitted = _run_exec(m_exec.group(1), ctx, helpers)
      if emitted.strip():
        out.append(emitted)
      continue
    out.append(line)
  return "\n".join(out)


def extract_py2cpp_inject_class_blocks(text: str) -> dict[str, list[str]]:
  """``PY2CPP_INJECT_CLASS(CppClass)`` … ``PY2CPP_END`` → ``{CppClass: [blob, …]}``（宏行已剔除）。"""
  lines = text.splitlines()
  blocks: dict[str, list[str]] = {}
  i = 0
  while i < len(lines):
    m = _INJECT_CLASS_RE.match(lines[i])
    if m is None:
      i += 1
      continue
    class_name = m.group(1)
    i += 1
    body_lines: list[str] = []
    while i < len(lines):
      if _END_RE.match(lines[i]):
        i += 1
        break
      body_lines.append(lines[i])
      i += 1
    else:
      raise ValueError("PY2CPP_INJECT_CLASS 缺少 PY2CPP_END")
    blob = "\n".join(body_lines).strip()
    if blob:
      blocks.setdefault(class_name, []).append(blob)
  return blocks


def _strip_ignore_regions(text: str) -> str:
  """剔除 ``PY2CPP_IGNORE`` … ``PY2CPP_END`` 块（仅 IDE/clangd 用，inject 拼接时不落盘）。"""
  lines = text.splitlines()
  out: list[str] = []
  ignoring = False
  for i, line in enumerate(lines):
    if _IGNORE_RE.match(line):
      if ignoring:
        raise ValueError(f"嵌套 PY2CPP_IGNORE（行 {i + 1}）")
      ignoring = True
      continue
    if ignoring:
      if _END_RE.match(line):
        ignoring = False
      continue
    out.append(line)
  if ignoring:
    raise ValueError("PY2CPP_IGNORE 缺少 PY2CPP_END")
  return "\n".join(out)


def _expand_scope_regions(text: str, module_rel: str | None) -> str:
  """``PY2CPP_BEGIN_SCOPE`` … ``PY2CPP_END_SCOPE`` → 按 ``module_rel`` 嵌套 ``namespace``。"""
  if not module_rel:
    if _BEGIN_SCOPE_RE.search(text):
      raise ValueError(
        "PY2CPP_BEGIN_SCOPE 无法推断模块路径；请传入 ctx module_rel"
      )
    return text
  lines = text.splitlines()
  out: list[str] = []
  i = 0
  while i < len(lines):
    if not _BEGIN_SCOPE_RE.match(lines[i]):
      out.append(lines[i])
      i += 1
      continue
    out.extend(namespace_open_lines(module_rel))
    i += 1
    body: list[str] = []
    while i < len(lines):
      if _BEGIN_SCOPE_RE.match(lines[i]):
        raise ValueError(f"嵌套 PY2CPP_BEGIN_SCOPE（行 {i + 1}）")
      if _END_SCOPE_RE.match(lines[i]):
        i += 1
        break
      body.append(lines[i])
      i += 1
    else:
      raise ValueError(f"PY2CPP_BEGIN_SCOPE（行 {i}) 缺少 PY2CPP_END_SCOPE")
    out.extend(body)
    out.extend(namespace_close_lines(module_rel))
  return "\n".join(out)


_NAMESPACE_MACRO_RE = re.compile(r"\bPY2CPP_NAMESPACE\b")


def _expand_namespace_macro(text: str, module_rel: str | None) -> str:
  """模板源 ``PY2CPP_NAMESPACE::…`` → ``py2cpp::…::…``（MSVC 展开路径；clangd 见 ``~macro`` 头）。"""
  if not _NAMESPACE_MACRO_RE.search(text):
    return text
  if not module_rel:
    raise ValueError(
      "PY2CPP_NAMESPACE 无法推断模块路径；请传入 ctx module_rel"
    )
  qual = namespace_qualifier_for_module_rel(module_rel)
  return _NAMESPACE_MACRO_RE.sub(qual, text)


def _expand_echo(text: str, ctx: dict[str, Any], helpers: dict[str, Any]) -> str:
  """``PY2CPP_ECHO(expr)`` → 构建期求值 ``expr``，将 ``str`` / ``list[str]`` 原样插入。"""

  def handler(expr: str) -> str:
    return _eval_echo_expr(expr, ctx, helpers)

  return _expand_macro_calls(text, "ECHO", handler)


def _expand_template_core(
  text: str,
  base_dir: Path,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> str:
  module_rel = ctx.get("module_rel")
  rel_str = module_rel if isinstance(module_rel, str) else None
  text = _expand_scope_regions(text, rel_str)
  text = _strip_and_register_def_blocks(text, base_dir, ctx, helpers)
  text = _expand_includes_and_exec(text, base_dir, ctx, helpers)
  text = _expand_blocks_in_text(text, ctx, helpers)
  text = _expand_echo(text, ctx, helpers)
  text = _expand_namespace_macro(text, rel_str)
  return text


def _expand_inject_class_bodies(
  text: str,
  base_dir: Path,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> str:
  """展开 ``PY2CPP_INJECT_CLASS`` 块内文本，保留宏行供 ``extract_py2cpp_inject_class_blocks``。"""
  lines = text.splitlines()
  out: list[str] = []
  i = 0
  while i < len(lines):
    if not _INJECT_CLASS_RE.match(lines[i]):
      out.append(lines[i])
      i += 1
      continue
    out.append(lines[i])
    i += 1
    body_start = i
    while i < len(lines) and not _END_RE.match(lines[i]):
      i += 1
    if i >= len(lines):
      raise ValueError("PY2CPP_INJECT_CLASS 缺少 PY2CPP_END")
    body = "\n".join(lines[body_start:i])
    if body:
      expanded = _expand_template_core(body, base_dir, ctx, helpers)
      if expanded:
        out.extend(expanded.splitlines())
    out.append(lines[i])
    i += 1
  return "\n".join(out)


def _expand_template_text(
  text: str,
  base_dir: Path,
  ctx: dict[str, Any],
  helpers: dict[str, Any],
) -> str:
  text = _strip_ignore_regions(text)
  text = _expand_inject_class_bodies(text, base_dir, ctx, helpers)
  return _expand_template_core(text, base_dir, ctx, helpers)


def _expand_standalone_eval(text: str, ctx: dict[str, Any]) -> str:
  def repl(m: re.Match[str]) -> str:
    return _eval_cpp_slot(m.group(1).strip(), ctx)

  return re.sub(r"PY2CPP_EVAL\s*\(\s*(.*?)\s*\)", repl, text)


def expand_template(
  rel: str,
  ctx: dict[str, Any] | None = None,
  *,
  apply_allman: bool = True,
  templates_root: Path | None = None,
) -> str:
  """展开 ``templates/<rel>``（``~`` 前缀文件亦可；``templates_root`` 默认可为仓库根或 ``zeus/templates``）。"""
  norm = rel.replace("\\", "/")
  root = (templates_root or _TEMPLATE_ROOT).resolve()
  path = (root / norm).resolve()
  if not str(path).startswith(str(root)):
    raise ValueError(f"模板路径越界: {rel}")
  if not path.is_file():
    raise FileNotFoundError(f"模板不存在: {rel}")
  raw_text = path.read_text(encoding="utf-8")
  _assert_no_forbidden_type_eval(raw_text, norm)
  _assert_no_forbidden_dynamic_type(raw_text, norm)
  _assert_no_forbidden_stl_containers(raw_text, norm)
  from ..constant.template_module_bindings import module_rel_from_template_rel

  inferred_rel = module_rel_from_template_rel(norm)
  helpers: dict[str, Any] = {
    "range": range,
  }
  run_ctx: dict[str, Any] = dict(ctx or {})
  for key, val in _builtin_template_ctx().items():
    run_ctx.setdefault(key, val)
  if inferred_rel and "module_rel" not in run_ctx:
    run_ctx["module_rel"] = inferred_rel
  run_ctx.update(helpers)
  expanded = _expand_template_text(raw_text, path.parent, run_ctx, helpers)
  expanded = _expand_standalone_eval(expanded, run_ctx)
  expanded = _replace_py2cpp_type(expanded)
  if apply_allman:
    expanded = kr_to_allman(expanded)
  return expanded


def expand_mirror_to_generated(
  generated_py2cpp_root: Path,
  *,
  generated_at: str = "",
  apply_allman: bool = True,
) -> list[Path]:
  """展开 ``templates/**/*.inl`` 与 ``templates/**/*.h``（跳过 ``~macro/``、``~test/``、``~`` / ``+`` / ``-`` 文件名）写入镜像。"""
  from ..constant.template_module_bindings import (
    _mirror_skip_template_name,
    _mirror_skip_template_rel,
    validate_template_module_bindings,
  )
  from .stdlib_mirror_codegen import finalize_mirror_codegen_text

  validate_template_module_bindings()
  written: list[Path] = []
  root = _TEMPLATE_ROOT.resolve()

  def _write_mirror(rel: str) -> None:
    out = generated_py2cpp_root / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    from ..constant.template_module_bindings import module_rel_from_mirror_template

    module_rel = module_rel_from_mirror_template(rel)
    expanded = expand_template(rel, apply_allman=apply_allman)
    text = finalize_mirror_codegen_text(rel, module_rel, expanded, generated_at)
    from .write_if_changed import write_text_if_changed
    write_text_if_changed(out, text)
    written.append(out)

  for path in sorted(root.rglob("*.inl")):
    rel = path.relative_to(root).as_posix()
    if _mirror_skip_template_rel(rel) or _mirror_skip_template_name(path.name):
      continue
    _write_mirror(rel)

  for path in sorted(root.rglob("*.h")):
    rel = path.relative_to(root).as_posix()
    if _mirror_skip_template_rel(rel) or _mirror_skip_template_name(path.name):
      continue
    _write_mirror(rel)

  return written


def expand_exception_pystr_ctor(name: str, *, apply_allman: bool = False) -> str | None:
  from ..constant.language import default_py_class_cpp_name

  cpp = default_py_class_cpp_name(name) if not (
    name.startswith("Py") and len(name) > 2 and name[2].isupper()
  ) else name
  if name in _EXCEPTION_PYSTR_CTOR_SKIP or cpp in _EXCEPTION_PYSTR_CTOR_SKIP:
    return None
  return expand_template(
    "core/~exception_pystr_ctor.inl",
    {"ctx_Cls": cpp, "ctx_Base": exception_pystr_ctor_base(cpp)},
    apply_allman=apply_allman,
  )


def expand_exception_repr_inl(*, apply_allman: bool = False) -> str:
  """``Exception`` 与各子类 ``__repr__`` 实现（``ExcTypeUnion`` 等 ``::repr`` 依赖）。"""
  _ = apply_allman
  ctx = _builtin_template_ctx()
  chunks: list[str] = [
    "PyStr py2cpp::core::exceptions::PyException::__repr__() const",
    "{",
    '  return PyStr("Exception()");',
    "}",
    "",
  ]
  for name in ctx["exception_type_names"]:
    chunks.extend([
      f"PyStr py2cpp::core::exceptions::{name}::__repr__() const",
      "{",
      f'  return PyStr("{name}()");',
      "}",
      "",
    ])
  text = "\n".join(chunks)
  return text
