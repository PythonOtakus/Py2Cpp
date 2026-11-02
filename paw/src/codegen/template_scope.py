"""``PY2CPP_BEGIN_SCOPE`` / ``PY2CPP_END_SCOPE`` 与 ``~macro`` 生成头。"""
from __future__ import annotations

from pathlib import Path

from ..analysis.module_namespace import cpp_namespace_segment

_TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates"
_MACRO_DIR_NAME = "~macro"
_BEGIN_SCOPE_MARKER = "PY2CPP_BEGIN_SCOPE"
_PY2CPP_MACRO_MARKER = "PY2CPP_"

MACRO_STUB_LINES: tuple[str, ...] = (
  "#define PY2CPP_IGNORE",
  "#define PY2CPP_END",
  "#define PY2CPP_BEGIN(...)",
  "#define PY2CPP_INJECT_CLASS(...)",
  "#define PY2CPP_INCLUDE(...)",
  "#define PY2CPP_EXEC(...)",
)


def namespace_segments_for_module_rel(module_rel: str) -> list[str]:
  return [cpp_namespace_segment(p) for p in module_rel.split("/")]


def namespace_qualifier_for_module_rel(module_rel: str) -> str:
  """``sql/sqlite`` → ``py2cpp::sql::sqlite``（与 runtime ``.h`` 命名空间一致）。"""
  return "py2cpp::" + "::".join(namespace_segments_for_module_rel(module_rel))


def namespace_open_lines(module_rel: str) -> list[str]:
  parts = namespace_segments_for_module_rel(module_rel)
  lines = ["namespace py2cpp {"]
  for part in parts:
    lines.append(f"namespace {part} {{")
  return lines


def namespace_close_lines(module_rel: str) -> list[str]:
  parts = namespace_segments_for_module_rel(module_rel)
  lines: list[str] = []
  for part in reversed(parts):
    lines.append(f"}} // namespace {part}")
  lines.append("} // namespace py2cpp")
  return lines


def macro_header_rel_for_template(template_rel: str) -> str:
  """``text/+bytes.inl`` → ``~macro/text/+bytes.inl.h``。"""
  norm = template_rel.replace("\\", "/")
  return f"{_MACRO_DIR_NAME}/{norm}.h"


def macro_header_path(template_rel: str, *, templates_root: Path | None = None) -> Path:
  root = (templates_root or _TEMPLATE_ROOT).resolve()
  return root / macro_header_rel_for_template(template_rel)


def template_uses_begin_scope(text: str) -> bool:
  return _BEGIN_SCOPE_MARKER in text


def format_macro_header(
  template_rel: str,
  module_rel: str | None,
  *,
  has_begin_scope: bool,
) -> str:
  lines = [
    "#pragma once",
    "/* clangd-only：由 scripts/gen_compile_commands.py 生成；勿手改。",
    f" * 模板：templates/{template_rel}",
  ]
  if module_rel:
    lines.append(f" * 模块：{module_rel}")
  lines.append(" */")
  lines.extend(MACRO_STUB_LINES)
  from .expand_py2cpp_template import clangd_macro_expansion_stub_lines

  lines.extend(clangd_macro_expansion_stub_lines())
  if module_rel:
    lines.append(
      f"#define PY2CPP_NAMESPACE {namespace_qualifier_for_module_rel(module_rel)}"
    )
  if has_begin_scope and module_rel:
    parts = namespace_segments_for_module_rel(module_rel)
    open_ns = " ".join(f"namespace {p} {{" for p in ["py2cpp", *parts])
    close_ns = " ".join("}" for _ in range(len(parts) + 1))
    lines.append(f"#define PY2CPP_BEGIN_SCOPE {open_ns}")
    lines.append(f"#define PY2CPP_END_SCOPE {close_ns}")
  return "\n".join(lines) + "\n"


def iter_templates_needing_macro_header(
  *,
  templates_root: Path | None = None,
) -> tuple[str, ...]:
  """含任意 ``PY2CPP_*`` 宏的 ``templates/**/*.inl`` / ``*.h``（不含 ``~macro/``）。"""
  root = (templates_root or _TEMPLATE_ROOT).resolve()
  if not root.is_dir():
    return ()
  out: list[str] = []
  for pattern in ("*.inl", "*.h"):
    for path in sorted(root.rglob(pattern)):
      rel = path.relative_to(root).as_posix()
      if rel.startswith("~macro/"):
        continue
      text = path.read_text(encoding="utf-8")
      if _PY2CPP_MACRO_MARKER in text:
        out.append(rel)
  return tuple(out)
