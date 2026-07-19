"""用户模块路径 → C++ ``namespace`` 嵌套（对齐 ``a/b/c.py`` / ``__init__.py`` 目录语义）。"""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..translator import Translator

from ..constant.namespace import (
  BUILTIN_NAMESPACE_SEGMENT_OVERRIDES,
  INIT_SEGMENT,
  MODULES_WITHOUT_CPP_NAMESPACE_REL,
)
from ..constant.stdlib_layout import stdlib_module_path

MODULES_WITHOUT_CPP_NAMESPACE: frozenset[str] = frozenset(
  stdlib_module_path(m) for m in MODULES_WITHOUT_CPP_NAMESPACE_REL
)


def cpp_namespace_segment(segment: str) -> str:
  """路径段 → 合法 C++ 命名空间标识符。"""
  if segment in BUILTIN_NAMESPACE_SEGMENT_OVERRIDES:
    return BUILTIN_NAMESPACE_SEGMENT_OVERRIDES[segment]
  if segment == INIT_SEGMENT:
    return INIT_SEGMENT
  out: list[str] = []
  for ch in segment:
    if ch.isalnum() or ch == "_":
      out.append(ch)
    else:
      out.append("_")
  name = "".join(out)
  return name or "_"


def module_path_namespace_segments(module_path: str) -> list[str]:
  """``import_tests/helper`` → ``['import_tests', 'helper']``；``ffi/sqlite/sqlite3`` → ``['ffi','sqlite','lib']``。"""
  path = module_path.replace("\\", "/").strip("/")
  if not path:
    return []
  from ..constant.ffi_layout import ffi_cpp_namespace_segment, is_ffi_module_path

  parts = path.split("/")
  if is_ffi_module_path(path):
    return [cpp_namespace_segment(ffi_cpp_namespace_segment(p)) for p in parts]
  return [cpp_namespace_segment(p) for p in parts]


def namespace_qualifier_from_segments(segments: list[str]) -> str:
  if not segments:
    return ""
  return "::".join(segments)


def namespace_qualifier_for_module(module_path: str) -> str:
  norm = module_path.replace("\\", "/")
  from ..constant.stdlib_layout import RUNTIME_PKG

  if norm == f"{RUNTIME_PKG}/builtins":
    return RUNTIME_PKG
  if norm in MODULES_WITHOUT_CPP_NAMESPACE:
    return ""
  return namespace_qualifier_from_segments(module_path_namespace_segments(module_path))


def inl_namespace_segments(module_path: str) -> list[str]:
  """``.inl`` 实现作用域：用户模块套 ``namespace``；运行时用全局全限定名。

  MSVC 在多个 ``namespace py2cpp { }`` 块（各子模块 ``.inl``）之后无法正确解析
  ``py2cpp::PyRange`` 等包根符号，故 ``py2cpp`` 及 ``py2cpp/…`` 下所有 ``.inl`` 均不套命名空间。
  FFI（``ffi/…``）``.inl`` 同样不套命名空间，实现用全限定 ``ffi::…``。
  """
  from ..constant.ffi_layout import is_ffi_module_path
  from ..constant.stdlib_layout import RUNTIME_PKG

  norm = module_path.replace("\\", "/")
  if norm == RUNTIME_PKG or norm.startswith(f"{RUNTIME_PKG}/"):
    return []
  if is_ffi_module_path(norm):
    return []
  return module_path_namespace_segments(module_path)


def qualify_symbol_in_module(module_path: str, bare: str) -> str:
  """模块内符号的全局限定名（用于跨模块引用）。"""
  q = namespace_qualifier_for_module(module_path)
  return f"{q}::{bare}" if q else bare


def qualify_base_in_module(derived_module: str, base_module: str, base_name: str) -> str:
  """在 ``derived_module`` 的类声明里书写基类名（同模块短名，否则相对兄弟命名空间）。"""
  from_segs = module_path_namespace_segments(derived_module)
  to_segs = module_path_namespace_segments(base_module)
  common = 0
  while (
    common < len(from_segs)
    and common < len(to_segs)
    and from_segs[common] == to_segs[common]
  ):
    common += 1
  rel = "::".join(to_segs[common:])
  if rel:
    return f"{rel}::{base_name}"
  return base_name


def using_namespace_line(qualifier: str) -> str:
  return f"using namespace {qualifier};"


def using_symbol_line(qualifier: str, symbol: str) -> str:
  # 嵌套 ``namespace py2cpp`` 内 ``using py2cpp::PyRange`` 须 ``::`` 前缀，否则 MSVC 绑到未完成的同名外层块。
  return f"using ::{qualifier}::{symbol};"


