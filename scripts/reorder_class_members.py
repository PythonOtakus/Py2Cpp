"""按 docs/编码规范.md §4.3 重排类体内成员顺序。

用法:
  python scripts/reorder_class_members.py py2cpp
  python scripts/reorder_class_members.py py2cpp/text/str.py

仅重排 ``class`` 体内部语句；模块 import、类定义先后顺序不变。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# --- Tier 4–8 dunder 子序 ---
LIFECYCLE = (
  "__new__",
  "__init__",
  "__post_init__",
  "__del__",
  "__copy__",
  "__move__",
  "__enter__",
  "__exit__",
  "__aenter__",
  "__aexit__",
)
REPR_DUNDERS = ("__str__", "__repr__", "__format__", "__bool__", "__bytes__")
CMP_DUNDERS = (
  "__cmp__",
  "__eq__",
  "__ne__",
  "__lt__",
  "__le__",
  "__gt__",
  "__ge__",
  "__hash__",
)
CONTAINER_DUNDERS = (
  "__len__",
  "__getitem__",
  "__setitem__",
  "__delitem__",
  "__contains__",
)
ITER_DUNDERS = ("__iter__", "__next__", "__reversed__")

ARITH_GROUPS = (
  ("__add__", "__radd__", "__iadd__"),
  ("__sub__", "__rsub__", "__isub__"),
  ("__mul__", "__rmul__", "__imul__"),
  ("__truediv__", "__rtruediv__", "__itruediv__"),
  ("__floordiv__", "__rfloordiv__", "__ifloordiv__"),
  ("__mod__", "__rmod__", "__imod__"),
  ("__lshift__", "__rlshift__", "__ilshift__"),
  ("__rshift__", "__rrshift__", "__irshift__"),
  ("__and__", "__rand__", "__iand__"),
  ("__or__", "__ror__", "__ior__"),
  ("__xor__", "__rxor__", "__ixor__"),
)
UNARY_DUNDERS = ("__neg__", "__pos__", "__invert__")

_DUNDER_RANK: dict[str, tuple[int, int]] = {}
for _i, _n in enumerate(LIFECYCLE):
  _DUNDER_RANK[_n] = (4, _i)
for _i, _n in enumerate(REPR_DUNDERS):
  _DUNDER_RANK[_n] = (5, _i)
for _i, _n in enumerate(CMP_DUNDERS):
  _DUNDER_RANK[_n] = (6, _i)
for _i, _n in enumerate(CONTAINER_DUNDERS):
  _DUNDER_RANK[_n] = (7, _i)
for _i, _n in enumerate(ITER_DUNDERS):
  _DUNDER_RANK[_n] = (8, _i)
for _gi, _grp in enumerate(ARITH_GROUPS):
  for _si, _n in enumerate(_grp):
    _DUNDER_RANK[_n] = (10, _gi * 10 + _si)
for _i, _n in enumerate(UNARY_DUNDERS):
  _DUNDER_RANK[_n] = (10, 1000 + _i)

# CPython 3.13 文档方法表顺序（T11）；未列出的公开方法排在表末、按源行号稳定序
CPYTHON_T11: dict[str, list[str]] = {
  "str": [
    "capitalize", "casefold", "center", "count", "encode", "endswith",
    "expandtabs", "find", "format", "format_map", "index", "isalnum",
    "isalpha", "isascii", "isdecimal", "isdigit", "isidentifier", "islower",
    "isnumeric", "isprintable", "isspace", "istitle", "isupper", "join",
    "ljust", "lower", "lstrip", "maketrans", "partition", "removeprefix",
    "removesuffix", "replace", "rfind", "rindex", "rjust", "rpartition",
    "rsplit", "rstrip", "split", "splitlines", "startswith", "strip",
    "swapcase", "title", "translate", "upper", "zfill",
  ],
  "bytes": [
    "capitalize", "center", "count", "decode", "endswith", "expandtabs",
    "find", "fromhex", "hex", "index", "isalnum", "isalpha", "isascii",
    "isdigit", "islower", "isspace", "istitle", "isupper", "join", "ljust",
    "lower", "lstrip", "maketrans", "partition", "removeprefix",
    "removesuffix", "replace", "rfind", "rindex", "rjust", "rpartition",
    "rsplit", "rstrip", "split", "splitlines", "startswith", "strip",
    "swapcase", "title", "translate", "upper", "zfill",
  ],
  "list": [
    "append", "clear", "copy", "count", "extend", "index", "insert", "pop",
    "remove", "reverse", "sort",
  ],
  "frozenlist": [
    "count", "index",
  ],
  "dict": [
    "clear", "copy", "get", "items", "keys", "pop", "popitem", "setdefault",
    "update", "values",
  ],
  "frozendict": [
    "copy", "get", "items", "keys", "values",
  ],
  "set": [
    "add", "clear", "copy", "difference", "difference_update", "discard",
    "intersection", "intersection_update", "isdisjoint", "issubset",
    "issuperset", "pop", "remove", "symmetric_difference",
    "symmetric_difference_update", "union", "update",
  ],
  "frozenset": [
    "copy", "difference", "intersection", "isdisjoint", "issubset",
    "issuperset", "symmetric_difference", "union",
  ],
  "deque": [
    "append", "appendleft", "clear", "copy", "count", "extend",
    "extendleft", "index", "insert", "pop", "popleft", "remove", "reverse",
    "rotate",
  ],
  "Path": [
    "anchor", "as_posix", "as_uri", "chmod", "cwd", "exists", "expanduser",
    "glob", "group", "hardlink_to", "home", "is_absolute", "is_block_device",
    "is_char_device", "is_dir", "is_fifo", "is_file", "is_junction",
    "is_mount", "is_reserved", "is_socket", "is_symlink", "iterdir", "joinpath",
    "lchmod", "lstat", "match", "mkdir", "open", "owner", "read_bytes",
    "read_text", "readlink", "relative_to", "rename", "replace", "resolve",
    "rglob", "rmdir", "samefile", "stat", "stem", "suffix", "symlink_to",
    "touch", "unlink", "walk", "with_name", "with_segments", "with_stem",
    "with_suffix", "write_bytes", "write_text",
  ],
  "datetime": [
    "astimezone", "combine", "ctime", "date", "day", "dst", "fold",
    "fromisocalendar", "fromisoformat", "fromordinal", "fromtimestamp",
    "hour", "isocalendar", "isoformat", "isoweekday", "microsecond", "minute",
    "month", "now", "replace", "resolution", "second", "strftime", "strptime",
    "time", "timestamp", "timetuple", "timetz", "today", "toordinal",
    "tzinfo", "tzname", "utcfromtimestamp", "utcnow", "utcoffset", "utctimetuple",
    "weekday", "year",
  ],
  "date": [
    "ctime", "day", "fromisocalendar", "fromisoformat", "fromordinal",
    "fromtimestamp", "isocalendar", "isoformat", "isoweekday", "month",
    "replace", "strftime", "strptime", "timetuple", "toordinal", "today",
    "weekday", "year",
  ],
  "time": [
    "dst", "fold", "fromisoformat", "hour", "isoformat", "isoweekday",
    "microsecond", "minute", "replace", "second", "strftime", "strptime",
    "tzinfo", "tzname", "utcoffset",
  ],
  "timedelta": [
    "total_seconds",
  ],
  "TextIOBase": ["close", "flush", "read", "readable", "readline", "readlines", "seek", "seekable", "tell", "truncate", "writable", "write", "writelines"],
  "BufferedReader": ["close", "detach", "flush", "read", "readable", "readline", "readlines", "seek", "seekable", "tell", "truncate", "writable", "write", "writelines"],
}

T11_RANK: dict[str, dict[str, int]] = {
  cls: {name: i for i, name in enumerate(names)}
  for cls, names in CPYTHON_T11.items()
}


def _ann_has_marker(ann: ast.expr | None, marker: str) -> bool:
  if ann is None:
    return False
  if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.MatMult):
    if isinstance(ann.right, ast.Name) and ann.right.id == marker:
      return True
  return False


def _is_static_or_classmethod(func: ast.FunctionDef) -> bool:
  for dec in func.decorator_list:
    if isinstance(dec, ast.Name) and dec.id in ("staticmethod", "classmethod"):
      return True
  return False


def _property_info(func: ast.FunctionDef) -> tuple[str, int] | None:
  """返回 (属性名, 0=getter/1=setter) 或 None。"""
  for dec in func.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == "property":
      return (func.name, 0)
    if isinstance(dec, ast.Attribute) and dec.attr == "setter":
      if isinstance(dec.value, ast.Name):
        return (dec.value.id, 1)
  return None


def _is_staticproperty(func: ast.FunctionDef) -> bool:
  for dec in func.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == "staticproperty":
      return True
  return False


def _dunder_tier(name: str) -> int | None:
  if name in _DUNDER_RANK:
    return _DUNDER_RANK[name][0]
  if name.startswith("__") and name.endswith("__"):
    return 10
  return None


def _stmt_tier(stmt: ast.stmt, func: ast.FunctionDef | None = None) -> int:
  if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(
    stmt.value.value, str
  ):
    return 0
  if isinstance(stmt, ast.TypeAlias):
    return 0
  if isinstance(stmt, ast.AnnAssign):
    if _ann_has_marker(stmt.annotation, "const"):
      return 1
    return 2
  if isinstance(stmt, ast.Assign):
    return 2
  if isinstance(stmt, ast.FunctionDef):
    return _function_tier(stmt)
  if isinstance(stmt, ast.Pass):
    return 12
  return 12


def _is_native_stub(func: ast.FunctionDef) -> bool:
  """``pass`` / ``...`` 体，由 C++ 注入；同 Tier 内排在已实现成员之后。"""
  body = [
    s
    for s in func.body
    if not (
      isinstance(s, ast.Expr)
      and isinstance(s.value, ast.Constant)
      and isinstance(s.value.value, str)
    )
  ]
  if not body:
    return True
  if len(body) == 1 and isinstance(body[0], ast.Pass):
    return True
  if len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(
    body[0].value, ast.Constant
  ):
    return body[0].value.value is ...
  return False


def _native_key(func: ast.FunctionDef) -> int:
  return 1 if _is_native_stub(func) else 0


def _function_tier(func: ast.FunctionDef) -> int:
  if _is_staticproperty(func):
    return 9
  pinfo = _property_info(func)
  if pinfo is not None:
    return 9
  if _is_static_or_classmethod(func):
    return 3
  dt = _dunder_tier(func.name)
  if dt is not None:
    return dt
  if func.name.startswith("_"):
    return 12
  return 11


def _function_subkey(
  func: ast.FunctionDef,
  class_name: str,
  lineno: int,
  overload_anchor: dict[str, int],
) -> tuple:
  tier = _function_tier(func)
  name = func.name

  nk = _native_key(func)

  if tier == 3:
    return (nk, 0 if not name.startswith("_") else 1, name)

  if tier == 9:
    if _is_staticproperty(func):
      return (nk, 1, name, 0)
    pinfo = _property_info(func)
    assert pinfo is not None
    return (nk, 0, pinfo[0], pinfo[1])

  if name in _DUNDER_RANK:
    return (nk, _DUNDER_RANK[name][1])

  if tier == 11:
    rank = T11_RANK.get(class_name, {}).get(name, 10_000)
    return (nk, rank, lineno)

  if tier == 12:
    return (nk, name)

  if name in overload_anchor:
    return (overload_anchor[name], nk, lineno)

  return (nk, lineno)


def _stmt_start_line(stmt: ast.stmt) -> int:
  if isinstance(stmt, ast.FunctionDef) and stmt.decorator_list:
    return stmt.decorator_list[0].lineno
  return stmt.lineno


def _stmt_source(lines: list[str], stmt: ast.stmt) -> str:
  start = _stmt_start_line(stmt)
  end = stmt.end_lineno or stmt.lineno
  return "".join(lines[start - 1 : end])


def _reorder_class_body(
  body: list[ast.stmt],
  class_name: str,
  lines: list[str],
) -> list[str]:
  if not body:
    return []

  overload_anchor: dict[str, int] = {}
  for stmt in body:
    if isinstance(stmt, ast.FunctionDef):
      if stmt.name not in overload_anchor:
        overload_anchor[stmt.name] = _stmt_start_line(stmt)

  indexed: list[tuple[tuple, int, str]] = []
  for stmt in body:
    tier = _stmt_tier(stmt)
    sub: tuple
    if isinstance(stmt, ast.FunctionDef):
      sub = _function_subkey(stmt, class_name, _stmt_start_line(stmt), overload_anchor)
    elif isinstance(stmt, ast.TypeAlias):
      if isinstance(stmt.name, ast.Name):
        sub = (stmt.name.id,)
      else:
        sub = (f"@{_stmt_start_line(stmt)}",)
    elif isinstance(stmt, ast.AnnAssign):
      if isinstance(stmt.target, ast.Name):
        sub = (stmt.target.id,)
      else:
        sub = (f"@{_stmt_start_line(stmt)}",)
    elif isinstance(stmt, ast.Assign):
      names = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
      sub = (names[0] if names else f"@{_stmt_start_line(stmt)}",)
    else:
      sub = (f"@{_stmt_start_line(stmt)}",)
    key = (tier, *sub)
    indexed.append((key, _stmt_start_line(stmt), _stmt_source(lines, stmt)))

  indexed.sort(key=lambda x: x[0])
  parts = [seg.rstrip() for _, _, seg in indexed]
  return parts


def _reorder_in_node(
  node: ast.AST,
  lines: list[str],
  chunks: list[tuple[int, int, str]],
) -> None:
  """收集 (start_line, end_line, replacement) 仅针对 class 体。"""
  if isinstance(node, ast.ClassDef):
    if node.body:
      new_parts = _reorder_class_body(node.body, node.name, lines)
      if new_parts:
        body_start = min(_stmt_start_line(s) for s in node.body)
        body_end = max((s.end_lineno or s.lineno) for s in node.body)
        replacement = "\n\n".join(new_parts) + "\n"
        chunks.append((body_start, body_end, replacement))
  for child in ast.iter_child_nodes(node):
    _reorder_in_node(child, lines, chunks)


def reorder_file(path: Path) -> bool:
  text = path.read_text(encoding="utf-8")
  try:
    tree = ast.parse(text)
  except SyntaxError as e:
    print(f"  SKIP syntax error: {path}: {e}")
    return False
  lines = text.splitlines(keepends=True)
  chunks: list[tuple[int, int, str]] = []
  _reorder_in_node(tree, lines, chunks)
  if not chunks:
    return False
  chunks.sort(key=lambda c: c[0], reverse=True)
  out_lines = list(lines)
  for start, end, replacement in chunks:
    rep_lines = replacement.splitlines(keepends=True)
    if rep_lines and not rep_lines[-1].endswith("\n"):
      rep_lines[-1] += "\n"
    out_lines[start - 1 : end] = rep_lines
  new_text = "".join(out_lines)
  if new_text != text:
    path.write_text(new_text, encoding="utf-8", newline="")
    return True
  return False


def main(argv: list[str]) -> int:
  roots = [Path(a) for a in argv] if argv else [REPO / "py2cpp"]
  changed = 0
  for root in roots:
    if not root.is_absolute():
      root = REPO / root
    files = sorted(root.rglob("*.py")) if root.is_dir() else [root]
    for path in files:
      if path.name.startswith("_") and path.parent.name == "scripts":
        continue
      if reorder_file(path):
        print(f"reordered: {path.relative_to(REPO)}")
        changed += 1
  print(f"done: {changed} file(s) updated")
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))
