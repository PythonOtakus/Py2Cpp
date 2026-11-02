"""Python 3.13 ``import`` / ``from … import`` 的静态解析与模块发现。

- 绝对/相对路径解析（PEP 328）
- 自入口与用户模块起传递闭包加载
- 标准库 ``from . import …`` 相对依赖
- ``#include "py2cpp/minimal.h"`` 仍由翻译器自动注入，用户无需手写
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..constant.ffi_layout import (
  find_ffi_source_file,
  ffi_import_parts_to_module_path,
  is_ffi_module_path,
)
from ..constant.stdlib_discovery import STDLIB_REL_PATHS, STDLIB_REL_PATH_SET
from ..constant.stdlib_layout import (
  RUNTIME_PKG,
  list_on_demand_stdlib_rels,
  resolve_stdlib_import_parts,
  stdlib_module_path,
  stdlib_rel_from_import_segment,
)
from .ir import CPP_RENAME

if TYPE_CHECKING:
  from ..translator import Translator

_RUNTIME_STDLIB_NAMES = STDLIB_REL_PATH_SET
_SKIP_IMPORT_MODULES = frozenset({"__future__", "typing", "collections", "collections.abc"})


@dataclass(frozen=True)
class ImportRequest:
  """一条待解析的 import 语句（仅模块顶层）。"""

  level: int
  module: str | None
  names: tuple[tuple[str, str | None], ...]
  is_star: bool
  is_plain_import: bool
  source_dotted: str | None = None


def dotted_import_to_module_path(dotted: str | None) -> str:
  """``py2cpp.util.list`` → ``py2cpp/util/list``；``ffi.windows`` → ``ffi/windows``；``py2cpp`` → 包根。"""
  if not dotted:
    return RUNTIME_PKG
  parts = dotted.split(".")
  ffi_path = ffi_import_parts_to_module_path(parts)
  if ffi_path is not None:
    return ffi_path
  if parts and parts[0] == RUNTIME_PKG:
    parts = parts[1:]
  if not parts:
    return RUNTIME_PKG
  resolved = resolve_stdlib_import_parts(parts)
  if resolved:
    return resolved
  return f"{RUNTIME_PKG}/{'/'.join(parts)}"


def module_path_package(module_path: str) -> str:
  if module_path == RUNTIME_PKG:
    return ""
  if "/" not in module_path:
    return ""
  return module_path.rsplit("/", 1)[0]


def _import_anchor_package(
  importer_path: str,
  runtime_root: Path | None,
  *,
  project_root: Path | None = None,
) -> str:
  """相对 import 锚点（对齐 PEP 328 ``__package__``）。

  - 包目录 ``…/pkg/__init__.py``：锚点为 ``…/pkg``（``importer_path``）。
  - 单文件 ``…/pkg/mod.py``：锚点为 **父包** ``…/pkg``，而非 ``…/pkg/mod``。
    故 ``py2cpp/serde/json.py`` 上 ``from ..util``（level=2）到 ``py2cpp``，
    ``from ...util``（level=3）应视为越界（勿与 level=2 解析到同一模块）。
  """
  if importer_path == RUNTIME_PKG:
    return RUNTIME_PKG
  if runtime_root is not None and importer_path.startswith(f"{RUNTIME_PKG}/"):
    rest = importer_path[len(f"{RUNTIME_PKG}/") :]
    if _pick_init_file(runtime_root / rest) is not None:
      return importer_path
  pkg = module_path_package(importer_path)
  if pkg:
    return pkg
  if project_root is not None and runtime_root is not None:
    py = _find_user_py_file(
      importer_path,
      project_root=project_root,
      runtime_root=runtime_root,
    )
    if py is not None:
      rel_dir = py.parent.resolve().relative_to(project_root.resolve())
      if rel_dir.parts:
        return rel_dir.as_posix()
      return ""
  return RUNTIME_PKG


def resolve_relative_module_path(
  importer_path: str,
  *,
  level: int,
  module: str | None,
  runtime_root: Path | None = None,
  project_root: Path | None = None,
) -> str:
  """将 ``ImportFrom`` 的 level/module 解析为 ``py2cpp/…`` 或 ``test/…`` 路径。"""
  if level < 0:
    raise ValueError("import level must be non-negative")
  base = _import_anchor_package(
    importer_path, runtime_root, project_root=project_root,
  )
  if level > 0:
    for step in range(level - 1):
      if base == RUNTIME_PKG:
        raise ValueError(
          f"relative import with {level} leading dot(s) from {importer_path!r} "
          f"escapes above {RUNTIME_PKG!r} (step {step + 1}/{level - 1})",
        )
      # 用户工程根路径为空串：``editor/foo`` 上 ``from ..command`` 升到根合法；
      # 已在根再升一级才越界（对齐 PEP 328；``py2cpp`` 包根由上支 RUNTIME_PKG 拦截）。
      if not base:
        raise ValueError(
          f"relative import with {level} leading dot(s) from {importer_path!r} "
          f"escapes above project root (step {step + 1}/{level - 1})",
        )
      base = module_path_package(base)
  if not module:
    return base
  tail = module.replace(".", "/")
  if base == RUNTIME_PKG:
    if not tail:
      return RUNTIME_PKG
    if tail in _RUNTIME_STDLIB_NAMES:
      return stdlib_module_path(tail)
    return f"{RUNTIME_PKG}/{tail}"
  if not base:
    return tail
  return f"{base}/{tail}" if tail else base


def absolute_dotted_to_module_path(dotted: str) -> str:
  return dotted_import_to_module_path(dotted)


def import_local_name(dotted: str, asname: str | None) -> str:
  if asname:
    return asname
  return dotted.split(".")[0]


def iter_module_import_requests(tree: ast.Module) -> list[ImportRequest]:
  out: list[ImportRequest] = []
  for node in tree.body:
    if isinstance(node, ast.ImportFrom):
      names = tuple((a.name, a.asname) for a in node.names)
      out.append(
        ImportRequest(
          level=node.level or 0,
          module=node.module,
          names=names,
          is_star=any(a.name == "*" for a in node.names),
          is_plain_import=False,
        )
      )
    elif isinstance(node, ast.Import):
      for alias in node.names:
        out.append(
          ImportRequest(
            level=0,
            module=None,
            names=((alias.name, alias.asname),),
            is_star=False,
            is_plain_import=True,
            source_dotted=alias.name,
          )
        )
  return out


class ModulePathConflictError(ValueError):
  """同名模块同时存在 ``.paw`` 与 ``.py``。"""


def _pick_source_file(directory: Path, stem: str) -> Path | None:
  """在 directory 下选择 ``stem.paw`` / ``stem.py``；二者皆在则报错。"""
  paw = directory / f"{stem}.paw"
  py = directory / f"{stem}.py"
  paw_ok = paw.is_file()
  py_ok = py.is_file()
  if paw_ok and py_ok:
    raise ModulePathConflictError(
      f"模块路径冲突: 同时存在 {paw.as_posix()} 与 {py.as_posix()}，"
      f"须只保留其一（Paw 用 .paw，兼容入口用 .py）"
    )
  if paw_ok:
    return paw
  if py_ok:
    return py
  return None


def _pick_init_file(package_dir: Path) -> Path | None:
  return _pick_source_file(package_dir, "__init__")


def _user_module_path_from_file(py_path: Path, project_root: Path) -> str:
  rel = py_path.resolve().relative_to(project_root.resolve())
  name = rel.name
  if name in ("__init__.py", "__init__.paw"):
    parent = rel.parent.as_posix()
    return f"{parent}/__init__" if parent != "." else "__init__"
  return rel.with_suffix("").as_posix()


def is_runtime_module_path(module_path: str) -> bool:
  return module_path == RUNTIME_PKG or module_path.startswith(f"{RUNTIME_PKG}/")


def _user_module_search_roots(project_root: Path, runtime_root: Path) -> list[Path]:
  """入口所在目录 + 仓库根（``runtime_root`` 父级，含 ``compiler/paw``）。"""
  roots: list[Path] = []
  for r in (project_root.resolve(), runtime_root.resolve().parent):
    if r not in roots:
      roots.append(r)
  return roots


def _find_user_py_file_under(
  module_path: str,
  *,
  root: Path,
  runtime_root: Path,
) -> Path | None:
  rel = module_path.replace("\\", "/")
  if rel == "__init__" or rel.endswith("/__init__"):
    pkg = rel[: -len("/__init__")] if rel.endswith("/__init__") else ""
    pkg_dir = (root / pkg) if pkg else root
    init = _pick_init_file(pkg_dir)
    if init is not None:
      try:
        init.resolve().relative_to(runtime_root.resolve())
        return None
      except ValueError:
        pass
      return init
    return None
  if "/" in rel or "\\" in rel:
    cand = _pick_source_file(root / Path(rel).parent, Path(rel).name)
  else:
    cand = _pick_source_file(root, rel)
  if cand is not None:
    try:
      cand.resolve().relative_to(runtime_root.resolve())
      return None
    except ValueError:
      pass
    return cand
  init = _pick_init_file(root / rel)
  if init is not None:
    try:
      init.resolve().relative_to(runtime_root.resolve())
      return None
    except ValueError:
      pass
    return init
  return None


def _find_user_py_file(
  module_path: str,
  *,
  project_root: Path,
  runtime_root: Path,
) -> Path | None:
  if is_runtime_module_path(module_path):
    return None
  if is_ffi_module_path(module_path):
    return find_ffi_source_file(module_path, project_root=project_root)
  for root in _user_module_search_roots(project_root, runtime_root):
    found = _find_user_py_file_under(
      module_path, root=root, runtime_root=runtime_root
    )
    if found is not None:
      return found
  return None


def _stdlib_py_path(runtime_root: Path, module_path: str) -> Path | None:
  if module_path == RUNTIME_PKG:
    return _pick_init_file(runtime_root)
  if not module_path.startswith(f"{RUNTIME_PKG}/"):
    return None
  rest = module_path[len(f"{RUNTIME_PKG}/") :]
  sub = _pick_source_file(runtime_root / Path(rest).parent, Path(rest).name) if "/" in rest else _pick_source_file(runtime_root, rest)
  if sub is not None:
    return sub
  return _pick_init_file(runtime_root / rest)


def discover_import_targets(
  importer_path: str,
  req: ImportRequest,
  *,
  project_root: Path,
  runtime_root: Path,
) -> list[str]:
  if req.is_plain_import:
    t = resolve_import_target_path(
      importer_path, req, project_root=project_root, runtime_root=runtime_root,
    )
    return [t] if t else []
  if req.level and req.module is None and not req.is_star:
    base = resolve_relative_module_path(
      importer_path,
      level=req.level,
      module=None,
      runtime_root=runtime_root,
      project_root=project_root,
    )
    out: list[str] = []
    for name, _ in req.names:
      if name == "*":
        continue
      if base == RUNTIME_PKG:
        rel = stdlib_rel_from_import_segment(name)
        if rel is not None:
          out.append(stdlib_module_path(rel))
        elif _stdlib_py_path(runtime_root, f"{RUNTIME_PKG}/{name}"):
          out.append(f"{RUNTIME_PKG}/{name}")
        else:
          out.append(RUNTIME_PKG)
        continue
      sub = f"{base}/{name}" if base else name
      if _stdlib_py_path(runtime_root, sub):
        out.append(sub)
      elif _find_user_py_file(
        sub, project_root=project_root, runtime_root=runtime_root,
      ):
        out.append(sub)
    return out
  t = resolve_import_target_path(
    importer_path, req, project_root=project_root, runtime_root=runtime_root,
  )
  return [t] if t else []


def resolve_import_target_path(
  importer_path: str,
  req: ImportRequest,
  *,
  project_root: Path,
  runtime_root: Path,
) -> str | None:
  # 仅跳过绝对 ``from collections import …``；相对 ``from .util import *`` 是 py2cpp 子包。
  if (
    not req.is_plain_import
    and (req.level or 0) == 0
    and req.module in _SKIP_IMPORT_MODULES
  ):
    return None
  if req.is_plain_import:
    assert req.source_dotted is not None
    path = absolute_dotted_to_module_path(req.source_dotted)
  elif req.level:
    path = resolve_relative_module_path(
      importer_path,
      level=req.level,
      module=req.module,
      runtime_root=runtime_root,
      project_root=project_root,
    )
  else:
    path = absolute_dotted_to_module_path(req.module)
  if _stdlib_py_path(runtime_root, path):
    return path
  if _find_user_py_file(path, project_root=project_root, runtime_root=runtime_root):
    return path
  # 绝对 import 默认落在 ``py2cpp/…``；标准库未命中时再试仓库顶层用户包
  # （如 ``compiler.paw.frontend.source`` → C0 自举种子）。
  prefix = f"{RUNTIME_PKG}/"
  if path.startswith(prefix):
    alt = path[len(prefix) :]
    if alt and _find_user_py_file(
      alt, project_root=project_root, runtime_root=runtime_root
    ):
      return alt
  if is_ffi_module_path(path) and find_ffi_source_file(path, project_root=project_root):
    return path
  return None


def discover_translation_modules(
  entry_py: Path,
  *,
  include_stdlib: bool,
  runtime_root: Path,
  project_root: Path | None = None,
) -> list[tuple[str, str]]:
  entry_py = entry_py.resolve()
  if project_root is None:
    project_root = entry_py.parent
  project_root = project_root.resolve()
  runtime_root = runtime_root.resolve()

  entry_mod = _user_module_path_from_file(entry_py, project_root)
  runtime_init = _pick_init_file(runtime_root)
  if runtime_init is not None and entry_py.resolve() == runtime_init.resolve():
    entry_mod = RUNTIME_PKG

  seen: set[str] = set()
  order: list[str] = []
  sources: dict[str, str] = {}

  def enqueue(path: str) -> None:
    if path in seen:
      return
    seen.add(path)
    order.append(path)

  def load_source(path: str) -> str | None:
    if path in sources:
      return sources[path]
    p = _stdlib_py_path(runtime_root, path)
    if p is None:
      p = _find_user_py_file(
        path, project_root=project_root, runtime_root=runtime_root,
      )
    if p is None and is_ffi_module_path(path):
      p = find_ffi_source_file(path, project_root=project_root)
    if p is None:
      return None
    text = p.read_text(encoding="utf-8").replace("\ufeff", "")
    sources[path] = text
    return text

  enqueue(entry_mod)
  if include_stdlib and entry_mod == RUNTIME_PKG:
    for n in STDLIB_REL_PATHS:
      enqueue(stdlib_module_path(n))
    for rel in list_on_demand_stdlib_rels():
      enqueue(stdlib_module_path(rel))
    # 模板经 ``#include "ffi/…"`` 间接依赖；bootstrap 须始终写出对应生成头
    from ..constant.template_ffi_includes import ffi_modules_required_by_templates

    for ffi_mp in ffi_modules_required_by_templates():
      enqueue(ffi_mp)
  idx = 0
  while idx < len(order):
    mp = order[idx]
    idx += 1
    code = load_source(mp)
    if code is None:
      continue
    from ..frontend.api import parse_module
    from ..frontend.dialect import dialect_from_path

    src_path = ""
    p_found = _stdlib_py_path(runtime_root, mp) or _find_user_py_file(
      mp, project_root=project_root, runtime_root=runtime_root,
    )
    if p_found is None and is_ffi_module_path(mp):
      p_found = find_ffi_source_file(mp, project_root=project_root)
    if p_found is not None:
      src_path = str(p_found)
    parsed = parse_module(
      code,
      path=src_path or f"<{mp}>",
      dialect=dialect_from_path(src_path) if src_path else None,
    )
    tree = parsed.tree
    # seed ``NO_MATERIALIZE`` 空树：从 MidIR 直构补 import，否则相对依赖发现断裂
    if (
      not tree.body
      and parsed.mid is not None
      and getattr(parsed, "mid_emit_ok", False)
    ):
      from compiler.py.mid.ast_from_mid import ast_module_from_mid

      tree = ast_module_from_mid(
        parsed.mid, filename=src_path or f"<{mp}>"
      )
    for req in iter_module_import_requests(tree):
      for target in discover_import_targets(
        mp, req, project_root=project_root, runtime_root=runtime_root,
      ):
        if not include_stdlib and target.startswith(f"{RUNTIME_PKG}/"):
          continue
        enqueue(target)

  if include_stdlib and not any(p.startswith(f"{RUNTIME_PKG}/") for p in order):
    enqueue(RUNTIME_PKG)

  out: list[tuple[str, str]] = []
  stdlib_set = {mp for mp in order if mp.startswith(f"{RUNTIME_PKG}/")}
  stdlib_ordered = [
    stdlib_module_path(n)
    for n in STDLIB_REL_PATHS
    if stdlib_module_path(n) in stdlib_set
  ]
  stdlib_ordered += [
    p for p in order
    if p.startswith(f"{RUNTIME_PKG}/") and p not in stdlib_ordered
  ]
  user = [mp for mp in order if not mp.startswith(f"{RUNTIME_PKG}/")]
  for mp in stdlib_ordered + user:
    code = sources.get(mp)
    if code is not None:
      out.append((mp, code))
  return out


def module_all_names(tree: ast.Module) -> list[str] | None:
  for node in tree.body:
    if isinstance(node, ast.Assign):
      for t in node.targets:
        if isinstance(t, ast.Name) and t.id == "__all__":
          val = node.value
          if isinstance(val, (ast.List, ast.Tuple)):
            names: list[str] = []
            for elt in val.elts:
              if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                names.append(elt.value)
            return names
  return None


def public_export_names(tree: ast.Module) -> list[str]:
  explicit = module_all_names(tree)
  if explicit is not None:
    return explicit
  names: list[str] = []
  for node in tree.body:
    if isinstance(node, ast.ClassDef):
      if not node.name.startswith("_"):
        names.append(node.name)
    elif isinstance(node, ast.FunctionDef):
      if not node.name.startswith("_"):
        names.append(node.name)
  return names
