"""``py2cpp/`` 源树路径 helper（``analysis/stubs`` 共用）。"""
from __future__ import annotations

from pathlib import Path

from ...constant.stdlib_discovery import STDLIB_REL_PATHS

RUNTIME_PKG = "py2cpp"
REPO_ROOT = Path(__file__).resolve().parents[3]
PY2CPP = REPO_ROOT / "py2cpp"


def stdlib_init_path() -> Path:
  return PY2CPP / "__init__.py"


def stdlib_builtins_path() -> Path:
  return PY2CPP / "builtins.py"


def stdlib_module_paths() -> list[Path]:
  paths = [stdlib_builtins_path(), stdlib_init_path()]
  for rel in STDLIB_REL_PATHS:
    mod_py = PY2CPP.joinpath(*rel.split("/")).with_suffix(".py")
    if mod_py.is_file():
      paths.append(mod_py)
      continue
    pkg_init = PY2CPP.joinpath(*rel.split("/"), "__init__.py")
    if pkg_init.is_file():
      paths.append(pkg_init)
  return paths


def stdlib_module_path(rel: str) -> str:
  if not rel or rel == RUNTIME_PKG:
    return RUNTIME_PKG
  return f"{RUNTIME_PKG}/{rel.replace(chr(92), '/')}"


def header_for_module_path(module_path: str) -> str:
  if module_path == RUNTIME_PKG:
    return f"{RUNTIME_PKG}.h"
  return f"{module_path}.h"


def module_path_for_py(path: Path) -> str:
  rel = path.relative_to(PY2CPP)
  if rel.name == "__init__.py":
    parts = rel.parts[:-1]
    if not parts:
      return RUNTIME_PKG
    return stdlib_module_path("/".join(parts))
  return stdlib_module_path(str(rel.with_suffix("")).replace("\\", "/"))
