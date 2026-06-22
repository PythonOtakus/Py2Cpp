"""``templates/**`` 轻量扫描（译期校验与展开器共用，不 ``exec``）。"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

_BEGIN_RE = re.compile(r"^\s*PY2CPP_BEGIN\s*\(\s*(.*?)\s*\)\s*$")
_END_RE = re.compile(r"^\s*PY2CPP_END\s*$")
_INJECT_CLASS_RE = re.compile(r"^\s*PY2CPP_INJECT_CLASS\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$")
_IGNORE_RE = re.compile(r"^\s*PY2CPP_IGNORE\s*$")
_BEGIN_SCOPE_RE = re.compile(r"^\s*PY2CPP_BEGIN_SCOPE\s*$")
_END_SCOPE_RE = re.compile(r"^\s*PY2CPP_END_SCOPE\s*$")
_INCLUDE_RE = re.compile(r"^\s*PY2CPP_INCLUDE\s*\(\s*\"([^\"]+)\"\s*\)\s*$")
_PY2CPP_INCLUDE_LINE_RE = re.compile(r'^\s*#\s*include\s*"py2cpp/')
_CTX_DEFINE_OUTSIDE_RE = re.compile(r"^\s*#\s*define\s+(ctx_[A-Za-z0-9_]+)")
_CTX_DEFINE_RE = re.compile(r"^\s*#\s*define\s+(ctx_[A-Za-z0-9_]+)")
_PY2CPP_ECHO_CTX_RE = re.compile(r"PY2CPP_ECHO\s*\(\s*(ctx_[A-Za-z0-9_]+)\s*\)")
_BEGIN_IF_CTX_RE = re.compile(r"PY2CPP_BEGIN\s*\(\s*if\s+(ctx_[A-Za-z0-9_]+)\b")
_PASCAL_SUFFIX_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_PRAGMA_ONCE_RE = re.compile(r"^\s*#\s*pragma\s+once\b", re.IGNORECASE)
_INCLUDE_GUARD_IFNDEF_RE = re.compile(
  r"^\s*#\s*ifndef\s+(PY2CPP_[A-Z0-9_]+|[A-Z][A-Z0-9_]*_(?:H|HPP|INL)\b)",
)
_INCLUDE_GUARD_DEFINE_RE = re.compile(
  r"^\s*#\s*define\s+(PY2CPP_[A-Z0-9_]+_(?:H|HPP|INL)\b|[A-Z][A-Z0-9_]*_(?:H|HPP|INL)\b)",
)
_INCLUDE_GUARD_ENDIF_RE = re.compile(
  r"^\s*#\s*endif\s*(?://|/\*)\s*(PY2CPP_[A-Z0-9_]+|[A-Z][A-Z0-9_]*_(?:H|HPP|INL))",
)
_QUALIFIED_CUT_TYPE_RE = re.compile(
  r"\bpy2cpp::(?:core|util|text)::(?:[a-z_][a-z0-9_]*::)*[A-Z][A-Za-z0-9_]*\b",
)


@dataclass(frozen=True)
class IgnoreRegion:
  start: int  # 0-based line index, inclusive
  end: int  # 0-based line index, inclusive


@dataclass(frozen=True)
class BlockSpan:
  header: str
  start: int
  end: int


def partition_ignore_regions(lines: list[str]) -> list[IgnoreRegion]:
  """``PY2CPP_IGNORE`` … ``PY2CPP_END`` 行号区间（含起止行）。"""
  regions: list[IgnoreRegion] = []
  i = 0
  while i < len(lines):
    if not _IGNORE_RE.match(lines[i]):
      i += 1
      continue
    start = i
    i += 1
    while i < len(lines) and not _END_RE.match(lines[i]):
      i += 1
    if i >= len(lines):
      regions.append(IgnoreRegion(start, len(lines) - 1))
      break
    regions.append(IgnoreRegion(start, i))
    i += 1
  return regions


def line_in_ignore(lineno: int, regions: list[IgnoreRegion]) -> bool:
  """``lineno`` 为 1-based。"""
  idx = lineno - 1
  return any(r.start <= idx <= r.end for r in regions)


def scan_begin_end_blocks(lines: list[str]) -> tuple[list[BlockSpan], list[tuple[int, str]]]:
  """扫描 ``PY2CPP_BEGIN`` 块；返回块列表与 ``(行号, 消息)`` 结构错误。"""
  blocks: list[BlockSpan] = []
  errors: list[tuple[int, str]] = []
  stack: list[tuple[str, int]] = []
  i = 0
  while i < len(lines):
    line = lines[i]
    if _IGNORE_RE.match(line):
      i += 1
      while i < len(lines) and not _END_RE.match(lines[i]):
        i += 1
      if i >= len(lines):
        errors.append((i, "PY2CPP_IGNORE 缺少 PY2CPP_END"))
        break
      i += 1
      continue
    if _INJECT_CLASS_RE.match(line):
      i += 1
      while i < len(lines) and not _END_RE.match(lines[i]):
        i += 1
      if i >= len(lines):
        errors.append((i, "PY2CPP_INJECT_CLASS 缺少 PY2CPP_END"))
        break
      i += 1
      continue
    m_begin = _BEGIN_RE.match(line)
    if m_begin:
      stack.append((m_begin.group(1), i))
      i += 1
      continue
    if _END_RE.match(line):
      if not stack:
        errors.append((i + 1, "PY2CPP_END 无匹配 PY2CPP_BEGIN"))
        i += 1
        continue
      header, start = stack.pop()
      blocks.append(BlockSpan(header, start, i))
      i += 1
      continue
    i += 1
  if stack:
    header, start = stack[-1]
    errors.append((start + 1, f"PY2CPP_BEGIN 缺少 PY2CPP_END: {header.strip()}"))
  return blocks, errors


def scan_scope_pair_errors(lines: list[str]) -> list[tuple[int, str]]:
  errors: list[tuple[int, str]] = []
  depth = 0
  for i, line in enumerate(lines):
    if _BEGIN_SCOPE_RE.match(line):
      depth += 1
      continue
    if _END_SCOPE_RE.match(line):
      if depth == 0:
        errors.append((i + 1, "PY2CPP_END_SCOPE 无匹配 PY2CPP_BEGIN_SCOPE"))
      else:
        depth -= 1
  if depth:
    errors.append((0, "PY2CPP_BEGIN_SCOPE 缺少 PY2CPP_END_SCOPE"))
  return errors


def scan_orphan_elif_else(blocks: list[BlockSpan]) -> list[tuple[int, str]]:
  """孤立 ``elif`` / ``else``（未与 ``if`` 链合并）。"""
  errors: list[tuple[int, str]] = []
  i = 0
  while i < len(blocks):
    h = blocks[i].header.strip()
    if h.startswith("if ") or h.startswith("if:"):
      j = i + 1
      while j < len(blocks):
        nh = blocks[j].header.strip()
        if nh.startswith("elif ") or nh == "else" or nh == "else:":
          j += 1
        else:
          break
      i = j
      continue
    if h.startswith("elif ") or h == "else" or h == "else:":
      errors.append((blocks[i].start + 1, f"孤立 {h.split(':')[0]}（须紧接 if/elif 链）"))
    i += 1
  return errors


def scan_def_naming(header: str, lineno: int) -> list[tuple[int, str]]:
  """``BEGIN(def fn_* (in_* …))`` 命名。"""
  text = header.strip()
  if not text.startswith("def "):
    return []
  stmt = f"{text}: pass"
  try:
    tree = ast.parse(stmt).body[0]
  except SyntaxError:
    return [(lineno, f"PY2CPP_BEGIN(def) 无法解析: {text}")]
  if not isinstance(tree, ast.FunctionDef):
    return [(lineno, f"PY2CPP_BEGIN(def) 非法: {text}")]
  errors: list[tuple[int, str]] = []
  name = tree.name
  if not name.startswith("fn_") or not _PASCAL_SUFFIX_RE.match(name[3:]):
    errors.append((lineno, f"BEGIN(def) helper 须 fn_PascalCase，当前: {name}"))
  for arg in tree.args.args:
    if not arg.arg.startswith("in_") or not _PASCAL_SUFFIX_RE.match(arg.arg[3:]):
      errors.append((lineno, f"BEGIN(def) 形参须 in_PascalCase，当前: {arg.arg}"))
  return errors


def scan_for_var_naming(header: str, lineno: int) -> list[tuple[int, str]]:
  text = header.strip()
  if not text.startswith("for "):
    return []
  m = re.match(r"for\s+(var_[A-Za-z0-9_]+)\s+in\s+", text)
  if not m:
    return []
  var = m.group(1)
  if not var.startswith("var_") or not _PASCAL_SUFFIX_RE.match(var[4:]):
    return [(lineno, f"BEGIN(for) 名称列表循环变量须 var_PascalCase，当前: {var}")]
  return []


def iter_include_refs(text: str) -> list[tuple[int, str]]:
  out: list[tuple[int, str]] = []
  for i, line in enumerate(text.splitlines(), start=1):
    m = _INCLUDE_RE.match(line)
    if m:
      out.append((i, m.group(1)))
  return out


def resolve_include_path(base_dir: Path, include_path: str, template_root: Path) -> Path | None:
  raw = include_path.replace("\\", "/")
  if "\\" in include_path:
    return None
  resolved = (base_dir / raw).resolve()
  root = template_root.resolve()
  if not str(resolved).startswith(str(root)):
    return None
  return resolved


def scan_include_guard_violations(lines: list[str]) -> list[tuple[int, str]]:
  """禁止模板内手写 include guard / ``#pragma once``（由 Python 包壳）。"""
  errors: list[tuple[int, str]] = []
  for i, line in enumerate(lines, start=1):
    if _PRAGMA_ONCE_RE.match(line):
      errors.append((i, "禁止 #pragma once；include guard 由 finalize_codegen_file_text 包壳"))
      continue
    if _INCLUDE_GUARD_IFNDEF_RE.match(line):
      errors.append((i, "禁止手写 include guard（#ifndef …）；由 Python 包壳"))
      continue
    if _INCLUDE_GUARD_DEFINE_RE.match(line):
      errors.append((i, "禁止手写 include guard（#define …_H/_INL）；由 Python 包壳"))
      continue
    if _INCLUDE_GUARD_ENDIF_RE.match(line):
      errors.append((i, "禁止手写 include guard 尾注释（#endif // …）；由 Python 包壳"))
  return errors


