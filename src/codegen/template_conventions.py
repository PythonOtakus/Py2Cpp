"""``templates/**`` 命名与格式规范：译期校验（bootstrap / ``include_stdlib``）。"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path

from ..constant.codegen_insert_hooks import CODEGEN_INSERT_HOOKS
from ..constant.inject_specs import (
  CLASS_PASTE_TEMPLATE_SPECS,
  CODEGEN_INJECT_TEMPLATE_RELS,
  CODEGEN_STANDALONE_TEMPLATE_RELS,
)
from ..constant.template_module_bindings import (
  _inject_skip_template_rel,
  _is_class_header_inject_template_name,
  _is_inject_inl_template_name,
  _mirror_skip_template_name,
  _mirror_skip_template_rel,
  _paste_template_module_rel_map,
  iter_bound_template_modules,
  module_rel_from_inject_template,
  module_rel_from_paste_before_template,
  module_rel_from_template_rel,
)
from ..constant.stdlib_discovery import STDLIB_REL_PATH_SET
from ..constant.template_ffi_includes import (
  is_forbidden_template_ab_include,
  iter_include_headers_in_text,
)
from ..translation_error import TranslationError
from .expand_py2cpp_template import (
  _find_forbidden_stl_container_lines,
  _FORBIDDEN_DYNAMIC_TYPE_RE,
  _FORBIDDEN_TYPE_EVAL_RE,
  template_root,
)
from .template_scan import (
  ctx_key_has_pascal_suffix,
  iter_include_refs,
  partition_ignore_regions,
  resolve_include_path,
  scan_begin_end_blocks,
  scan_ctx_ignore_echo_set_violations,
  scan_ctx_key_naming_violations,
  scan_def_naming,
  scan_for_var_naming,
  scan_include_guard_violations,
  scan_inject_class_shell_violations,
  scan_inject_ignore_violations,
  scan_orphan_elif_else,
  scan_qualified_cut_type_violations,
  scan_scope_pair_errors,
)

_DEPRECATED_MACRO_RES: tuple[tuple[re.Pattern[str], str], ...] = (
  (re.compile(r"\bPY2CPP_STMT\s*\("), "PY2CPP_STMT"),
  (re.compile(r"\bPY2CPP_SET\s*\("), "PY2CPP_SET"),
  (re.compile(r"\bPY2CPP_SYM\s*\("), "PY2CPP_SYM"),
  (re.compile(r"\bPY2CPP_MACRO\s*\("), "PY2CPP_MACRO"),
  (re.compile(r"\bPY2CPP_RAW\s*\("), "PY2CPP_RAW"),
  (re.compile(r"\bPY2CPP_EMIT\s*\("), "PY2CPP_EMIT"),
  (re.compile(r"\bPY2CPP_FILE_META\s*\("), "PY2CPP_FILE_META"),
  (re.compile(r"\bPY2CPP_EMIT_CTX\s*\("), "PY2CPP_EMIT_CTX"),
  (re.compile(r"\bPY2CPP_INLINE_ECHO\s*\("), "PY2CPP_INLINE_ECHO"),
)

_PYTHON_ONLY_INCLUDE_TEMPLATE_RELS: frozenset[str] = frozenset({
  "core/~protocol_erase_spec.inl",
  "core/~protocol_erase_preamble.inl",
  "core/~exception_group_fallback_header.inl",
})

_NAMESPACE_MACRO_RE = re.compile(r"\bPY2CPP_NAMESPACE\b")
_BACKSLASH_INCLUDE_RE = re.compile(r'PY2CPP_INCLUDE\s*\(\s*"[^"]*\\')


class ViolationSeverity(str, Enum):
  ERROR = "error"
  WARNING = "warning"


@dataclass(frozen=True)
class TemplateViolation:
  rule: str
  template_rel: str
  lineno: int | None
  message: str
  severity: ViolationSeverity = ViolationSeverity.ERROR


def _iter_template_files() -> list[tuple[str, Path]]:
  root = template_root().resolve()
  out: list[tuple[str, Path]] = []
  for path in sorted(root.rglob("*")):
    if not path.is_file() or path.suffix not in (".h", ".inl"):
      continue
    rel = path.relative_to(root).as_posix()
    if rel.startswith("~macro/"):
      continue
    out.append((rel, path))
  return out


def _templates_fingerprint() -> float:
  root = template_root().resolve()
  latest = root.stat().st_mtime
  for path in root.rglob("*"):
    if not path.is_file():
      continue
    rel = path.relative_to(root).as_posix()
    if rel.startswith("~macro/"):
      continue
    latest = max(latest, path.stat().st_mtime)
  codegen_dir = Path(__file__).resolve().parent
  for path in sorted(codegen_dir.glob("*_gen.py")):
    latest = max(latest, path.stat().st_mtime)
  expand_py = codegen_dir / "expand_py2cpp_template.py"
  if expand_py.is_file():
    latest = max(latest, expand_py.stat().st_mtime)
  return latest


def _is_paste_inject_rel(rel: str) -> bool:
  if rel in CODEGEN_STANDALONE_TEMPLATE_RELS or rel in CODEGEN_INJECT_TEMPLATE_RELS:
    return False
  name = rel.split("/")[-1]
  if name.startswith("-") and name.endswith(".inl") and name.count(".") == 1:
    return True
  if _is_inject_inl_template_name(name):
    return True
  return _is_class_header_inject_template_name(name)


def _check_filename_rules(rel: str) -> list[TemplateViolation]:
  name = rel.split("/")[-1]
  violations: list[TemplateViolation] = []
  if name.startswith("+") and name.count(".") != 1:
    violations.append(TemplateViolation(
      "R0102", rel, 1,
      f"inject 模板须为 +<stem>.inl 或 +<stem>.h（单扩展名），当前: {name}",
    ))
  if name.startswith("-") and (not name.endswith(".inl") or name.count(".") != 1):
    violations.append(TemplateViolation(
      "R0103", rel, 1,
      f"paste_before 模板须为 -<stem>.inl（单扩展名），当前: {name}",
    ))
  if not _mirror_skip_template_rel(rel) and not _mirror_skip_template_name(name):
    if name.startswith("~"):
      violations.append(TemplateViolation(
        "R0101", rel, 1,
        f"镜像模板文件名不得以 ~ / + / - 开头，当前: {name}",
      ))
  return violations


def _check_module_bindings(
  stdlib_rel_paths: frozenset[str],
) -> list[TemplateViolation]:
  violations: list[TemplateViolation] = []
  for template_rel, module_rel, kind in iter_bound_template_modules(
    stdlib_rel_paths=stdlib_rel_paths,
  ):
    if module_rel not in stdlib_rel_paths:
      violations.append(TemplateViolation(
        "R0201", template_rel, None,
        f"{kind} 绑定模块不在 py2cpp 标准库中: {module_rel}",
      ))
  root = template_root().resolve()
  for path in sorted(root.rglob("*.inl")):
    rel = path.relative_to(root).as_posix()
    if _inject_skip_template_rel(rel):
      continue
    name = path.name
    if _is_inject_inl_template_name(name):
      if rel in CODEGEN_STANDALONE_TEMPLATE_RELS:
        continue
      module_rel = module_rel_from_inject_template(rel)
      kind = "inject_inl"
    elif name.startswith("-") and name.endswith(".inl") and name.count(".") == 1:
      module_rel = module_rel_from_paste_before_template(rel)
      kind = "paste_before"
    else:
      continue
    if module_rel not in stdlib_rel_paths:
      violations.append(TemplateViolation(
        "R0201", rel, None,
        f"{kind} 绑定模块不在 py2cpp 标准库中: {module_rel}",
      ))
  for path in sorted(root.rglob("*.h")):
    rel = path.relative_to(root).as_posix()
    if _inject_skip_template_rel(rel):
      continue
    if not _is_class_header_inject_template_name(path.name):
      continue
    if rel in CODEGEN_STANDALONE_TEMPLATE_RELS:
      continue
    module_rel = module_rel_from_inject_template(rel)
    if module_rel not in stdlib_rel_paths:
      violations.append(TemplateViolation(
        "R0201", rel, None,
        f"inject_h 绑定模块不在 py2cpp 标准库中: {module_rel}",
      ))
  return violations


def _collect_include_closure() -> frozenset[str]:
  """凡被任一模板 ``PY2CPP_INCLUDE``（含传递）引用的 rel。"""
  root = template_root().resolve()
  included: set[str] = set()
  for hook in CODEGEN_INSERT_HOOKS.values():
    included.add(hook.template_rel.replace("\\", "/"))
  for rels in CLASS_PASTE_TEMPLATE_SPECS.values():
    included.update(r.replace("\\", "/") for r in rels)
  included |= _PYTHON_ONLY_INCLUDE_TEMPLATE_RELS
  queue = list(included)
  while queue:
    rel = queue.pop()
    path = root / rel
    if not path.is_file():
      continue
    text = path.read_text(encoding="utf-8")
    for _, inc in iter_include_refs(text):
      resolved = resolve_include_path(path.parent, inc, root)
      if resolved is None:
        continue
      child_rel = resolved.relative_to(root).as_posix()
      if child_rel not in included:
        included.add(child_rel)
        queue.append(child_rel)
  for rel, path in _iter_template_files():
    text = path.read_text(encoding="utf-8")
    if not iter_include_refs(text):
      continue
    for _, inc in iter_include_refs(text):
      resolved = resolve_include_path(path.parent, inc, root)
      if resolved is None:
        continue
      child_rel = resolved.relative_to(root).as_posix()
      included.add(child_rel)
  return frozenset(included)


def _check_orphan_tilde_files(include_closure: frozenset[str]) -> list[TemplateViolation]:
  violations: list[TemplateViolation] = []
  paste_map = _paste_template_module_rel_map()
  for rel, _path in _iter_template_files():
    name = rel.split("/")[-1]
    if not name.startswith("~"):
      continue
    if rel in include_closure:
      continue
    if module_rel_from_template_rel(rel) is not None:
      continue
    if rel in paste_map:
      continue
    violations.append(TemplateViolation(
      "R0202", rel, 1,
      "孤立的 ~ 模板：未登记 module_rel、未被 PY2CPP_INCLUDE/hook 引用",
      severity=ViolationSeverity.WARNING,
    ))
  return violations


_CTX_KEY_LITERAL_RE = re.compile(r'"ctx_[A-Za-z0-9_]+"')


def _check_codegen_ctx_key_naming() -> list[TemplateViolation]:
  """``*_gen.py`` / ``expand_py2cpp_template.py`` 中 ``ctx`` 字典键命名。"""
  violations: list[TemplateViolation] = []
  codegen_dir = Path(__file__).resolve().parent
  paths = sorted(codegen_dir.glob("*_gen.py"))
  expand_py = codegen_dir / "expand_py2cpp_template.py"
  if expand_py.is_file():
    paths.append(expand_py)
  for path in paths:
    rel = path.relative_to(codegen_dir.parent.parent).as_posix()
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
      for m in _CTX_KEY_LITERAL_RE.finditer(line):
        key = m.group(0)[1:-1]
        if ctx_key_has_pascal_suffix(key):
          continue
        violations.append(TemplateViolation(
          "R0603", rel, i,
          f"ctx 键须 ctx_PascalCase，当前: {key}",
        ))
  return violations


def _check_duplicate_paste_after() -> list[TemplateViolation]:
  seen: dict[str, str] = {}
  violations: list[TemplateViolation] = []
  root = template_root().resolve()
  for path in sorted(root.rglob("*.inl")):
    rel = path.relative_to(root).as_posix()
    if _inject_skip_template_rel(rel) or rel in CODEGEN_INJECT_TEMPLATE_RELS:
      continue
    if not _is_inject_inl_template_name(path.name):
      continue
    module_rel = module_rel_from_inject_template(rel)
    if module_rel in seen:
      violations.append(TemplateViolation(
        "R0203", rel, None,
        f"重复 paste_after 模块 {module_rel}（已有 {seen[module_rel]}）",
      ))
    else:
      seen[module_rel] = rel
  return violations


def _scan_file_content(rel: str, text: str, base_dir: Path) -> list[TemplateViolation]:
  lines = text.splitlines()
  violations: list[TemplateViolation] = []
  root = template_root().resolve()

  for lineno, line in enumerate(lines, start=1):
    if _FORBIDDEN_TYPE_EVAL_RE.search(line):
      violations.append(TemplateViolation(
        "R0402", rel, lineno,
        "禁止 PY2CPP_TYPE(PY2CPP_EVAL(...))；请用 IGNORE #define ctx_* + PY2CPP_ECHO(ctx_*)",
      ))
    if _FORBIDDEN_DYNAMIC_TYPE_RE.search(line):
      violations.append(TemplateViolation(
        "R0401", rel, lineno,
        "PY2CPP_DYNAMIC_TYPE 已删除；请用 IGNORE #define ctx_* + PY2CPP_ECHO(ctx_*)",
      ))
    for pat, name in _DEPRECATED_MACRO_RES:
      if pat.search(line):
        violations.append(TemplateViolation(
          "R0401", rel, lineno,
          f"已弃用宏 {name}（见 codegen-templates §14）",
        ))
    if _NAMESPACE_MACRO_RE.search(line) and not rel.startswith("~macro/"):
      violations.append(TemplateViolation(
        "R0403", rel, lineno,
        "PY2CPP_NAMESPACE 仅用于生成的 ~macro 桩；paste/镜像模板勿用",
      ))
    if _BACKSLASH_INCLUDE_RE.search(line):
      violations.append(TemplateViolation(
        "R0301", rel, lineno,
        "PY2CPP_INCLUDE 路径须使用正斜杠 /",
      ))

  for lineno, kind, stmt in _find_forbidden_stl_container_lines(text):
    violations.append(TemplateViolation(
      "R0801", rel, lineno,
      f"禁止 STL 容器（{kind}）: {stmt.strip()}",
    ))

  for lineno, inc in iter_include_refs(text):
    if "\\" in inc:
      violations.append(TemplateViolation(
        "R0301", rel, lineno,
        f'PY2CPP_INCLUDE 路径须使用正斜杠 /: "{inc}"',
      ))
      continue
    resolved = resolve_include_path(base_dir, inc, root)
    if resolved is None:
      violations.append(TemplateViolation(
        "R0301", rel, lineno,
        f'PY2CPP_INCLUDE 路径越界或不存在: "{inc}"',
      ))
    elif not resolved.is_file():
      violations.append(TemplateViolation(
        "R0301", rel, lineno,
        f'PY2CPP_INCLUDE 目标不存在: "{inc}"',
      ))

  for lineno, _q, header in iter_include_headers_in_text(text):
    if is_forbidden_template_ab_include(header):
      violations.append(TemplateViolation(
        "R0902", rel, lineno,
        f"禁止模板直导 A/B 系统头 <{header}>；改 #include \"ffi/…\" "
        f"或 C++ 包装头（cstdint/cstdarg/cfloat）；见 docs/c-ffi-pyi.md §11",
      ))

  ignore_regions = partition_ignore_regions(lines)
  for lineno, msg in scan_include_guard_violations(lines):
    violations.append(TemplateViolation("R0901", rel, lineno, msg))
  for lineno, msg in scan_qualified_cut_type_violations(
    lines,
    ignore_regions=ignore_regions,
  ):
    violations.append(TemplateViolation("R0802", rel, lineno, msg))
  for lineno, msg in scan_ctx_key_naming_violations(lines):
    violations.append(TemplateViolation("R0603", rel, lineno, msg))
  for lineno, msg in scan_ctx_ignore_echo_set_violations(
    lines,
    ignore_regions=ignore_regions,
  ):
    violations.append(TemplateViolation("R0603", rel, lineno, msg))

  blocks, struct_errors = scan_begin_end_blocks(lines)
  for lineno, msg in struct_errors:
    violations.append(TemplateViolation("R0501", rel, lineno or None, msg))
  for lineno, msg in scan_orphan_elif_else(blocks):
    violations.append(TemplateViolation("R0502", rel, lineno, msg))
  for block in blocks:
    header_lineno = block.start + 1
    for _, msg in scan_def_naming(block.header, header_lineno):
      violations.append(TemplateViolation("R0601", rel, header_lineno, msg))
    for _, msg in scan_for_var_naming(block.header, header_lineno):
      violations.append(TemplateViolation("R0602", rel, header_lineno, msg))
  for lineno, msg in scan_scope_pair_errors(lines):
    violations.append(TemplateViolation("R0503", rel, lineno or None, msg))

  if _is_paste_inject_rel(rel):
    for lineno, msg in scan_inject_ignore_violations(
      lines,
      check_py2cpp_include=True,
      check_ctx_define=True,
    ):
      rule = "R0701" if "include" in msg else "R0702"
      violations.append(TemplateViolation(rule, rel, lineno, msg))

  if _is_class_header_inject_template_name(rel.split("/")[-1]):
    for lineno, msg in scan_inject_class_shell_violations(lines):
      violations.append(TemplateViolation("R0703", rel, lineno, msg))

  return violations


@lru_cache(maxsize=4)
def _cached_violations(fingerprint: float) -> tuple[TemplateViolation, ...]:
  del fingerprint
  violations: list[TemplateViolation] = []
  stdlib = STDLIB_REL_PATH_SET
  include_closure = _collect_include_closure()

  violations.extend(_check_module_bindings(stdlib_rel_paths=stdlib))
  violations.extend(_check_duplicate_paste_after())
  violations.extend(_check_codegen_ctx_key_naming())
  violations.extend(_check_orphan_tilde_files(include_closure))

  for rel, path in _iter_template_files():
    violations.extend(_check_filename_rules(rel))
    text = path.read_text(encoding="utf-8")
    violations.extend(_scan_file_content(rel, text, path.parent))

  violations.sort(key=lambda v: (v.template_rel, v.lineno or 0, v.rule))
  return tuple(violations)


def clear_template_violations_cache() -> None:
  _cached_violations.cache_clear()


def collect_template_violations() -> list[TemplateViolation]:
  return list(_cached_violations(_templates_fingerprint()))


def format_template_violation(v: TemplateViolation) -> str:
  loc = f"templates/{v.template_rel}"
  if v.lineno is not None:
    loc += f":{v.lineno}"
  return f"  {loc}: [{v.rule}] {v.message}"


def format_template_violations_report(violations: list[TemplateViolation]) -> str:
  errors = [v for v in violations if v.severity == ViolationSeverity.ERROR]
  parts = [f"发现 {len(errors)} 处模板规范违规（可用 --no-strict 关闭）："]
  parts.extend(format_template_violation(v) for v in errors)
  return "\n".join(parts)


def check_template_conventions(*, strict: bool = True) -> None:
  if not strict:
    return
  violations = collect_template_violations()
  for w in violations:
    if w.severity != ViolationSeverity.WARNING:
      continue
    loc = f"templates/{w.template_rel}"
    if w.lineno is not None:
      loc += f":{w.lineno}"
    print(f"警告: {loc}: [{w.rule}] {w.message}", file=sys.stderr)
  errors = [v for v in violations if v.severity == ViolationSeverity.ERROR]
  if errors:
    raise TranslationError(format_template_violations_report(errors))


def validate_template_module_bindings(
  *,
  stdlib_rel_paths: frozenset[str] = STDLIB_REL_PATH_SET,
) -> None:
  missing = _check_module_bindings(stdlib_rel_paths=stdlib_rel_paths)
  if missing:
    raise ValueError(
      "templates 绑定模块不在 py2cpp 标准库中:\n"
      + "\n".join(format_template_violation(v).strip() for v in missing)
    )


def collect_forbidden_type_eval_violations() -> list[str]:
  return [
    format_template_violation(v).strip()
    for v in collect_template_violations()
    if v.rule == "R0402"
  ]


def collect_forbidden_dynamic_type_violations() -> list[str]:
  return [
    v.template_rel
    for v in collect_template_violations()
    if v.rule == "R0401" and "DYNAMIC_TYPE" in v.message
  ]


def collect_forbidden_stl_container_violations() -> list[str]:
  out: list[str] = []
  for v in collect_template_violations():
    if v.rule != "R0801":
      continue
    loc = f"{v.template_rel}:{v.lineno}"
    out.append(
      f"模板禁止使用 STL 容器；请用 PyList / PyDict 或定长数组：{loc}\n"
      f"  {loc} [{v.message}]"
    )
  return out
