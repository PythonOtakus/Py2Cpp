"""``paw/`` 源树路径 helper（``analysis/stubs`` 共用）。"""
from __future__ import annotations

from pathlib import Path

from ...constant.stdlib_discovery import STDLIB_REL_PATHS

RUNTIME_PKG = "paw"
REPO_ROOT = Path(__file__).resolve().parents[3]
PY2CPP = REPO_ROOT / "lib" / "paw"


def _pick(path_no_suffix: Path) -> Path | None:
  for suf in (".paw", ".py"):
    p = path_no_suffix.with_suffix(suf)
    if p.is_file():
      return p
  return None


def _pick_init(package_dir: Path) -> Path | None:
  return _pick(package_dir / "__init__")


def stdlib_init_path() -> Path:
  p = _pick_init(PY2CPP)
  if p is None:
    raise FileNotFoundError(f"missing stdlib package root under {PY2CPP}")
  return p


def stdlib_builtins_path() -> Path:
  p = _pick(PY2CPP / "builtins")
  if p is None:
    raise FileNotFoundError(f"missing builtins under {PY2CPP}")
  return p


def stdlib_module_paths() -> list[Path]:
  paths = [stdlib_builtins_path(), stdlib_init_path()]
  for rel in STDLIB_REL_PATHS:
    parts = rel.split("/")
    mod = _pick(PY2CPP.joinpath(*parts))
    if mod is not None:
      paths.append(mod)
      continue
    pkg_init = _pick_init(PY2CPP.joinpath(*parts))
    if pkg_init is not None:
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
  if rel.stem == "__init__" and rel.suffix in (".py", ".paw"):
    parts = rel.parts[:-1]
    if not parts:
      return RUNTIME_PKG
    return stdlib_module_path("/".join(parts))
  return stdlib_module_path(str(rel.with_suffix("")).replace("\\", "/"))


def parse_stdlib_source(path: Path):
  """读标准库源为扫描用 AST（``.paw`` 经 Paw→Mid→``module_tree_from_mid``）。

  生产 ``parse_module`` 保持空 tree；stubs 扫描用 Mid 桥物化，**不** ``ast.parse`` 源文件。
  """
  from compiler.py.mid.tree_from_mid import module_tree_from_mid
  from ...frontend.api import parse_module_file

  parsed = parse_module_file(path, use_cache=True)
  if parsed.mid is None:
    raise SyntaxError(f"{path}: 无 MidIR，无法为 stubs 构建扫描树")
  return module_tree_from_mid(parsed.mid, filename=str(path))