def scan_qualified_cut_type_violations(
  lines: list[str],
  *,
  ignore_regions: list[IgnoreRegion],
) -> list[tuple[int, str]]:
  """``core`` / ``util`` / ``text`` 域类型须 ``PY2CPP_TYPE(短名)``，勿写全限定名。"""
  errors: list[tuple[int, str]] = []
  for i, line in enumerate(lines, start=1):
    if line_in_ignore(i, ignore_regions):
      continue
    m = _QUALIFIED_CUT_TYPE_RE.search(line)
    if m is None:
      continue
    errors.append((
      i,
      f"禁止全限定类型 {m.group(0)}；请用 PY2CPP_TYPE(短名)",
    ))
  return errors


def ctx_key_has_pascal_suffix(key: str) -> bool:
  """``ctx_`` 后须 PascalCase（与 ``fn_``/``var_`` 后缀规则一致）。"""
  return key.startswith("ctx_") and bool(_PASCAL_SUFFIX_RE.match(key[4:]))


def _iter_ctx_key_refs_on_line(line: str) -> list[str]:
  """行内 ``#define ctx_*``、``PY2CPP_ECHO(ctx_*)``、``BEGIN(if ctx_*)`` 键名。"""
  keys: list[str] = []
  m = _CTX_DEFINE_RE.match(line)
  if m:
    keys.append(m.group(1))
  keys.extend(m.group(1) for m in _PY2CPP_ECHO_CTX_RE.finditer(line))
  keys.extend(m.group(1) for m in _BEGIN_IF_CTX_RE.finditer(line))
  return keys


