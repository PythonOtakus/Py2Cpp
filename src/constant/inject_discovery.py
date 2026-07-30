"""扫描 ``templates/**/+*.inl`` / ``+*.h`` / ``-*.inl``，推断模块级 inject 规格。"""
from __future__ import annotations

from pathlib import Path

from .inject_specs import CODEGEN_INJECT_TEMPLATE_RELS, PASTE_AFTER_IN_MODULE_MODULES
from .template_module_bindings import (
  _inject_skip_template_rel,
  _is_class_header_inject_template_name,
  _is_inject_inl_template_name,
  module_rel_from_inject_template,
  module_rel_from_paste_before_template,
  validate_template_module_bindings,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE_ROOT = _REPO_ROOT / "templates"
_ZEUS_TEMPLATE_ROOT = _REPO_ROOT / "zeus" / "templates"


def discover_module_paste_after_templates() -> tuple[tuple[str, str, bool], ...]:
  """返回 ``(module_rel, template_rel, in_module)``；跳过 ``test/``。"""
  validate_template_module_bindings()
  out: list[tuple[str, str, bool]] = []
  root = _TEMPLATE_ROOT.resolve()
  for path in sorted(root.rglob("*.inl")):
    rel = path.relative_to(root).as_posix()
    if (
      _inject_skip_template_rel(rel)
      or rel in CODEGEN_INJECT_TEMPLATE_RELS
      or not _is_inject_inl_template_name(path.name)
    ):
      continue
    module_rel = module_rel_from_inject_template(rel)
    in_module = module_rel in PASTE_AFTER_IN_MODULE_MODULES
    out.append((module_rel, rel, in_module))
  return tuple(out)


def discover_zeus_paste_after_templates() -> tuple[tuple[str, str, str], ...]:
  """``zeus/templates/**/+*.inl`` → ``(module_rel, template_rel, templates_root)``。

  模块路径为用户模块 rel（如 ``platform/window``），**不**加 ``py2cpp/`` 前缀。
  """
  out: list[tuple[str, str, str]] = []
  root = _ZEUS_TEMPLATE_ROOT
  if not root.is_dir():
    return tuple(out)
  root = root.resolve()
  for path in sorted(root.rglob("*.inl")):
    rel = path.relative_to(root).as_posix()
    if _inject_skip_template_rel(rel) or not _is_inject_inl_template_name(path.name):
      continue
    module_rel = module_rel_from_inject_template(rel)
    out.append((module_rel, rel, str(root)))
  return tuple(out)


def discover_class_header_inject_templates() -> tuple[tuple[str, str], ...]:
  """``+*.h`` → 模块 ``.h`` 类体尾部 inject（``text/+str.h`` → ``text/str``）。"""
  validate_template_module_bindings()
  out: list[tuple[str, str]] = []
  root = _TEMPLATE_ROOT.resolve()
  for path in sorted(root.rglob("*.h")):
    rel = path.relative_to(root).as_posix()
    if _inject_skip_template_rel(rel) or rel in CODEGEN_INJECT_TEMPLATE_RELS:
      continue
    if not _is_class_header_inject_template_name(path.name):
      continue
    module_rel = module_rel_from_inject_template(rel)
    out.append((module_rel, rel))
  return tuple(out)


def discover_module_paste_before_templates() -> tuple[tuple[str, str], ...]:
  """返回 ``(module_rel, template_rel)``；跳过 ``test/``。"""
  validate_template_module_bindings()
  out: list[tuple[str, str]] = []
  root = _TEMPLATE_ROOT.resolve()
  for path in sorted(root.rglob("*.inl")):
    rel = path.relative_to(root).as_posix()
    if _inject_skip_template_rel(rel):
      continue
    name = path.name
    if not (name.startswith("-") and name.endswith(".inl") and name.count(".") == 1):
      continue
    module_rel = module_rel_from_paste_before_template(rel)
    out.append((module_rel, rel))
  return tuple(out)
