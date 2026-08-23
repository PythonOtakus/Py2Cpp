"""整文件 codegen 模板写盘：展开后由 Python 包壳（注释 + include guard）。"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MirrorCodegenSpec:
  """单模块 mirror 写盘规则（默认与 ``util/tuple`` 一致）。"""

  header_inl_include: bool = True
  header_prefix_lines: tuple[str, ...] = ()
  inl_source_note: str | None = None


# 有 ``templates/<rel>.h`` 镜像且由 mirror 写盘的 STDLIB codegen 模块。
STDLIB_MIRROR_CODEGEN_SPECS: dict[str, MirrorCodegenSpec] = {
  "util/tuple": MirrorCodegenSpec(),
  "util/stack_array": MirrorCodegenSpec(),
  "core/refcount": MirrorCodegenSpec(
    header_inl_include=False,
    header_prefix_lines=("#include <stddef.h>", "#include <new>", ""),
  ),
  "core/proxy": MirrorCodegenSpec(header_inl_include=False),
  "weak/ref": MirrorCodegenSpec(header_inl_include=False),
  "core/delegate": MirrorCodegenSpec(
    header_inl_include=False,
    inl_source_note="py2cpp/delegate.py（模板实现）",
  ),
  "core/generator": MirrorCodegenSpec(
    header_inl_include=False,
    inl_source_note="py2cpp/core/generator.py（模板实现）",
  ),
  "core/coroutine": MirrorCodegenSpec(
    header_inl_include=False,
    inl_source_note="py2cpp/core/coroutine.py（模板实现）",
  ),
  "core/async_generator": MirrorCodegenSpec(
    header_inl_include=False,
    inl_source_note="py2cpp/core/async_generator.py（模板实现）",
  ),
}

STDLIB_MIRROR_CODEGEN_RELS: frozenset[str] = frozenset(STDLIB_MIRROR_CODEGEN_SPECS.keys())

# ``layout_emit`` / ``umbrella_gen`` 写盘的独立整文件模板（非 mirror 扫描）。
STANDALONE_WHOLE_FILE_HEADER_SPECS: dict[str, tuple[str, str]] = {
  "char.h": ("py2cpp/char", "py2cpp/__init__.py"),
  "byte.h": ("py2cpp/byte", "py2cpp/__init__.py"),
  "c_str.h": ("py2cpp/c_str", "py2cpp/__init__.py"),
  "py_types.h": ("py2cpp/py_types", "py2cpp/__init__.py"),
  "member_access.h": ("py2cpp/member_access", "py2cpp/__init__.py"),
  "operators.h": ("py2cpp/operators", "py2cpp/__init__.py"),
}

STANDALONE_WHOLE_FILE_INL_GUARD: dict[str, str] = {
  "operators.inl": "PY2CPP_OPERATORS_INL",
}

WHOLE_FILE_TEMPLATE_MINIMAL = "minimal.h"


def _mirror_spec(module_rel: str) -> MirrorCodegenSpec:
  return STDLIB_MIRROR_CODEGEN_SPECS.get(module_rel, MirrorCodegenSpec())


def _codegen_preamble_lines(source_note: str | None, generated_at: str) -> list[str]:
  from ..analysis.ir import codegen_file_header_lines

  if source_note:
    return codegen_file_header_lines(source_note, generated_at)
  lines = ["// 由 py2cpp 生成"]
  if generated_at:
    lines.append(f"// {generated_at}")
  return lines


def wrap_codegen_header(
  body: str,
  *,
  guard: str,
  generated_at: str,
  source_note: str | None = None,
  prefix_lines: Sequence[str] = (),
  include_inl: str | None = None,
) -> str:
  """整文件 ``.h``：来源注释 + ``#ifndef`` + 可选 ``#include *.inl``。"""
  lines: list[str] = [
    *_codegen_preamble_lines(source_note, generated_at),
    f"#ifndef {guard}",
    f"#define {guard}",
    "",
    *prefix_lines,
    body.strip(),
  ]
  if include_inl:
    lines.extend(["", f'#include "{include_inl}"'])
  lines.extend(["", f"#endif // {guard}", ""])
  return "\n".join(lines)


def wrap_codegen_inl_guarded(
  body: str,
  *,
  guard: str,
  generated_at: str,
  source_note: str | None = None,
) -> str:
  """整文件 ``.inl``（带 include guard，如 ``operators.inl``）。"""
  lines: list[str] = [
    *_codegen_preamble_lines(source_note, generated_at),
    f"#ifndef {guard}",
    f"#define {guard}",
    "",
    body.strip(),
    "",
    f"#endif // {guard}",
    "",
  ]
  return "\n".join(lines)


def wrap_mirror_codegen_header(body: str, module_rel: str, generated_at: str) -> str:
  from ..emit.layout_emit import module_path_to_guard
  from ..constant.stdlib_layout import stdlib_module_path

  module_path = stdlib_module_path(module_rel)
  spec = _mirror_spec(module_rel)
  include_inl = f"py2cpp/{module_rel}.inl" if spec.header_inl_include else None
  return wrap_codegen_header(
    body,
    guard=module_path_to_guard(module_path),
    generated_at=generated_at,
    source_note=f"{module_path}.py",
    prefix_lines=spec.header_prefix_lines,
    include_inl=include_inl,
  )


