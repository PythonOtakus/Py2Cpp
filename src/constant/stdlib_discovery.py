"""``py2cpp/`` 遍历发现与排序。"""
from __future__ import annotations

from pathlib import Path

from .paths import PY2CPP_ROOT
from .stdlib_modules import (
  STDLIB_CODEGEN_MODULES,
  STDLIB_SKIP_DOMAIN_PACKAGE_INITS,
  STDLIB_SKIP_PREFIXES,
  STDLIB_SKIP_REL_PATHS,
  UMBRELLA_PREFIX_TIERS,
  UMBRELLA_PRIORITY_MODULES,
)


def discover_stdlib_rel_paths(runtime_root: Path | None = None) -> tuple[str, ...]:
  """``py2cpp/`` 下可翻译 ``.py`` → 相对包根域路径（不含包根 ``__init__.py``）。"""
  root = (runtime_root or PY2CPP_ROOT).resolve()
  found: list[str] = []
  for py in sorted(root.rglob("*.py")):
    if "__pycache__" in py.parts:
      continue
    rel = py.relative_to(root)
    if rel == Path("__init__.py"):
      continue
    if rel.name == "__init__.py":
      mod = "/".join(rel.parts[:-1])
    else:
      mod = str(rel.with_suffix("")).replace("\\", "/")
    if mod in STDLIB_SKIP_REL_PATHS:
      continue
    if any(mod.startswith(prefix) for prefix in STDLIB_SKIP_PREFIXES):
      continue
    if mod in STDLIB_SKIP_DOMAIN_PACKAGE_INITS:
      continue
    found.append(mod)
  return tuple(found)


def _stdlib_tier_index(rel_path: str) -> int:
  for i, prefix in enumerate(UMBRELLA_PREFIX_TIERS):
    if rel_path.startswith(prefix) or rel_path == prefix.rstrip("/"):
      return i
  return len(UMBRELLA_PREFIX_TIERS)


def order_stdlib_rel_paths(
  discovered: tuple[str, ...] | frozenset[str] | set[str],
) -> tuple[str, ...]:
  disc = frozenset(discovered)
  priority = frozenset(UMBRELLA_PRIORITY_MODULES)
  tier_buckets: list[list[str]] = [
    [] for _ in range(len(UMBRELLA_PREFIX_TIERS) + 1)
  ]
  for mod in disc:
    if mod in priority:
      continue
    tier_buckets[_stdlib_tier_index(mod)].append(mod)
  ordered: list[str] = []
  for tier, bucket in enumerate(tier_buckets):
    for mod in UMBRELLA_PRIORITY_MODULES:
      if mod in disc and _stdlib_tier_index(mod) == tier:
        ordered.append(mod)
    ordered.extend(sorted(bucket))
  return tuple(ordered)


_DISCOVERED = discover_stdlib_rel_paths(PY2CPP_ROOT)
STDLIB_REL_PATHS: tuple[str, ...] = order_stdlib_rel_paths(_DISCOVERED)
STDLIB_REL_PATH_SET: frozenset[str] = frozenset(STDLIB_REL_PATHS)


def is_stdlib_codegen_module(module_path: str) -> bool:
  """``py2cpp/<域>/…`` 是否为表驱动 codegen 模块（非逐类翻译）。"""
  norm = module_path.replace("\\", "/").strip("/")
  prefix = "py2cpp/"
  if not norm.startswith(prefix):
    return False
  return norm[len(prefix) :] in STDLIB_CODEGEN_MODULES


def stdlib_module_paths_for_rel_paths(rel_paths: frozenset[str]) -> frozenset[str]:
  """相对 ``py2cpp/`` 域路径 → ``py2cpp/<域>/…`` 译器模块路径。"""
  from .stdlib_layout import stdlib_module_path

  return frozenset(stdlib_module_path(r) for r in rel_paths)
