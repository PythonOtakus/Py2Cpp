"""翻译完成后写入 ``generated/.cache/architect/graph.json`` 语义图。"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..analysis.type_emit import field_ann_ast
from .nav_index import (
  build_module_shard,
  _should_update_module_shard,
)

if TYPE_CHECKING:
  from ..translator import Translator

ARCHITECT_GRAPH_VERSION = 2
ARCHITECT_CACHE_SUBDIR = ".cache/architect"
ARCHITECT_GRAPH_FILE = "graph.json"
ARCH_PLAN_SUFFIX = ".arch.json"

_EXPORT_SYMBOL_KINDS = frozenset({
  "class",
  "function",
  "type_alias",
  "enum",
  "enum_member",
  "union_variant",
  "delegate",
})

_GRAPH_SYMBOL_KINDS = frozenset({
  "class",
  "function",
  "field",
  "method",
  "type_alias",
  "enum",
  "enum_member",
  "property",
})

_SELECT_RE = re.compile(r"""\.select\s*\(\s*(['"])(.+?)\1""")


def architect_cache_dir(output_dir: Path) -> Path:
  return output_dir / ARCHITECT_CACHE_SUBDIR


def _graph_path(cache: Path) -> Path:
  return cache / ARCHITECT_GRAPH_FILE


def _module_imports(tr: Translator, module_path: str) -> list[str]:
  bindings = tr.module_import_bindings.get(module_path, {})
  paths = sorted({b.module_path for b in bindings.values() if b.module_path})
  return paths


def _compact_symbol(sym: dict[str, Any]) -> dict[str, Any]:
  kind = sym.get("kind")
  name = sym.get("name")
  if not isinstance(kind, str) or not isinstance(name, str):
    return {}
  if kind not in _GRAPH_SYMBOL_KINDS:
    return {}
  out: dict[str, Any] = {"kind": kind, "name": name}
  owner = sym.get("owner")
  if isinstance(owner, str) and owner:
    out["owner"] = owner
  role = sym.get("role")
  if isinstance(role, str) and role:
    out["role"] = role
  return out


def _module_symbols(tr: Translator, module_path: str) -> list[dict[str, Any]]:
  shard = build_module_shard(tr, module_path)
  if shard is None:
    return []
  out: list[dict[str, Any]] = []
  for sym in shard.get("symbols", []):
    if not isinstance(sym, dict):
      continue
    compact = _compact_symbol(sym)
    if compact:
      out.append(compact)
  return out


def _module_exports(tr: Translator, module_path: str) -> list[str]:
  names: list[str] = []
  for sym in _module_symbols(tr, module_path):
    if sym.get("kind") in _EXPORT_SYMBOL_KINDS:
      names.append(sym["name"])
  return sorted(set(names))


def _sym_endpoint(
  module_path: str,
  *,
  symbol: str,
  kind: str,
  owner: str | None = None,
) -> dict[str, Any]:
  ep: dict[str, Any] = {"module": module_path, "symbol": symbol, "kind": kind}
  if owner:
    ep["owner"] = owner
  return ep


def _annotation_type_names(node: ast.AST | None) -> list[str]:
  if node is None:
    return []
  if isinstance(node, ast.Name):
    return [node.id]
  if isinstance(node, ast.Subscript):
    return _annotation_type_names(node.value)
  if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
    return _annotation_type_names(node.left) + _annotation_type_names(node.right)
  if isinstance(node, ast.Attribute):
    return [ast.unparse(node)]
  return []


def _class_names_in_module(tr: Translator, module_path: str) -> set[str]:
  return {
    info.name
    for info in tr.classes.values()
    if info.module_path == module_path
  }


def _scan_select_refs(source: str, module_path: str) -> list[dict[str, Any]]:
  refs: list[dict[str, Any]] = []
  seen: set[str] = set()
  try:
    tree = ast.parse(source)
  except SyntaxError:
    tree = None
  if tree is not None:
    for node in ast.walk(tree):
      if not isinstance(node, ast.Call):
        continue
      func = node.func
      if not (
        isinstance(func, ast.Attribute)
        and func.attr == "select"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
      ):
        continue
      path = node.args[0].value
      if path in seen:
        continue
      seen.add(path)
      refs.append({
        "from": _sym_endpoint(module_path, symbol="<module>", kind="module"),
        "to": {"path": path},
        "kind": "select_path",
      })
  for m in _SELECT_RE.finditer(source):
    path = m.group(2)
    if path in seen:
      continue
    seen.add(path)
    refs.append({
      "from": _sym_endpoint(module_path, symbol="<module>", kind="module"),
      "to": {"path": path},
      "kind": "select_path",
    })
  return refs


def _collect_module_refs(tr: Translator, module_path: str) -> list[dict[str, Any]]:
  refs: list[dict[str, Any]] = []
  for dep in _module_imports(tr, module_path):
    refs.append({
      "from": module_path,
      "to": dep,
      "kind": "import",
    })

  local_classes = _class_names_in_module(tr, module_path)
  for info in tr.classes.values():
    if info.module_path != module_path:
      continue
    if info.is_enum or info.is_union or info.is_protocol or info.is_mixin:
      continue
    cls_ep = _sym_endpoint(module_path, symbol=info.name, kind="class")
    for base in info.bases:
      to_ep: dict[str, Any] = {"symbol": base, "kind": "class"}
      if base in local_classes:
        to_ep["module"] = module_path
      refs.append({"from": cls_ep, "to": to_ep, "kind": "inherit"})
    for field in info.fields:
      field_ep = _sym_endpoint(
        module_path, symbol=field, kind="field", owner=info.name,
      )
      refs.append({
        "from": field_ep,
        "to": cls_ep,
        "kind": "member_of",
      })
      ann = field_ann_ast(info, field)
      for type_name in _annotation_type_names(ann):
        if type_name in local_classes:
          refs.append({
            "from": field_ep,
            "to": _sym_endpoint(module_path, symbol=type_name, kind="class"),
            "kind": "field_type",
          })

  py_rel = module_path.replace("\\", "/")
  if not py_rel.endswith(".py"):
    py_rel = f"{py_rel}.py"
  py_path = tr._repo_root() / Path(py_rel)
  if py_path.is_file():
    try:
      refs.extend(_scan_select_refs(py_path.read_text(encoding="utf-8"), module_path))
    except OSError:
      pass
  return refs


def _ref_touches_module(ref: dict[str, Any], module_path: str) -> bool:
  frm = ref.get("from")
  if isinstance(frm, str):
    return frm == module_path
  if isinstance(frm, dict) and frm.get("module") == module_path:
    return True
  to = ref.get("to")
  if isinstance(to, str):
    return to == module_path
  if isinstance(to, dict) and to.get("module") == module_path:
    return True
  return False


def _build_module_graph(tr: Translator, module_path: str) -> dict[str, Any]:
  py_file = module_path.replace("\\", "/")
  if not py_file.endswith(".py"):
    py_file = f"{py_file}.py"
  return {
    "imports": _module_imports(tr, module_path),
    "exports": _module_exports(tr, module_path),
    "symbols": _module_symbols(tr, module_path),
    "pyFile": py_file,
  }


def write_architect_graph(tr: Translator) -> Path:
  """合并写入 ``<output>/.cache/architect/graph.json``；返回 graph 路径。"""
  cache = architect_cache_dir(tr.base_output_dir)
  cache.mkdir(parents=True, exist_ok=True)
  graph_path = _graph_path(cache)

  nav_manifest_rel = ".cache/nav/manifest.json"
  graph: dict[str, Any] = {"version": ARCHITECT_GRAPH_VERSION, "modules": {}, "refs": []}
  if graph_path.is_file():
    try:
      loaded = json.loads(graph_path.read_text(encoding="utf-8"))
      if isinstance(loaded.get("modules"), dict):
        graph["modules"] = loaded["modules"]
      if isinstance(loaded.get("refs"), list):
        graph["refs"] = loaded["refs"]
    except (OSError, json.JSONDecodeError):
      pass

  updated: list[str] = []
  for module_path in tr.module_order:
    if not _should_update_module_shard(tr, module_path):
      continue
    graph["modules"][module_path] = _build_module_graph(tr, module_path)
    updated.append(module_path)

  if updated:
    updated_set = set(updated)
    graph["refs"] = [
      ref for ref in graph["refs"]
      if isinstance(ref, dict) and not any(_ref_touches_module(ref, mod) for mod in updated_set)
    ]
    for module_path in updated:
      graph["refs"].extend(_collect_module_refs(tr, module_path))

  graph["version"] = ARCHITECT_GRAPH_VERSION
  graph["generatedRoot"] = tr._display_path(tr.base_output_dir)
  graph["repoRoot"] = tr._display_path(tr._repo_root())
  graph["navManifest"] = nav_manifest_rel
  graph["planSuffix"] = ARCH_PLAN_SUFFIX
  graph["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
  if updated:
    graph["lastUpdatedModules"] = updated

  graph_path.write_text(
    json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return graph_path