def wrap_mirror_codegen_inl(body: str, module_rel: str, generated_at: str) -> str:
  from ..constant.stdlib_layout import stdlib_module_path

  module_path = stdlib_module_path(module_rel)
  spec = _mirror_spec(module_rel)
  if spec.inl_source_note:
    note_line = f"// 由 py2cpp 根据 {spec.inl_source_note} 生成"
  else:
    note_line = f"// 由 py2cpp 根据 {module_path}.py 生成（模板实现）"
  return "\n".join([
    note_line,
    f"// {generated_at}",
    "",
    body.strip(),
    "",
  ])


def finalize_codegen_file_text(
  template_rel: str,
  expanded: str,
  generated_at: str,
  ctx: dict[str, Any] | None = None,
) -> str:
  """``expand_template`` 之后：mirror / 独立整文件模板包壳，其余片段原样返回。"""
  ctx = ctx or {}
  norm = template_rel.replace("\\", "/")
  from ..constant.template_module_bindings import module_rel_from_mirror_template
  from ..emit.layout_emit import module_path_to_guard

  module_rel = module_rel_from_mirror_template(norm)
  if module_rel and module_rel in STDLIB_MIRROR_CODEGEN_RELS:
    if norm.endswith(".h"):
      return wrap_mirror_codegen_header(expanded, module_rel, generated_at)
    if norm.endswith(".inl"):
      return wrap_mirror_codegen_inl(expanded, module_rel, generated_at)

  if norm in STANDALONE_WHOLE_FILE_HEADER_SPECS:
    mod_path, default_note = STANDALONE_WHOLE_FILE_HEADER_SPECS[norm]
    guard = str(ctx.get("guard") or module_path_to_guard(mod_path))
    note = str(ctx.get("source_note") or default_note)
    return wrap_codegen_header(
      expanded,
      guard=guard,
      generated_at=generated_at,
      source_note=note,
    )

  if norm == WHOLE_FILE_TEMPLATE_MINIMAL:
    guard = str(ctx["guard"])
    note = str(ctx.get("source_note", "templates/minimal.h"))
    return wrap_codegen_header(
      expanded,
      guard=guard,
      generated_at=generated_at,
      source_note=note,
    )

  if norm in STANDALONE_WHOLE_FILE_INL_GUARD:
    guard = str(ctx.get("guard") or STANDALONE_WHOLE_FILE_INL_GUARD[norm])
    note = ctx.get("source_note")
    note_s = str(note) if note else None
    return wrap_codegen_inl_guarded(
      expanded,
      guard=guard,
      generated_at=generated_at,
      source_note=note_s,
    )

  return expanded.strip() + "\n"


def finalize_mirror_codegen_text(
  template_rel: str,
  module_rel: str,
  expanded: str,
  generated_at: str,
) -> str:
  if module_rel not in STDLIB_MIRROR_CODEGEN_RELS:
    return expanded.strip() + "\n"
  return finalize_codegen_file_text(template_rel, expanded, generated_at, ctx={})


def expand_whole_file_template(
  rel: str,
  generated_at: str,
  ctx: dict[str, Any] | None = None,
  *,
  apply_allman: bool = True,
) -> str:
  """展开整文件模板并在 Python 侧包壳（mirror / standalone）。"""
  from .expand_py2cpp_template import expand_template

  expanded = expand_template(rel, ctx, apply_allman=apply_allman)
  return finalize_codegen_file_text(rel, expanded, generated_at, ctx)


def write_mirror_codegen_artifacts(
  generated_py2cpp_root: Path,
  generated_at: str,
  *,
  apply_allman: bool = True,
) -> list[Path]:
  from .expand_py2cpp_template import expand_mirror_to_generated

  return expand_mirror_to_generated(
    generated_py2cpp_root,
    generated_at=generated_at,
    apply_allman=apply_allman,
  )


def stdlib_codegen_rel(module_path: str) -> str | None:
  """``STDLIB_CODEGEN_MODULES`` 表项（已迁 mirror 的模块返回 None 给 layout 跳过）。"""
  from ..constant.stdlib_modules import STDLIB_CODEGEN_MODULES
  from ..constant.stdlib_layout import RUNTIME_PKG

  if not module_path.startswith(f"{RUNTIME_PKG}/"):
    return None
  rel = module_path[len(f"{RUNTIME_PKG}/") :]
  if rel in STDLIB_CODEGEN_MODULES:
    return rel
  return None


def _stdlib_module_rel(module_path: str) -> str | None:
  from ..constant.stdlib_layout import RUNTIME_PKG

  norm = module_path.replace("\\", "/")
  prefix = f"{RUNTIME_PKG}/"
  if not norm.startswith(prefix):
    return None
  return norm[len(prefix) :]


def write_stdlib_codegen_header(tr, module_path: str) -> bool:
  """``True``：本模块 ``.h`` 已由 mirror 写盘，跳过 stub 头。"""
  rel = _stdlib_module_rel(module_path)
  if rel is not None and rel in STDLIB_MIRROR_CODEGEN_RELS:
    return True
  return False


def write_stdlib_codegen_inl(tr, module_path: str) -> bool:
  """``True``：本模块 ``.inl`` 已由 mirror 写盘，跳过 stub 实现。"""
  rel = _stdlib_module_rel(module_path)
  if rel is not None and rel in STDLIB_MIRROR_CODEGEN_RELS:
    return True
  return False