def _line_is_comment_only(line: str) -> bool:
  s = line.lstrip()
  return s.startswith("//") or s.startswith("/*") or s.startswith("*")


def scan_ctx_key_naming_violations(lines: list[str]) -> list[tuple[int, str]]:
  """``ctx_*`` 键须 ``ctx_`` + PascalCase（``#define`` / ``ECHO`` / ``BEGIN(if)``）。"""
  errors: list[tuple[int, str]] = []
  reported: set[tuple[int, str]] = set()
  for i, line in enumerate(lines, start=1):
    for key in _iter_ctx_key_refs_on_line(line):
      if ctx_key_has_pascal_suffix(key):
        continue
      item = (i, key)
      if item in reported:
        continue
      reported.add(item)
      errors.append((
        i,
        f"ctx 键须 ctx_PascalCase，当前: {key}",
      ))
  return errors


def scan_ctx_ignore_echo_set_violations(
  lines: list[str],
  *,
  ignore_regions: list[IgnoreRegion],
) -> list[tuple[int, str]]:
  """IGNORE ``#define ctx_*`` 与 ``PY2CPP_ECHO(ctx_*)`` 键集合须一致（双向）。"""
  defined: dict[str, int] = {}
  for i, line in enumerate(lines, start=1):
    if not line_in_ignore(i, ignore_regions):
      continue
    m = _CTX_DEFINE_RE.match(line)
    if m:
      defined[m.group(1)] = i

  echo: set[str] = set()
  errors: list[tuple[int, str]] = []
  echo_missing_reported: set[tuple[int, str]] = set()
  for i, line in enumerate(lines, start=1):
    if line_in_ignore(i, ignore_regions) or _line_is_comment_only(line):
      continue
    for m in _PY2CPP_ECHO_CTX_RE.finditer(line):
      key = m.group(1)
      echo.add(key)
      if key in defined:
        continue
      item = (i, key)
      if item in echo_missing_reported:
        continue
      echo_missing_reported.add(item)
      errors.append((
        i,
        f"PY2CPP_ECHO({key}) 须在 PY2CPP_IGNORE 内 #define {key}",
      ))

  orphan_reported: set[str] = set()
  for key, lineno in sorted(defined.items(), key=lambda kv: kv[1]):
    if key in echo or key in orphan_reported:
      continue
    orphan_reported.add(key)
    errors.append((
      lineno,
      f"PY2CPP_IGNORE 内 #define {key} 未在模板中使用 PY2CPP_ECHO({key})",
    ))
  return errors


