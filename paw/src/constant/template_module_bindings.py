"""``-*.inl`` 扫描、``+`` / 镜像模块绑定校验。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .inject_specs import CODEGEN_STANDALONE_TEMPLATE_RELS
from .stdlib_discovery import STDLIB_REL_PATH_SET

_TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates"


def module_rel_from_mirror_template(template_rel: str) -> str:
  """``sql/sqlite.inl`` / ``util/tuple.h`` → ``sql/sqlite`` / ``util/tuple``。"""
  for suffix in (".inl", ".h"):
    if template_rel.endswith(suffix):
      return template_rel[:-len(suffix)]
  raise ValueError(f"镜像模板须为 *.inl 或 *.h: {template_rel}")


def _mirror_skip_template_rel(rel: str) -> bool:
  return (
    rel.startswith("~test/")
    or rel.startswith("~macro/")
    or rel.startswith("~class_header/")
    or rel in CODEGEN_STANDALONE_TEMPLATE_RELS
  )


def _inject_skip_template_rel(rel: str) -> bool:
  return rel.startswith("~test/") or rel.startswith("~macro/")


def _is_inject_inl_template_name(name: str) -> bool:
  """``+stem.inl``（单点，排除 ``+stem.inl.h`` 等）。"""
  return name.startswith("+") and name.endswith(".inl") and name.count(".") == 1


def _is_class_header_inject_template_name(name: str) -> bool:
  """``+stem.h``（单点，排除 ``+stem.inl.h``）。"""
  return name.startswith("+") and name.endswith(".h") and name.count(".") == 1


def _mirror_skip_template_name(name: str) -> bool:
  return name.startswith("~") or name.startswith("+") or name.startswith("-")


def module_rel_from_inject_template(template_rel: str) -> str:
  """``util/+memory.inl`` / ``text/+str.h`` → ``util/memory`` / ``text/str``。"""
  parts = template_rel.split("/")
  name = parts[-1]
  if not name.startswith("+"):
    raise ValueError(f"inject 模板须以 + 开头: {template_rel}")
  if name.endswith(".inl"):
    stem = name[1:-4]
  elif name.endswith(".h"):
    stem = name[1:-2]
  else:
    raise ValueError(f"inject 模板须为 +<stem>.inl 或 +<stem>.h: {template_rel}")
  parent = "/".join(parts[:-1])
  if parent:
    return f"{parent}/{stem}"
  return stem


def module_rel_from_paste_before_template(template_rel: str) -> str:
  """``system/-time.inl`` → ``system/time``（父目录 + ``-`` 后 stem）。"""
  parts = template_rel.split("/")
  name = parts[-1]
  if not name.startswith("-") or not name.endswith(".inl"):
    raise ValueError(f"paste_before 模板须为 -<stem>.inl: {template_rel}")
  stem = name[1:-4]
  parent = "/".join(parts[:-1])
  if parent:
    return f"{parent}/{stem}"
  return stem


@lru_cache(maxsize=None)
def _paste_template_module_rel_map() -> dict[str, str]:
  """``~*.inl`` 类尾 / inject 模板 → ``py2cpp`` 模块 rel（无法从文件名推断时登记）。"""
  from .codegen_insert_hooks import CODEGEN_INSERT_HOOKS
  from .inject_specs import CLASS_PASTE_MODULE_REL, CLASS_PASTE_TEMPLATE_SPECS

  out: dict[str, str] = {}
  for class_name, template_rels in CLASS_PASTE_TEMPLATE_SPECS.items():
    module_rel = CLASS_PASTE_MODULE_REL[class_name]
    for template_rel in template_rels:
      out[template_rel] = module_rel
  for hook in CODEGEN_INSERT_HOOKS.values():
    if hook.module_rel:
      out[hook.template_rel] = hook.module_rel
  return out


def module_rel_from_template_rel(template_rel: str) -> str | None:
  """``templates/<rel>`` → ``py2cpp`` 模块 rel；``~test/`` 等无法推断时返回 ``None``。"""
  norm = template_rel.replace("\\", "/")
  if norm == "~test/~syntax_showcase.inl":
    return "util/memory"
  if norm.startswith("~test/") or norm in CODEGEN_STANDALONE_TEMPLATE_RELS:
    return None
  name = norm.split("/")[-1]
  if name.startswith("+"):
    return module_rel_from_inject_template(norm)
  if name.startswith("-"):
    return module_rel_from_paste_before_template(norm)
  if name.startswith("~"):
    return _paste_template_module_rel_map().get(norm)
  if norm.endswith(".inl") or norm.endswith(".h"):
    return module_rel_from_mirror_template(norm)
  return None


def iter_bound_template_modules(
  *,
  stdlib_rel_paths: frozenset[str] = STDLIB_REL_PATH_SET,
) -> tuple[tuple[str, str, str], ...]:
  """``(template_rel, module_rel, kind)``；``kind`` 为 ``mirror_inl`` / ``mirror_h`` / ``inject``。跳过 ``~test/`` / ``~macro/`` 与 ``~`` / ``+`` / ``-`` 文件名。"""
  out: list[tuple[str, str, str]] = []
  root = _TEMPLATE_ROOT.resolve()
  for path in sorted(root.rglob("*.inl")):
    rel = path.relative_to(root).as_posix()
    if _mirror_skip_template_rel(rel):
      continue
    name = path.name
    if _mirror_skip_template_name(name):
      continue
    module_rel = module_rel_from_mirror_template(rel)
    out.append((rel, module_rel, "mirror_inl"))
  for path in sorted(root.rglob("*.h")):
    rel = path.relative_to(root).as_posix()
    if _mirror_skip_template_rel(rel):
      continue
    name = path.name
    if _mirror_skip_template_name(name):
      continue
    module_rel = module_rel_from_mirror_template(rel)
    out.append((rel, module_rel, "mirror_h"))
  return tuple(out)


def validate_template_module_bindings(
  *,
  stdlib_rel_paths: frozenset[str] = STDLIB_REL_PATH_SET,
) -> None:
  """无前缀 / ``+`` 模板必须有对应 ``py2cpp/<module_rel>.py``（在 ``STDLIB_REL_PATH_SET`` 内）。"""
  from ..codegen.template_conventions import validate_template_module_bindings as _validate

  _validate(stdlib_rel_paths=stdlib_rel_paths)
