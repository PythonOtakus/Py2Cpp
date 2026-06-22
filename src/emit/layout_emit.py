"""``generated/runtime`` 与各模块 ``.h`` / ``.inl`` 写盘（自 ``translator.py`` 拆出）。"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..analysis.ir import ModuleAnalysis, codegen_file_header_lines
from ..analysis.module_namespace import (
  merge_consecutive_namespace_blocks,
  namespace_qualifier_for_module,
  splice_before_innermost_namespace_close,
  using_namespace_line,
  using_symbol_line,
)
from ..codegen.expand_py2cpp_template import expand_template
from ..codegen.stdlib_mirror_codegen import expand_whole_file_template
from ..codegen.umbrella_gen import build_py2cpp_umbrella_header
from ..constant.stdlib_layout import RUNTIME_PKG, RUNTIME_BUILTINS_MODULE, stdlib_header_include, stdlib_module_path
from ..codegen.stdlib_mirror_codegen import write_stdlib_codegen_header, write_stdlib_codegen_inl
from ..constant.stdlib_discovery import STDLIB_REL_PATHS
from .layout_config_emit import (
  _HEADER_INL_BEFORE_NS_CLOSE,
  _HEADER_SKIP_INL_IN_MODULE_H,
  _HEADER_SKIP_OPERATORS_BEFORE_INL,
  _HEADER_TAIL_SKIP_UMBRELLA,
  _INL_EXTRA_OPERATORS_INL,
  _INL_SKIP_OPERATORS_H,
  _INL_SKIP_UMBRELLA,
  _JSON_API_EXTRA_HEADER_INCLUDES,
  _JSON_API_MODULE,
  _PROTOCOL_TRAITS_MODULE,
  PROTOCOL_TRAITS_GUARD,
  PROTOCOL_TRAITS_HEADER,
  RUNTIME_CPP,
  RUNTIME_PREFIX,
  UMBRELLA_HEADER,
  module_inl_extra_include_lines,
)

if TYPE_CHECKING:
  from ..translator import Translator

_ITER_RESULT_MODULE = stdlib_module_path("core/iter_result")


def module_path_to_guard(module_path: str) -> str:
  parts: list[str] = []
  for seg in module_path.replace("\\", "/").strip("/").split("/"):
    if not seg:
      continue
    name = seg.removesuffix(".py")
    if name.startswith("_"):
      name = name[1:]
    parts.append(name.upper())
  return "_".join(parts) + "_H" if parts else "PY2CPP_H"


def include_line_to_header_path(line: str) -> str | None:
  s = line.strip()
  if s.startswith('#include "') and s.endswith('"'):
    return s[len('#include "') : -1]
  return None


def format_include_line(inc: str) -> str:
  if len(inc) >= 2 and inc[0] == "<" and inc[-1] == ">":
    return f"#include {inc}"
  return f'#include "{inc}"'


def insert_inl_before_namespace_close(
  body: list[str], module_path: str, insert_lines: list[str]
) -> list[str]:
  if not insert_lines:
    return body
  q = namespace_qualifier_for_module(module_path)
  segs = q.split("::") if q else module_path_namespace_segments(module_path)
  if not segs:
    return [*body, *insert_lines]
  target = f"}} // namespace {segs[-1]}"
  for i in range(len(body) - 1, -1, -1):
    if body[i].strip() == target:
      return [*body[:i], *insert_lines, "", *body[i:]]
  return [*body, *insert_lines]


def split_protocol_header_lines(lines: list[str]) -> tuple[list[str], list[str]]:
  for i, line in enumerate(lines):
    if line.startswith("/// 常用") and "@protocol" in line:
      return lines[:i], lines[i:]
  return lines, []


def runtime_cpp_using_lines(tr: Translator) -> list[str]:
  out: list[str] = []
  for name in tr.stdlib_modules_for_umbrella:
    mp = stdlib_module_path(name)
    q = namespace_qualifier_for_module(mp)
    if q:
      out.append(using_namespace_line(q))
  return out


def write_primitive_type_headers(tr: Translator) -> None:
  note = f"{RUNTIME_PREFIX}/__init__.py"
  for rel, template_rel in (
    (f"{RUNTIME_PREFIX}/char", "char.h"),
    (f"{RUNTIME_PREFIX}/byte", "byte.h"),
    (f"{RUNTIME_PREFIX}/c_str", "c_str.h"),
    (f"{RUNTIME_PREFIX}/py_types", "py_types.h"),
    (f"{RUNTIME_PREFIX}/member_access", "member_access.h"),
  ):
    hpath = tr._stdlib_artifact_path(rel, ".h")
    hpath.parent.mkdir(parents=True, exist_ok=True)
    hpath.write_text(
      expand_whole_file_template(
        template_rel,
        tr.generated_at,
        {"source_note": note},
        apply_allman=template_rel != "member_access.h",
      ).strip(),
      encoding="utf-8",
    )
  ops_rel = f"{RUNTIME_PREFIX}/operators"
  ops_h = tr._stdlib_artifact_path(ops_rel, ".h")
  ops_h.parent.mkdir(parents=True, exist_ok=True)
  ops_h.write_text(
    expand_whole_file_template(
      "operators.h",
      tr.generated_at,
      {"source_note": note},
      apply_allman=True,
    ).strip(),
    encoding="utf-8",
  )
  op_inl = tr._stdlib_artifact_path(ops_rel, ".inl")
  op_inl.write_text(
    expand_whole_file_template(
      "operators.inl",
      tr.generated_at,
      {},
      apply_allman=True,
    ).strip(),
    encoding="utf-8",
  )


def build_stdlib_cpp_lines(tr: Translator, *, merge_entry_runtime: bool) -> list[str]:
  lines = [
    *codegen_file_header_lines("标准库非模板实现汇总", tr.generated_at),
    "#include <stdio.h>",
    "#include <string.h>",
    "#include <math.h>",
    "",
  ]
  lines.append(f'#include "{UMBRELLA_HEADER}"')
  lines.append("")
  for name in tr.stdlib_modules_for_umbrella or STDLIB_REL_PATHS:
    mp = stdlib_module_path(name)
    q = namespace_qualifier_for_module(mp)
    if q:
      lines.append(using_namespace_line(q))
  if tr.stdlib_modules_for_umbrella:
    lines.append("")
  for mp in tr.module_order:
    if not tr._is_stdlib_module(mp):
      continue
    chunk = tr.per_module_source_lines.get(mp, [])
    if chunk:
      lines.extend(merge_consecutive_namespace_blocks(chunk))
      lines.append("")
  if merge_entry_runtime and tr.source_lines:
    lines.extend(tr.source_lines)
  return lines


def write_protocol_traits_header(tr: Translator) -> None:
  lines = tr.per_module_header_lines.get(_PROTOCOL_TRAITS_MODULE, [])
  traits, rest = split_protocol_header_lines(lines)
  tr.per_module_header_lines[_PROTOCOL_TRAITS_MODULE] = rest
  guard = PROTOCOL_TRAITS_GUARD
  hpath = tr._stdlib_artifact_path(_PROTOCOL_TRAITS_MODULE, ".h")
  traits_path = hpath.parent / "protocol_traits.h"
  traits_path.write_text(
    "\n".join([
      *codegen_file_header_lines(f"{RUNTIME_PREFIX}/core/protocols.py", tr.generated_at),
      f"#ifndef {guard}",
      f"#define {guard}",
      "",
      *traits,
      f"#endif // {guard}",
      "",
    ]),
    encoding="utf-8",
  )


def write_protocol_erase_header(tr: Translator) -> None:
  from ..codegen.protocol_erase_gen import (
    protocol_erase_domain_header_lines,
    protocol_erase_header_lines,
  )
  from ..constant.stdlib_layout import CORE_PKG

  hpath = tr.runtime_output_dir / CORE_PKG / "protocol_erase.h"
  hpath.parent.mkdir(parents=True, exist_ok=True)
  hpath.write_text(
    "\n".join(protocol_erase_header_lines(generated_at=tr.generated_at)),
    encoding="utf-8",
  )
  domain_lines = protocol_erase_domain_header_lines(generated_at=tr.generated_at)
  if domain_lines:
    dpath = tr.runtime_output_dir / CORE_PKG / "protocol_erase_domain.h"
    dpath.write_text("\n".join(domain_lines), encoding="utf-8")


def write_umbrella_header(tr: Translator) -> None:
  if not tr._is_runtime_bootstrap():
    return
  if not any(tr._is_stdlib_module(mp) for mp in tr.module_order):
    return
  write_primitive_type_headers(tr)
  write_protocol_erase_header(tr)
  rel = f"{RUNTIME_PREFIX}/minimal"
  guard = module_path_to_guard(rel)
  hpath = tr.runtime_output_dir / UMBRELLA_HEADER
  hpath.parent.mkdir(parents=True, exist_ok=True)
  hpath.write_text(
    build_py2cpp_umbrella_header(
      guard,
      tr.generated_at,
      RUNTIME_PREFIX,
      tr.stdlib_modules_for_umbrella or STDLIB_REL_PATHS,
      debug=tr.debug,
    ),
    encoding="utf-8",
  )
  sync_runtime_cpp_usings(tr)


def sync_runtime_cpp_usings(tr: Translator) -> None:
  path = tr.runtime_output_dir / RUNTIME_CPP
  if not path.is_file() or not tr.stdlib_modules_for_umbrella:
    return
  lines = path.read_text(encoding="utf-8").splitlines()
  start = None
  end = None
  for i, line in enumerate(lines):
    if line.startswith("using namespace py2cpp::"):
      if start is None:
        start = i
      end = i + 1
    elif start is not None and not line.startswith("using namespace py2cpp::"):
      break
  if start is None:
    insert_at = None
    for i, line in enumerate(lines):
      if line == f'#include "{RUNTIME_PREFIX}/operators.inl"':
        insert_at = i + 1
        break
    if insert_at is None:
      return
    new_usings = runtime_cpp_using_lines(tr)
    lines[insert_at:insert_at] = [""] + new_usings + [""]
  else:
    lines[start:end] = runtime_cpp_using_lines(tr)
  path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_per_module_headers(tr: Translator) -> None:
  for module_path in tr.module_order:
    if module_path == tr.entry_module_path and not (
      tr._is_runtime_bootstrap() and module_path == RUNTIME_PKG
    ):
      continue
    if tr._is_stdlib_module(module_path) and not tr._can_write_stdlib_artifact(module_path):
      continue
    if write_stdlib_codegen_header(tr, module_path):
      continue
    if module_path == _PROTOCOL_TRAITS_MODULE:
      write_protocol_traits_header(tr)
    lines = tr.per_module_header_lines.get(module_path, [])
    deferred = tr.per_module_deferred_header_lines.get(module_path, [])
    if deferred:
      lines = splice_before_innermost_namespace_close(lines, deferred)
    guard = module_path_to_guard(module_path)
    if tr._is_stdlib_module(module_path):
      hpath = tr._stdlib_artifact_path(module_path, ".h")
    else:
      rel_mp = tr._user_module_output_relpath(module_path)
      hpath = tr.entry_output_dir / f"{rel_mp}.h"
    hpath.parent.mkdir(parents=True, exist_ok=True)
    note = (
      tr._stdlib_source_note(module_path)
      if tr._is_stdlib_module(module_path)
      else f"{module_path}.py"
    )
    content = [
      *codegen_file_header_lines(note, tr.generated_at),
      f"#ifndef {guard}",
      f"#define {guard}",
      "",
    ]
    ma = tr.module_analysis.get(module_path, ModuleAnalysis(module_path))
    extra_includes: list[str] = []
    if module_path == _JSON_API_MODULE:
      for inc in _JSON_API_EXTRA_HEADER_INCLUDES:
        if inc not in ma.includes:
          extra_includes.append(inc)
    for inc in list(extra_includes) + list(ma.includes):
      content.append(format_include_line(inc))
    if module_path == _PROTOCOL_TRAITS_MODULE:
      content.append(f'#include "{PROTOCOL_TRAITS_HEADER}"')
    if ma.includes:
      content.append("")
    if ma.forward_decls:
      for decl in ma.forward_decls:
        content.append(decl)
      content.append("")
    content.extend(lines)
    if ma.post_class_includes:
      content.append("")
      for inc in ma.post_class_includes:
        content.append(format_include_line(inc))
    if tr.per_module_inl_lines.get(module_path):
      if module_path not in _HEADER_SKIP_INL_IN_MODULE_H:
        inl_tail: list[str] = []
        if (
          tr._is_stdlib_module(module_path)
          and module_path not in (RUNTIME_PKG, RUNTIME_BUILTINS_MODULE)
          and module_path not in _HEADER_TAIL_SKIP_UMBRELLA
          and module_path != _ITER_RESULT_MODULE
        ):
          inl_tail.append(f'#include "{UMBRELLA_HEADER}"')
        if (
          tr._is_stdlib_module(module_path)
          and module_path not in _HEADER_SKIP_OPERATORS_BEFORE_INL
        ):
          inl_tail.append(f'#include "{RUNTIME_PREFIX}/operators.h"')
        global_traits = tr.per_module_global_traits_lines.get(module_path, [])
        if global_traits:
          inl_tail.extend([
            "",
            '#include "py2cpp/core/refcount.h"',
            "",
            *global_traits,
          ])
        inl_tail.extend(["", f'#include "{module_path}.inl"', ""])
        if module_path in _HEADER_INL_BEFORE_NS_CLOSE:
          content = insert_inl_before_namespace_close(content, module_path, inl_tail)
        else:
          content.extend(inl_tail)
    content.append(f"#endif // {guard}")
    content.append("")
    hpath.write_text("\n".join(content), encoding="utf-8")


def _sanitize_core_iter_result_inl(
  content: list[str],
  *,
  str_inc: str,
  umbrella_inc: str,
) -> list[str]:
  """``iter_result.inl``：仅 ``str.h`` + ``operators.h``；注入必要 ``using``。"""
  header: list[str] = []
  includes: list[str] = []
  rest: list[str] = []
  phase = "header"
  for line in content:
    stripped = line.strip()
    if phase == "header":
      if stripped.startswith("#include"):
        phase = "includes"
        includes.append(line)
      else:
        header.append(line)
      continue
    if phase == "includes":
      if stripped.startswith("#include"):
        includes.append(line)
        continue
      phase = "rest"
    if stripped.startswith("using ::py2cpp::text::str::") and stripped != "using ::py2cpp::text::str::PyStr;":
      continue
    rest.append(line)
  ops_inc = next((ln for ln in includes if "operators.h" in ln), None)
  other_includes = [
    ln
    for ln in includes
    if ln not in (str_inc, umbrella_inc, ops_inc) and "minimal.h" not in ln
  ]
  ordered_includes = [str_inc]
  if ops_inc is not None:
    ordered_includes.append(ops_inc)
  ordered_includes.extend(other_includes)
  usings = [
    "using namespace py2cpp::core::iter_result;",
    "using ::py2cpp::text::str::PyStr;",
  ]
  rest = [
    ln
    for ln in rest
    if ln.strip()
    not in (
      "using namespace py2cpp::core::iter_result;",
      "using ::py2cpp::text::str::PyStr;",
    )
  ]
  if rest and rest[0].strip():
    ordered_includes.append("")
  return [*header, *ordered_includes, "", *usings, "", *rest]


def write_per_module_inl(tr: Translator) -> None:
  for module_path in tr.module_order:
    if tr._is_stdlib_module(module_path) and not tr._can_write_stdlib_artifact(module_path):
      continue
    if write_stdlib_codegen_inl(tr, module_path):
      continue
    lines = tr.per_module_inl_lines.get(module_path)
    if not lines:
      continue
    if tr._is_stdlib_module(module_path):
      ipath = tr._stdlib_artifact_path(module_path, ".inl")
    else:
      rel_mp = tr._user_module_output_relpath(module_path)
      ipath = tr.entry_output_dir / f"{rel_mp}.inl"
    ipath.parent.mkdir(parents=True, exist_ok=True)
    inl_includes: list[str] = []
    ma = tr.module_analysis.get(module_path)
    if (
      tr._is_stdlib_module(module_path)
      and module_path != RUNTIME_PKG
      and module_path not in _INL_SKIP_UMBRELLA
    ):
      inl_includes.append(f'#include "{UMBRELLA_HEADER}"')
    inl_includes.extend(module_inl_extra_include_lines(module_path))
    if (
      tr._is_stdlib_module(module_path)
      and module_path != RUNTIME_PKG
      and module_path not in _INL_SKIP_OPERATORS_H
    ):
      ops_h = f'#include "{RUNTIME_PREFIX}/operators.h"'
      if ops_h not in inl_includes:
        inl_includes.append(ops_h)
    if (
      ma
      and ma.forward_decls
      and stdlib_header_include("text/str") not in ma.includes
      and module_path not in _INL_SKIP_UMBRELLA
    ):
      str_inc = f'#include "{stdlib_header_include("text/str")}"'
      if str_inc not in inl_includes:
        inl_includes.append(str_inc)
    inl_preamble: list[str] = []
    if module_path in _INL_EXTRA_OPERATORS_INL:
      inl_includes.append(f'#include "{RUNTIME_PREFIX}/operators.inl"')
    note = (
      f"{tr._stdlib_source_note(module_path)}（模板实现）"
      if tr._is_stdlib_module(module_path)
      else f"{module_path}.py（实现）"
    )
    preamble = tr._stdlib_inl_using_lines(module_path) if tr._is_stdlib_module(module_path) else []
    seen_pre = {ln.strip() for ln in preamble}
    idx = tr.header_usings_index
    umbrella_inc = f'#include "{UMBRELLA_HEADER}"'
    for inc in inl_includes:
      if inc == umbrella_inc:
        continue
      header = include_line_to_header_path(inc) or inc
      for ns, sym in idx.get(header, ()):
        if module_path == _ITER_RESULT_MODULE and ns == 'py2cpp::text::str' and sym != 'PyStr':
          continue
        line = using_symbol_line(ns, sym)
        if line not in seen_pre:
          seen_pre.add(line)
          preamble.append(line)
    if module_path == _ITER_RESULT_MODULE:
      str_inc = f'#include "{stdlib_header_include("text/str")}"'
      rest = [
        inc
        for inc in inl_includes
        if inc not in (str_inc, umbrella_inc) and "minimal.h" not in inc
      ]
      inl_includes = [str_inc, *rest]
    body = list(lines)
    if any("::new (&" in ln for ln in body):
      new_inc = "#include <new>"
      if new_inc not in inl_includes:
        inl_includes.append(new_inc)
    if preamble:
      flat = [ln.strip() for ln in preamble]
      body = [*flat, ""] + body
    body = merge_consecutive_namespace_blocks(body)
    content = [
      *codegen_file_header_lines(note, tr.generated_at),
      "",
      *inl_includes,
      *(["",] if inl_includes else []),
      *inl_preamble,
      *body,
      "",
    ]
    if module_path == _ITER_RESULT_MODULE:
      content = _sanitize_core_iter_result_inl(
        content,
        str_inc=f'#include "{stdlib_header_include("text/str")}"',
        umbrella_inc=umbrella_inc,
      )
    ipath.write_text("\n".join(content), encoding="utf-8")
  write_mirror_codegen_artifacts(tr)


def write_mirror_codegen_artifacts(tr: Translator) -> None:
  if not tr._is_runtime_bootstrap():
    return
  from ..codegen.stdlib_mirror_codegen import write_mirror_codegen_artifacts as _write

  _write(tr.runtime_output_dir / "py2cpp", tr.generated_at)
