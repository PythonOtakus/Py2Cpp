"""翻译完成后写入 ``generated/.cache/nav/`` 符号索引（Python ↔ C++ 双向跳转）。"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..analysis.ir import ClassInfo, escape_cpp_param
from ..analysis.type_emit import field_ann_ast, field_storage_cpp
from ..analysis.module_namespace import namespace_qualifier_for_module, qualify_symbol_in_module
from ..analysis.patterns import property_getter_method_for
from ..constant.stdlib_layout import RUNTIME_PKG

if TYPE_CHECKING:
  from ..translator import Translator

NAV_INDEX_VERSION = 2
NAV_CACHE_SUBDIR = ".cache/nav"
NAV_MANIFEST = "manifest.json"
NAV_MODULES_DIR = "modules"


@dataclass(frozen=True)
class _CppSite:
  file: str
  line: int


def nav_cache_dir(output_dir: Path) -> Path:
  return output_dir / NAV_CACHE_SUBDIR


def module_shard_name(module_path: str) -> str:
  """``py2cpp/util/list`` → ``py2cpp/util/list.json``（与 ``pyFile`` 模块路径同形）。"""
  return f"{module_path.replace('\\', '/').strip('/')}.json"


def module_shard_rel(module_path: str) -> str:
  return f"{NAV_MODULES_DIR}/{module_shard_name(module_path)}"


def _legacy_module_shard_name(module_path: str) -> str:
  safe = module_path.replace("\\", "/").strip("/").replace("/", "__")
  return f"{safe}.json"


def _py_span(node: ast.AST) -> dict[str, int]:
  lineno = int(getattr(node, "lineno", 0) or 0)
  end = int(getattr(node, "end_lineno", lineno) or lineno)
  col = getattr(node, "col_offset", None)
  out: dict[str, int] = {"line": lineno, "endLine": end}
  if col is not None:
    out["column"] = int(col) + 1
  return out


def _first_line_match(lines: list[str], patterns: list[re.Pattern[str]], *, start: int = 0) -> int | None:
  for i in range(start, len(lines)):
    text = lines[i]
    for pat in patterns:
      if pat.search(text):
        return i + 1
  return None


def _looks_like_method_call(line: str, cpp_member: str) -> bool:
  """``this->fn(`` / ``->fn(`` / ``.fn(`` 为调用点，非方法定义行。"""
  return bool(
    re.search(rf"(?:this->|->|\.){re.escape(cpp_member)}\s*\(", line)
  )


def _impl_definition_line(
  lines: list[str],
  patterns: list[re.Pattern[str]],
  cpp_member: str,
) -> int | None:
  """``.inl`` 实现行：跳过同文件内的 ``this->method(`` 调用，优先 ``::method(`` 定义。"""
  if not lines:
    return None
  candidates: list[tuple[int, bool]] = []
  for i, text in enumerate(lines):
    if not any(pat.search(text) for pat in patterns):
      continue
    if _looks_like_method_call(text, cpp_member):
      continue
    qualified = bool(re.search(rf"::\s*{re.escape(cpp_member)}\s*\(", text))
    candidates.append((i + 1, qualified))
  if not candidates:
    return None
  for line_no, is_qualified in candidates:
    if is_qualified:
      return line_no
  return candidates[0][0]


def _read_lines(path: Path | None) -> list[str]:
  if path is None or not path.is_file():
    return []
  try:
    return path.read_text(encoding="utf-8").splitlines()
  except OSError:
    return []


def _method_cpp_patterns(info: ClassInfo, method_name: str, cpp_member: str) -> tuple[list[re.Pattern[str]], list[re.Pattern[str]]]:
  qual = info.module_path.replace("/", "::")
  ns = namespace_qualifier_for_module(info.module_path)
  cls = info.cpp_name()
  if ns:
    qual_prefix = f"{ns}::{cls}"
    short_prefix = cls
  else:
    qual_prefix = cls
    short_prefix = cls

  if method_name == "__init__":
    decl = [re.compile(rf"\b{re.escape(cls)}\s*\(")]
    impl = [
      re.compile(rf"\b{re.escape(qual_prefix)}\s*::\s*{re.escape(cls)}\s*\("),
      re.compile(rf"\b{re.escape(short_prefix)}\s*::\s*{re.escape(cls)}\s*\("),
      re.compile(rf"\b{re.escape(cls)}\s*\("),
    ]
    return decl, impl
  if method_name == "__del__":
    decl = [re.compile(rf"~{re.escape(cls)}\s*\(")]
    impl = [
      re.compile(rf"\b{re.escape(qual_prefix)}\s*::\s*~{re.escape(cls)}\s*\("),
      re.compile(rf"~{re.escape(cls)}\s*\("),
    ]
    return decl, impl

  decl = [re.compile(rf"\b{re.escape(cpp_member)}\s*\(")]
  impl = [
    re.compile(
      rf"\b{re.escape(qual_prefix)}\s*::\s*{re.escape(cpp_member)}\s*\(",
    ),
    re.compile(rf"\b{re.escape(short_prefix)}\s*::\s*{re.escape(cpp_member)}\s*\("),
    re.compile(rf"\b{re.escape(cpp_member)}\s*\("),
  ]
  return decl, impl


def _field_cpp_patterns(info: ClassInfo, field_cpp: str) -> list[re.Pattern[str]]:
  return [
    re.compile(rf"\b{re.escape(field_cpp)}\s*;"),
    re.compile(rf"\b{re.escape(field_cpp)}\s*="),
  ]


def _class_cpp_patterns(info: ClassInfo) -> list[re.Pattern[str]]:
  cls = info.cpp_name()
  return [
    re.compile(rf"\b(class|struct)\s+{re.escape(cls)}\b"),
  ]


def _is_class_forward_decl(line: str, cls: str) -> bool:
  """``class Foo;`` / ``template<...> class Foo;``（含同一行内 namespace 块中的前向声明）。"""
  if not re.search(rf"\b(class|struct)\s+{re.escape(cls)}\b", line):
    return False
  return bool(re.search(rf"\b(class|struct)\s+{re.escape(cls)}\s*;", line))


def _class_decl_line(lines: list[str], info: ClassInfo) -> int | None:
  """类定义起始行；跳过 ``.h`` 顶部的 ``class PyList;`` 前向声明。"""
  cls = info.cpp_name()
  name_pat = re.compile(rf"\b(class|struct)\s+{re.escape(cls)}\b")
  for i, line in enumerate(lines):
    if not name_pat.search(line):
      continue
    if _is_class_forward_decl(line, cls):
      continue
    for j in range(i, min(i + 5, len(lines))):
      if "{" in lines[j]:
        return i + 1
      if j == i and _is_class_forward_decl(lines[j], cls):
        break
  return None


def _module_function_cpp_patterns(
  tr: Translator,
  module_path: str,
  cpp_name: str,
) -> tuple[list[re.Pattern[str]], list[re.Pattern[str]]]:
  ns = namespace_qualifier_for_module(module_path)
  decl = [re.compile(rf"\b{re.escape(cpp_name)}\s*\(")]
  if ns:
    impl = [
      re.compile(rf"\b{re.escape(ns)}\s*::\s*{re.escape(cpp_name)}\s*\("),
      re.compile(rf"\b{re.escape(cpp_name)}\s*\("),
    ]
  else:
    impl = [re.compile(rf"\b{re.escape(cpp_name)}\s*\(")]
  return decl, impl


def _resolve_module_artifacts(tr: Translator, module_path: str) -> dict[str, str | None]:
  """模块生成物路径（相对仓库根）；只读模块仍指向已有文件。"""
  out: dict[str, str | None] = {"h": None, "inl": None, "cpp": None}
  if tr._is_stdlib_module(module_path):
    hpath = tr._stdlib_artifact_path(module_path, ".h")
    ipath = tr._stdlib_artifact_path(module_path, ".inl")
    if hpath.is_file():
      out["h"] = tr._display_path(hpath)
    if ipath.is_file():
      out["inl"] = tr._display_path(ipath)
    return out

  rel_mp = tr._user_module_output_relpath(module_path)
  hpath = tr.entry_output_dir / f"{rel_mp}.h"
  ipath = tr.entry_output_dir / f"{rel_mp}.inl"
  if hpath.is_file():
    out["h"] = tr._display_path(hpath)
  if ipath.is_file():
    out["inl"] = tr._display_path(ipath)
  if module_path == tr.entry_module_path:
    stem = tr.module_name
    cpp_path = tr.entry_output_dir / f"{stem}.cpp"
    if cpp_path.is_file():
      out["cpp"] = tr._display_path(cpp_path)
  return out


def _should_update_module_shard(tr: Translator, module_path: str) -> bool:
  if module_path == tr.entry_module_path:
    return True
  if tr._is_stdlib_module(module_path):
    return tr._can_write_stdlib_artifact(module_path)
  return module_path in tr.module_order


def _collect_class_symbols(
  tr: Translator,
  info: ClassInfo,
  *,
  h_lines: list[str],
  inl_lines: list[str],
  cpp_lines: list[str],
) -> list[dict[str, Any]]:
  if info.is_descriptor or info.is_mixin or info.is_annotation or info.is_variant_mixin:
    return []
  if tr._is_type_marker(info):
    return []

  symbols: list[dict[str, Any]] = []
  qual = qualify_symbol_in_module(info.module_path, info.cpp_name())
  cls_decl_line = _class_decl_line(h_lines, info)
  cls_entry: dict[str, Any] = {
    "kind": "class",
    "module": info.module_path,
    "name": info.name,
    "cppName": info.cpp_name(),
    "cppQual": qual,
    "py": {
      "file": tr._module_source_file_path(info.module_path),
      **_py_span(info.node),
    },
    "cpp": {},
  }
  if cls_decl_line is not None:
    cls_entry["cpp"]["decl"] = {"line": cls_decl_line}
  symbols.append(cls_entry)

  for field in info.fields:
    if field.startswith("_") and field_ann_ast(info, field) is None and not field_storage_cpp(info, field):
      continue
    field_cpp = info.cpp_member_name(field)
    node = info.field_defaults.get(field)
    if node is None:
      for stmt in info.node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == field:
          node = stmt
          break
    py_span = _py_span(node) if node is not None else {"line": info.node.lineno, "endLine": info.node.lineno}
    decl_line = _first_line_match(h_lines, _field_cpp_patterns(info, field_cpp))
    entry: dict[str, Any] = {
      "kind": "field",
      "module": info.module_path,
      "owner": info.name,
      "name": field,
      "cppName": field_cpp,
      "py": {"file": tr._module_source_file_path(info.module_path), **py_span},
      "cpp": {},
    }
    if decl_line is not None:
      entry["cpp"]["decl"] = {"line": decl_line}
    symbols.append(entry)

  for prop_name, prop in info.properties.items():
    if prop.getter is not None:
      getter_cpp = property_getter_method_for(prop_name)
      decl_p, impl_p = _method_cpp_patterns(info, prop_name, getter_cpp)
      symbols.append(_method_symbol(
        tr, info, prop_name, prop.getter, getter_cpp, decl_p, impl_p,
        h_lines, inl_lines, cpp_lines, kind="property",
      ))
    if prop.setter is not None:
      setter_cpp = f"set_{escape_cpp_param(prop_name)}"
      decl_p, impl_p = _method_cpp_patterns(info, prop_name, setter_cpp)
      symbols.append(_method_symbol(
        tr, info, prop_name, prop.setter, setter_cpp, decl_p, impl_p,
        h_lines, inl_lines, cpp_lines, kind="property",
      ))

  for method in info.iter_methods():
    if method.name.startswith("__") and method.name not in (
      "__init__", "__del__", "__copy__", "__move__", "__repr__", "__str__",
      "__bool__", "__getitem__", "__setitem__", "__len__", "__contains__",
      "__iter__", "__next__", "__enter__", "__exit__",
    ):
      if method.name.endswith("__"):
        continue
    mcpp = info.cpp_member_name(method.name)
    decl_p, impl_p = _method_cpp_patterns(info, method.name, mcpp)
    symbols.append(_method_symbol(
      tr, info, method.name, method, mcpp, decl_p, impl_p,
      h_lines, inl_lines, cpp_lines, kind="method",
    ))

  return symbols


def _method_symbol(
  tr: Translator,
  info: ClassInfo,
  py_name: str,
  node: ast.AST,
  cpp_member: str,
  decl_patterns: list[re.Pattern[str]],
  impl_patterns: list[re.Pattern[str]],
  h_lines: list[str],
  inl_lines: list[str],
  cpp_lines: list[str],
  *,
  kind: str,
) -> dict[str, Any]:
  decl_line = _first_line_match(h_lines, decl_patterns)
  impl_line = _impl_definition_line(inl_lines, impl_patterns, cpp_member)
  if impl_line is None:
    impl_line = _impl_definition_line(cpp_lines, impl_patterns, cpp_member)
  entry: dict[str, Any] = {
    "kind": kind,
    "module": info.module_path,
    "owner": info.name,
    "name": py_name,
    "cppName": cpp_member,
    "py": {
      "file": tr._module_source_file_path(info.module_path),
      **_py_span(node),
    },
    "cpp": {},
  }
  if decl_line is not None:
    entry["cpp"]["decl"] = {"line": decl_line}
  if impl_line is not None:
    entry["cpp"]["impl"] = {"line": impl_line}
  return entry


def build_module_shard(tr: Translator, module_path: str) -> dict[str, Any] | None:
  artifacts = _resolve_module_artifacts(tr, module_path)
  if not any(artifacts.values()):
    return None

  repo = tr._repo_root()
  h_lines = _read_lines(repo / artifacts["h"] if artifacts["h"] else None)
  inl_lines = _read_lines(repo / artifacts["inl"] if artifacts["inl"] else None)
  cpp_lines = _read_lines(repo / artifacts["cpp"] if artifacts["cpp"] else None)

  symbols: list[dict[str, Any]] = []
  for info in tr.classes.values():
    if info.module_path != module_path:
      continue
    symbols.extend(_collect_class_symbols(
      tr, info, h_lines=h_lines, inl_lines=inl_lines, cpp_lines=cpp_lines,
    ))

  for mp, func in tr.module_functions:
    if mp != module_path:
      continue
    if func.name == "main":
      continue
    cpp_name = tr._module_function_cpp_name(module_path, func)
    decl_p, impl_p = _module_function_cpp_patterns(tr, module_path, cpp_name)
    decl_line = _first_line_match(h_lines, decl_p)
    impl_line = _impl_definition_line(inl_lines, impl_p, cpp_name)
    if impl_line is None:
      impl_line = _impl_definition_line(cpp_lines, impl_p, cpp_name)
    entry: dict[str, Any] = {
      "kind": "function",
      "module": module_path,
      "name": func.name,
      "cppName": cpp_name,
      "py": {
        "file": tr._module_source_file_path(module_path),
        **_py_span(func),
      },
      "cpp": {},
    }
    if decl_line is not None:
      entry["cpp"]["decl"] = {"line": decl_line}
    if impl_line is not None:
      entry["cpp"]["impl"] = {"line": impl_line}
    symbols.append(entry)

  return {
    "version": NAV_INDEX_VERSION,
    "module": module_path,
    "pyFile": tr._module_source_file_path(module_path),
    "artifacts": artifacts,
    "symbols": symbols,
    "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  }


def write_nav_index(tr: Translator) -> Path:
  """写入/合并 ``<output>/.cache/nav/`` 索引；返回 manifest 路径。"""
  cache = nav_cache_dir(tr.base_output_dir)
  modules_dir = cache / NAV_MODULES_DIR
  modules_dir.mkdir(parents=True, exist_ok=True)
  manifest_path = cache / NAV_MANIFEST

  manifest: dict[str, Any] = {"version": NAV_INDEX_VERSION, "modules": {}}
  if manifest_path.is_file():
    try:
      manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
      manifest.setdefault("modules", {})
    except (OSError, json.JSONDecodeError):
      pass

  manifest["generatedRoot"] = tr._display_path(tr.base_output_dir)
  manifest["repoRoot"] = tr._display_path(tr._repo_root())
  manifest["version"] = NAV_INDEX_VERSION
  manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

  updated_modules: list[str] = []
  for module_path in tr.module_order:
    if not _should_update_module_shard(tr, module_path):
      continue
    shard = build_module_shard(tr, module_path)
    if shard is None:
      continue
    shard_rel = module_shard_rel(module_path)
    shard_path = cache / shard_rel
    shard_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path = modules_dir / _legacy_module_shard_name(module_path)
    if legacy_path.is_file() and legacy_path != shard_path:
      try:
        legacy_path.unlink()
      except OSError:
        pass
    shard_path.write_text(
      json.dumps(shard, ensure_ascii=False, indent=2) + "\n",
      encoding="utf-8",
    )
    manifest["modules"][module_path] = {
      "shard": shard_rel.replace("\\", "/"),
      "pyFile": shard["pyFile"],
      "artifacts": shard["artifacts"],
      "updatedAt": shard["updatedAt"],
      "symbolCount": len(shard["symbols"]),
    }
    updated_modules.append(module_path)

  manifest_path.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return manifest_path