def _body_is_only_import_usings(body: list[str]) -> bool:
  """块内除空白与 ``using`` 外无其它语句时视为可省略（汇总 ``.cpp`` 顶部已有 ``using namespace``）。"""
  for line in body:
    stripped = line.strip()
    if not stripped:
      continue
    if stripped.startswith("using ") and stripped.endswith(";"):
      continue
    return False
  return True


def _strip_blank_lines(lines: list[str]) -> list[str]:
  start = 0
  end = len(lines)
  while start < end and not lines[start].strip():
    start += 1
  while end > start and not lines[end - 1].strip():
    end -= 1
  return lines[start:end]


def _try_parse_allman_namespace_block(
  lines: list[str], start: int
) -> tuple[list[str], list[str], int] | None:
  """解析生成器输出的 Allman ``namespace`` 块（以 ``} // namespace`` 闭合）。"""
  i = start
  n = len(lines)
  if i >= n:
    return None
  segments: list[str] = []
  while True:
    seg_line = lines[i].strip()
    if not seg_line.startswith("namespace "):
      return None
    segments.append(seg_line[len("namespace ") :].strip())
    i += 1
    if i >= n or lines[i].strip() != "{":
      return None
    i += 1
    if i < n and lines[i].strip().startswith("namespace "):
      continue
    break
  body: list[str] = []
  for close_seg in reversed(segments):
    close = f"}} // namespace {close_seg}"
    while i < n:
      if lines[i].strip() == close:
        i += 1
        break
      body.append(lines[i])
      i += 1
    else:
      return None
  return segments, body, i


def format_allman_namespace_block(segments: list[str], body: list[str]) -> list[str]:
  """按 ``use_cpp_namespaces`` 相同版式输出嵌套 ``namespace``。"""
  if not segments:
    return list(body)
  out: list[str] = []
  indent = 0
  for seg in segments:
    out.append(f"{'  ' * indent}namespace {seg}")
    out.append(f"{'  ' * indent}{{")
    indent += 1
  for line in body:
    out.append(line)
  for seg in reversed(segments):
    indent -= 1
    out.append(f"{'  ' * indent}}} // namespace {seg}")
  return out


def innermost_namespace_close_index(lines: list[str]) -> int | None:
  """返回首个 ``} // namespace`` 行下标（最内层闭合）。"""
  for i, line in enumerate(lines):
    if line.strip().startswith("} // namespace"):
      return i
  return None


def splice_before_innermost_namespace_close(
  body: list[str],
  insert: list[str],
) -> list[str]:
  """在 Allman 嵌套块的最内层 ``} // namespace`` 之前插入行。"""
  if not insert:
    return body
  close_idx = innermost_namespace_close_index(body)
  if close_idx is None:
    if body and body[-1].strip():
      return body + ["", *insert]
    return body + insert
  prefix = body[:close_idx]
  if prefix and prefix[-1].strip():
    prefix.append("")
  return prefix + insert + body[close_idx:]


def merge_consecutive_namespace_blocks(lines: list[str]) -> list[str]:
  """合并相邻、同路径的 ``namespace`` 块，并丢弃空块。"""
  out: list[str] = []
  i = 0
  n = len(lines)
  while i < n:
    parsed = _try_parse_allman_namespace_block(lines, i)
    if parsed is None:
      out.append(lines[i])
      i += 1
      continue
    segments, body, i = parsed
    merged = list(body)
    while i < n:
      nxt = _try_parse_allman_namespace_block(lines, i)
      if nxt is None or nxt[0] != segments:
        break
      merged.extend(nxt[1])
      i = nxt[2]
    merged = _strip_blank_lines(merged)
    if merged and not _body_is_only_import_usings(merged):
      if out and out[-1].strip():
        out.append("")
      out.extend(format_allman_namespace_block(segments, merged))
  return out


@contextmanager
def use_cpp_namespaces(tr: Translator, segments: list[str]):
  """Allman：``namespace x`` 与 ``{`` 分行；逐层缩进。"""
  if not segments:
    yield
    return
  prev_depth = len(tr._cpp_namespace_stack)
  opened: list[str] = []
  for seg in segments:
    tr.write_line(f"namespace {seg}")
    tr.write_line("{")
    tr.indent_level += 1
    opened.append(seg)
    tr._cpp_namespace_stack.append(seg)
  try:
    yield
  finally:
    for seg in reversed(opened):
      tr.indent_level -= 1
      tr.write_line(f"}} // namespace {seg}")
    tr._cpp_namespace_stack = tr._cpp_namespace_stack[:prev_depth]
