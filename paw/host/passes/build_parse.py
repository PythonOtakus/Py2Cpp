"""Build DSL 字符串 → ``BuildPlan`` IR（``Type.build("…")`` / ``list[T].build("…")`` 译期专用）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass

BUILD_INDEX_PREFIX = "_bidx_"


class BuildParseError(ValueError):
  """build 串语法错误。"""


@dataclass(frozen=True)
class LiteralValue:
  kind: str
  value: object


@dataclass(frozen=True)
class ExprValue:
  src: str
  expr: ast.expr
  index_refs: frozenset[str]


@dataclass(frozen=True)
class IndexRefValue:
  name: str


BuildValue = LiteralValue | ExprValue | IndexRefValue


@dataclass(frozen=True)
class AssignSegment:
  field: str
  value: BuildValue


@dataclass(frozen=True)
class StructDescentSegment:
  field: str
  body: BuildBody


@dataclass(frozen=True)
class ListDescentSegment:
  field: str
  count: int
  index_bind: str | None
  body: BuildBody


BuildSegment = AssignSegment | StructDescentSegment | ListDescentSegment


@dataclass(frozen=True)
class BuildBody:
  segments: tuple[BuildSegment, ...]


@dataclass(frozen=True)
class ListRootPlan:
  count: int
  index_bind: str | None
  body: BuildBody


@dataclass(frozen=True)
class StructRootPlan:
  body: BuildBody


BuildPlan = ListRootPlan | StructRootPlan


def _skip_ws(path: str, i: int) -> int:
  while i < len(path) and path[i].isspace():
    i += 1
  return i


def _read_ident(path: str, i: int) -> tuple[str, int]:
  start = i
  if i >= len(path) or not (path[i].isalpha() or path[i] == "_"):
    raise BuildParseError(f"期望标识符，位于: {path[i:]!r}")
  i += 1
  while i < len(path) and (path[i].isalnum() or path[i] == "_"):
    i += 1
  return path[start:i], i


def _read_uint(path: str, i: int) -> tuple[int, int]:
  i = _skip_ws(path, i)
  if i >= len(path) or not path[i].isdigit():
    raise BuildParseError(f"期望非负整数，位于: {path[i:]!r}")
  start = i
  while i < len(path) and path[i].isdigit():
    i += 1
  return int(path[start:i]), i


def _read_int(path: str, i: int) -> tuple[int, int]:
  i = _skip_ws(path, i)
  sign = 1
  if i < len(path) and path[i] == "-":
    sign = -1
    i += 1
  start = i
  if i >= len(path) or not path[i].isdigit():
    raise BuildParseError(f"期望整数，位于: {path[i:]!r}")
  while i < len(path) and path[i].isdigit():
    i += 1
  return sign * int(path[start:i]), i


def _read_string_literal(path: str, i: int) -> tuple[str, int]:
  if i >= len(path) or path[i] not in ("'", '"'):
    raise BuildParseError(f"期望字符串字面量，位于: {path[i:]!r}")
  quote = path[i]
  i += 1
  chars: list[str] = []
  while i < len(path):
    ch = path[i]
    if ch == "\\":
      i += 1
      if i >= len(path):
        raise BuildParseError("字符串转义不完整")
      esc = path[i]
      if esc == "n":
        chars.append("\n")
      elif esc == "t":
        chars.append("\t")
      elif esc == "r":
        chars.append("\r")
      elif esc in ("'", '"', "\\"):
        chars.append(esc)
      else:
        raise BuildParseError(f"不支持的字符串转义 \\{esc!r}")
      i += 1
      continue
    if ch == quote:
      return "".join(chars), i + 1
    chars.append(ch)
    i += 1
  raise BuildParseError("字符串字面量缺少结束引号")


def _desugar_expr_index_refs(src: str) -> tuple[str, frozenset[str]]:
  out: list[str] = []
  refs: set[str] = set()
  i = 0
  n = len(src)
  in_str: str | None = None
  escape = False
  while i < n:
    ch = src[i]
    if in_str is not None:
      out.append(ch)
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      i += 1
      continue
    if ch in ("'", '"'):
      in_str = ch
      out.append(ch)
      i += 1
      continue
    if ch == "$":
      i += 1
      name, i = _read_ident(src, i)
      refs.add(name)
      out.append(f"{BUILD_INDEX_PREFIX}{name}")
      continue
    out.append(ch)
    i += 1
  return "".join(out), frozenset(refs)


def _parse_brace_expr(path: str, i: int) -> tuple[ExprValue, int]:
  assert path[i] == "{"
  depth = 0
  start = i + 1
  j = i
  in_str: str | None = None
  escape = False
  while j < len(path):
    ch = path[j]
    if in_str is not None:
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      j += 1
      continue
    if ch in ("'", '"'):
      in_str = ch
      j += 1
      continue
    if ch == "{":
      depth += 1
    elif ch == "}":
      depth -= 1
      if depth == 0:
        expr_src = path[start:j]
        desugared, index_refs = _desugar_expr_index_refs(expr_src)
        try:
          tree = ast.parse(desugared, mode="eval")
        except SyntaxError as e:
          raise BuildParseError(f"表达式语法错误: {e}") from e
        return ExprValue(expr_src, tree.body, index_refs), j + 1
    j += 1
  raise BuildParseError("表达式缺少 '}'")


def _parse_value(path: str, i: int) -> tuple[BuildValue, int]:
  i = _skip_ws(path, i)
  if i >= len(path):
    raise BuildParseError("缺少赋值右值")
  ch = path[i]
  if ch == "{":
    expr, i = _parse_brace_expr(path, i)
    return expr, i
  if ch == "$":
    name, i = _read_ident(path, i + 1)
    return IndexRefValue(name), i
  if ch in ("'", '"'):
    s, i = _read_string_literal(path, i)
    return LiteralValue("str", s), i
  if ch.isdigit() or ch == "-":
    n, i = _read_int(path, i)
    return LiteralValue("int", n), i
  name, ni = _read_ident(path, i)
  if name == "True":
    return LiteralValue("bool", True), ni
  if name == "False":
    return LiteralValue("bool", False), ni
  if name == "None":
    return LiteralValue("none", None), ni
  raise BuildParseError(f"无法解析赋值右值，位于: {path[i:]!r}")


def _parse_index_bind(path: str, i: int) -> tuple[str | None, int]:
  i = _skip_ws(path, i)
  if i >= len(path) or path[i] != ":":
    return None, i
  j = _skip_ws(path, i + 1)
  if j >= len(path) or path[j] != "$":
    raise BuildParseError(f"期望 ': $ident' 下标绑定，位于: {path[i:]!r}")
  name, j = _read_ident(path, j + 1)
  return name, j


def _parse_list_count_bracket(path: str, i: int) -> tuple[int, str | None, int]:
  if i >= len(path) or path[i] != "[":
    raise BuildParseError(f"期望 '[:N]'，位于: {path[i:]!r}")
  i += 1
  i = _skip_ws(path, i)
  if i >= len(path) or path[i] != ":":
    raise BuildParseError(
      "build list 段首版仅支持 [:N]；单下标 field[0] > 不支持",
    )
  count, i = _read_uint(path, i + 1)
  i = _skip_ws(path, i)
  if i >= len(path) or path[i] != "]":
    raise BuildParseError("缺少 ']'")
  i += 1
  index_bind, i = _parse_index_bind(path, i)
  i = _skip_ws(path, i)
  if i >= len(path) or path[i] != ">":
    raise BuildParseError("list 段缺少 '>'")
  return count, index_bind, i + 1


def _parse_body(path: str, i: int, end: int) -> tuple[BuildBody, int]:
  segments: list[BuildSegment] = []
  i = _skip_ws(path, i)
  while i < end:
    seg, i = _parse_segment(path, i, end)
    segments.append(seg)
    i = _skip_ws(path, i)
    if i >= end:
      break
    if path[i] != ",":
      raise BuildParseError(f"段须以 ',' 分隔，位于: {path[i:]!r}")
    i = _skip_ws(path, i + 1)
  if not segments and end > 0:
    pass
  return BuildBody(tuple(segments)), i


def _parse_segment(path: str, i: int, end: int) -> tuple[BuildSegment, int]:
  i = _skip_ws(path, i)
  if i >= end:
    raise BuildParseError("段不能为空")
  field, i = _read_ident(path, i)
  i = _skip_ws(path, i)
  if i < end and path[i] == "=":
    value, i = _parse_value(path, i + 1)
    return AssignSegment(field, value), i
  if i < end and path[i] == "[":
    count, index_bind, i = _parse_list_count_bracket(path, i)
    body, i = _parse_body(path, i, end)
    return ListDescentSegment(field, count, index_bind, body), i
  if i < end and path[i] == ">":
    body, i = _parse_body(path, i + 1, end)
    return StructDescentSegment(field, body), i
  raise BuildParseError(f"无法解析段 {field!r}，位于: {path[i:end]!r}")


def _parse_list_root(path: str) -> ListRootPlan:
  i = 0
  count, index_bind, i = _parse_list_count_bracket(path, 0)
  body, i = _parse_body(path, i, len(path))
  i = _skip_ws(path, i)
  if i < len(path):
    raise BuildParseError(f"list 根 build 串尾部多余: {path[i:]!r}")
  return ListRootPlan(count, index_bind, body)


def _parse_struct_root(path: str) -> StructRootPlan:
  body, i = _parse_body(path, 0, len(path))
  i = _skip_ws(path, i)
  if i < len(path):
    raise BuildParseError(f"build 串尾部多余: {path[i:]!r}")
  return StructRootPlan(body)


def parse_build_literal(value: object, *, list_root: bool) -> BuildPlan:
  if not isinstance(value, str):
    raise BuildParseError("build 串须为字符串字面量")
  path = value.strip()
  if not path:
    raise BuildParseError("build 串不能为空")
  if list_root:
    if not path.startswith("["):
      raise BuildParseError("list[T].build 串首须为 [:N] > …")
    return _parse_list_root(path)
  if path.startswith("[:"):
    raise BuildParseError("struct build 串不得以 [:N] > 开头")
  return _parse_struct_root(path)