def scan_ctx_echo_missing_define_violations(
  lines: list[str],
  *,
  ignore_regions: list[IgnoreRegion],
) -> list[tuple[int, str]]:
  """兼容别名；见 ``scan_ctx_ignore_echo_set_violations``。"""
  return scan_ctx_ignore_echo_set_violations(
    lines,
    ignore_regions=ignore_regions,
  )


def scan_inject_ignore_violations(
  lines: list[str],
  *,
  check_py2cpp_include: bool,
  check_ctx_define: bool,
) -> list[tuple[int, str]]:
  """``+/-`` inject：``py2cpp`` include 与 ``ctx_*`` define 须在 IGNORE 内。"""
  regions = partition_ignore_regions(lines)
  errors: list[tuple[int, str]] = []
  for i, line in enumerate(lines, start=1):
    if check_py2cpp_include and _PY2CPP_INCLUDE_LINE_RE.match(line):
      if not line_in_ignore(i, regions):
        errors.append((i, 'paste inject 模板须在 PY2CPP_IGNORE 内 #include "py2cpp/…"'))
    if check_ctx_define:
      m = _CTX_DEFINE_OUTSIDE_RE.match(line)
      if m and not line_in_ignore(i, regions):
        errors.append((i, f"paste inject 模板须在 PY2CPP_IGNORE 内 #define {m.group(1)}"))
  return errors


_CLASS_SHELL_OPEN_RE = re.compile(
  r"(?:^|\n)\s*(?:template\s*<[^>]+>\s*)?class\s+(\w+)\s*(?::[^{]*)?\s*\{",
  re.MULTILINE,
)
_CLOSE_SHELL_RE = re.compile(r"^\s*\};\s*(?://.*)?$")
_NAMESPACE_PY2CPP_RE = re.compile(r"\bnamespace\s+py2cpp\b")


def _line_index_of_char_offset(lines: list[str], offset: int) -> int:
  pos = 0
  for i, line in enumerate(lines):
    next_pos = pos + len(line) + 1
    if offset < next_pos:
      return i
    pos = next_pos
  return len(lines) - 1


def _find_class_shell_open(
  lines: list[str],
  region_start: int,
  region_end: int,
) -> tuple[str, int] | None:
  """IGNORE 区间内 ``class C … {``（跳过 ``class C;`` 前向声明）。"""
  chunk = "\n".join(lines[region_start:region_end + 1])
  matches = list(_CLASS_SHELL_OPEN_RE.finditer(chunk))
  if not matches:
    return None
  m = matches[-1]
  lineno = _line_index_of_char_offset(lines[region_start:region_end + 1], m.start(1))
  return m.group(1), region_start + lineno + 1


def _ignore_region_before_line(
  lines: list[str],
  before_idx: int,
) -> tuple[int, int] | None:
  """``before_idx``（0-based）之前、以 ``PY2CPP_END`` 结束的最近 IGNORE 区间。"""
  i = before_idx - 1
  while i >= 0:
    if _END_RE.match(lines[i]):
      end_idx = i
      j = i - 1
      while j >= 0 and not _IGNORE_RE.match(lines[j]):
        if _INJECT_CLASS_RE.match(lines[j]) or _BEGIN_RE.match(lines[j]):
          return None
        j -= 1
      if j < 0 or not _IGNORE_RE.match(lines[j]):
        return None
      return j, end_idx - 1
    i -= 1
  return None


def _find_shell_close_after(lines: list[str], after_idx: int) -> int | None:
  """``after_idx``（0-based，``PY2CPP_END`` 行）之后须 ``PY2CPP_IGNORE`` + ``};``。"""
  i = after_idx + 1
  n = len(lines)
  while i < n:
    if _INJECT_CLASS_RE.match(lines[i]) or _BEGIN_RE.match(lines[i]):
      return None
    if _IGNORE_RE.match(lines[i]):
      j = i + 1
      while j < n and not _END_RE.match(lines[j]):
        if _CLOSE_SHELL_RE.match(lines[j]):
          return j + 1
        if lines[j].strip() and not lines[j].strip().startswith("//"):
          stripped = lines[j].strip()
          if stripped != "}" and not stripped.startswith("} //"):
            pass
        j += 1
      return None
    if lines[i].strip():
      if _CLOSE_SHELL_RE.match(lines[i]):
        return i + 1
      break
    i += 1
  return None


def scan_inject_class_shell_violations(lines: list[str]) -> list[tuple[int, str]]:
  """``+<stem>.h``：``IGNORE`` 类壳 + ``INJECT_CLASS(C)`` + ``IGNORE };`` 结构（T22）。"""
  errors: list[tuple[int, str]] = []
  if not lines:
    errors.append((1, "+*.h inject 模板不能为空"))
    return errors
  if not _IGNORE_RE.match(lines[0]):
    errors.append((1, "+*.h inject 模板须以 PY2CPP_IGNORE 开头"))

  outer_text = "\n".join(lines)
  if not _NAMESPACE_PY2CPP_RE.search(outer_text):
    errors.append((1, "+*.h inject 模板须在 IGNORE 内声明 namespace py2cpp"))

  inject_spans: list[tuple[int, str, int]] = []
  i = 0
  n = len(lines)
  while i < n:
    m = _INJECT_CLASS_RE.match(lines[i])
    if not m:
      i += 1
      continue
    class_name = m.group(1)
    inject_start = i
    i += 1
    while i < n and not _END_RE.match(lines[i]):
      i += 1
    if i >= n:
      errors.append((inject_start + 1, f"PY2CPP_INJECT_CLASS({class_name}) 缺少 PY2CPP_END"))
      return errors
    inject_end = i
    inject_spans.append((inject_start, class_name, inject_end))
    i += 1

  if not inject_spans:
    errors.append((1, "+*.h inject 模板须至少一处 PY2CPP_INJECT_CLASS"))
    return errors

  unit_start = 0
  while unit_start < len(inject_spans):
    unit_end = unit_start
    shell_class = inject_spans[unit_start][1]
    while (
      unit_end + 1 < len(inject_spans)
      and inject_spans[unit_end + 1][1] == shell_class
    ):
      unit_end += 1

    first_inject_line, _, _ = inject_spans[unit_start]
    _, _, last_inject_end = inject_spans[unit_end]
    region = _ignore_region_before_line(lines, first_inject_line)
    if region is None:
      errors.append((
        first_inject_line + 1,
        f"PY2CPP_INJECT_CLASS({shell_class}) 前须有 IGNORE 内 class {shell_class} {{ … PY2CPP_END",
      ))
    else:
      found = _find_class_shell_open(lines, region[0], region[1])
      if found is None:
        errors.append((
          region[0] + 1,
          f"IGNORE 类壳须 class {shell_class} {{ …（允许 template<…> / 基类）",
        ))
      elif found[0] != shell_class:
        errors.append((
          first_inject_line + 1,
          f"PY2CPP_INJECT_CLASS({shell_class}) 与类壳 class {found[0]} 不一致",
        ))

    for idx in range(unit_start, unit_end + 1):
      _, name, _ = inject_spans[idx]
      if name != shell_class:
        errors.append((
          inject_spans[idx][0] + 1,
          f"同壳内 PY2CPP_INJECT_CLASS 须同名 {shell_class}，当前: {name}",
        ))

    close_line = _find_shell_close_after(lines, last_inject_end)
    if close_line is None:
      errors.append((
        last_inject_end + 1,
        f"PY2CPP_INJECT_CLASS({shell_class}) 后须有 PY2CPP_IGNORE … }}; … PY2CPP_END 闭合类壳",
      ))

    unit_start = unit_end + 1

  return errors
