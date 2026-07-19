"""翻译完成后写入 ``generated/.cache/nav/`` 符号索引（Python ↔ C++ 双向跳转）。"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..analysis.ir import ClassInfo, PropertyDef
from ..analysis.type_emit import field_ann_ast, field_storage_cpp
from ..analysis.module_namespace import namespace_qualifier_for_module, qualify_symbol_in_module
from ..analysis.patterns import (
  property_getter_method_for,
  property_postsetter_method_for,
  property_setter_method_for,
)

if TYPE_CHECKING:
  from ..translator import Translator

NAV_INDEX_VERSION = 3
NAV_CACHE_SUBDIR = ".cache/nav"
NAV_MANIFEST = "manifest.json"
NAV_MODULES_DIR = "modules"

# 对外可见 / 常用于跳转的 dunder；其余双下划线结尾名跳过（私有实现）
_DUNDER_ALLOWLIST = frozenset({
  "__init__", "__del__", "__copy__", "__move__", "__repr__", "__str__",
  "__bool__", "__getitem__", "__setitem__", "__delitem__", "__len__", "__contains__",
  "__iter__", "__next__", "__reversed__", "__enter__", "__exit__",
  "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__",
  "__add__", "__sub__", "__mul__", "__truediv__", "__floordiv__", "__mod__", "__pow__",
  "__iadd__", "__isub__", "__imul__", "__itruediv__", "__ifloordiv__", "__imod__",
  "__and__", "__or__", "__xor__", "__invert__", "__lshift__", "__rshift__",
  "__neg__", "__pos__", "__abs__", "__hash__", "__call__", "__await__",
  "__aenter__", "__aexit__", "__anext__", "__int__", "__float__", "__index__",
})


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


def _py_span_lineno(lineno: int) -> dict[str, int]:
  return {"line": lineno, "endLine": lineno}


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


def _is_class_forward_decl(line: str, cls: str) -> bool:
  """``class Foo;`` / ``template<...> class Foo;``（含同一行内 namespace 块中的前向声明）。"""
  if not re.search(rf"\b(class|struct)\s+{re.escape(cls)}\b", line):
    return False
  return bool(re.search(rf"\b(class|struct)\s+{re.escape(cls)}\s*;", line))


def _class_decl_line(lines: list[str], info: ClassInfo) -> int | None:
  """类 / ``enum class`` 定义起始行；跳过 ``.h`` 顶部的前向声明。"""
  cls = info.cpp_name()
  enum_pat = re.compile(rf"\benum\s+class\s+{re.escape(cls)}\b")
  name_pat = re.compile(rf"\b(class|struct)\s+{re.escape(cls)}\b")
  for i, line in enumerate(lines):
    if enum_pat.search(line):
      for j in range(i, min(i + 5, len(lines))):
        if "{" in lines[j]:
          return i + 1
      return i + 1
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


def _using_alias_patterns(name: str) -> list[re.Pattern[str]]:
  return [
    re.compile(rf"\busing\s+{re.escape(name)}\s*="),
    re.compile(rf"\busing\s+{re.escape(name)}\s*;"),
  ]


def _enum_member_patterns(name: str) -> list[re.Pattern[str]]:
  return [
    re.compile(rf"^\s*{re.escape(name)}\s*="),
    re.compile(rf"^\s*{re.escape(name)}\s*,?\s*$"),
    re.compile(rf"^\s*{re.escape(name)}\s*,"),
  ]


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


def _skip_dunder_method(name: str) -> bool:
  if not name.startswith("__"):
    return False
  if name in _DUNDER_ALLOWLIST:
    return False
  return name.endswith("__")


def _py_file(tr: Translator, module_path: str) -> str:
  return tr._module_source_file_path(module_path)


def _base_symbol(
  *,
  kind: str,
  module: str,
  name: str,
  cpp_name: str,
  py_file: str,
  py_span: dict[str, int],
  owner: str | None = None,
  cpp_qual: str | None = None,
  role: str | None = None,
) -> dict[str, Any]:
  entry: dict[str, Any] = {
    "kind": kind,
    "module": module,
    "name": name,
    "cppName": cpp_name,
    "py": {"file": py_file, **py_span},
    "cpp": {},
  }
  if owner is not None:
    entry["owner"] = owner
  if cpp_qual is not None:
    entry["cppQual"] = cpp_qual
  if role is not None:
    entry["role"] = role
  return entry


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
  role: str | None = None,
  owner: str | None = None,
) -> dict[str, Any]:
  decl_line = _first_line_match(h_lines, decl_patterns)
  impl_line = _impl_definition_line(inl_lines, impl_patterns, cpp_member)
  if impl_line is None:
    impl_line = _impl_definition_line(cpp_lines, impl_patterns, cpp_member)
  entry = _base_symbol(
    kind=kind,
    module=info.module_path,
    name=py_name,
    cpp_name=cpp_member,
    py_file=_py_file(tr, info.module_path),
    py_span=_py_span(node),
    owner=owner if owner is not None else info.name,
    role=role,
  )
  if decl_line is not None:
    entry["cpp"]["decl"] = {"line": decl_line}
  if impl_line is not None:
    entry["cpp"]["impl"] = {"line": impl_line}
  return entry


def _append_property_symbols(
  tr: Translator,
  info: ClassInfo,
  prop_name: str,
  prop: PropertyDef,
  h_lines: list[str],
  inl_lines: list[str],
  cpp_lines: list[str],
  symbols: list[dict[str, Any]],
) -> None:
  if prop.getter is not None:
    getter_cpp = property_getter_method_for(prop_name)
    decl_p, impl_p = _method_cpp_patterns(info, prop_name, getter_cpp)
    symbols.append(_method_symbol(
      tr, info, prop_name, prop.getter, getter_cpp, decl_p, impl_p,
      h_lines, inl_lines, cpp_lines, kind="property", role="getter",
    ))
  if prop.setter is not None:
    setter_cpp = property_setter_method_for(prop_name)
    decl_p, impl_p = _method_cpp_patterns(info, prop_name, setter_cpp)
    symbols.append(_method_symbol(
      tr, info, prop_name, prop.setter, setter_cpp, decl_p, impl_p,
      h_lines, inl_lines, cpp_lines, kind="property", role="setter",
    ))
  if prop.postsetter is not None:
    post_cpp = property_postsetter_method_for(prop_name)
    decl_p, impl_p = _method_cpp_patterns(info, prop_name, post_cpp)
    symbols.append(_method_symbol(
      tr, info, prop_name, prop.postsetter, post_cpp, decl_p, impl_p,
      h_lines, inl_lines, cpp_lines, kind="property", role="postsetter",
    ))


def _variant_class_node(info: ClassInfo, variant_name: str) -> ast.AST:
  for stmt in info.node.body:
    if isinstance(stmt, ast.ClassDef) and stmt.name == variant_name:
      return stmt
  return info.node


def _hosts_using_mixin(tr: Translator, mixin: ClassInfo) -> list[ClassInfo]:
  return [
    host for host in tr.classes.values()
    if not host.is_mixin
    and not host.is_annotation
    and mixin.name in getattr(host, "bases", ())
  ]


def _collect_type_alias_symbols(
  tr: Translator,
  *,
  module_path: str,
  owner: str | None,
  aliases: Any,
  h_lines: list[str],
  py_only: bool,
  search_start: int = 0,
) -> list[dict[str, Any]]:
  symbols: list[dict[str, Any]] = []
  items: list[Any]
  if isinstance(aliases, dict):
    items = list(aliases.values())
  else:
    items = list(aliases or [])
  for alias in items:
    name = alias.name
    lineno = int(getattr(alias, "lineno", 0) or 0)
    if lineno <= 0 and hasattr(alias, "value"):
      lineno = int(getattr(alias.value, "lineno", 0) or 0)
    span = _py_span_lineno(lineno) if lineno > 0 else _py_span_lineno(1)
    entry = _base_symbol(
      kind="type_alias",
      module=module_path,
      name=name,
      cpp_name=name,
      py_file=_py_file(tr, module_path),
      py_span=span,
      owner=owner,
      cpp_qual=qualify_symbol_in_module(module_path, name) if owner is None else None,
    )
    if not py_only:
      decl_line = _first_line_match(
        h_lines, _using_alias_patterns(name), start=max(0, search_start),
      )
      if decl_line is not None:
        entry["cpp"]["decl"] = {"line": decl_line}
    symbols.append(entry)
  return symbols


def _collect_enum_member_symbols(
  tr: Translator,
  info: ClassInfo,
  h_lines: list[str],
) -> list[dict[str, Any]]:
  symbols: list[dict[str, Any]] = []
  for member in info.enum_members:
    # 成员赋值行在 Python 类体中
    py_node: ast.AST | None = None
    for stmt in info.node.body:
      if isinstance(stmt, ast.Assign):
        for t in stmt.targets:
          if isinstance(t, ast.Name) and t.id == member.name:
            py_node = stmt
            break
      elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        if stmt.target.id == member.name:
          py_node = stmt
      if py_node is not None:
        break
    span = _py_span(py_node) if py_node is not None else _py_span(info.node)
    entry = _base_symbol(
      kind="enum_member",
      module=info.module_path,
      name=member.name,
      cpp_name=member.name,
      py_file=_py_file(tr, info.module_path),
      py_span=span,
      owner=info.name,
      cpp_qual=f"{info.cpp_name()}::{member.name}",
    )
    decl_line = _first_line_match(h_lines, _enum_member_patterns(member.name))
    if decl_line is not None:
      entry["cpp"]["decl"] = {"line": decl_line}
    symbols.append(entry)
  return symbols


def _collect_union_variant_symbols(
  tr: Translator,
  info: ClassInfo,
  h_lines: list[str],
  inl_lines: list[str],
  cpp_lines: list[str],
) -> list[dict[str, Any]]:
  symbols: list[dict[str, Any]] = []
  cls = info.cpp_name()
  for variant in info.union_variants:
    vnode = _variant_class_node(info, variant.name)
    factory_decl = [
      re.compile(rf"\bstatic\b[^\n;]*\b{re.escape(variant.name)}\s*\("),
      re.compile(rf"\b{re.escape(cls)}\s+{re.escape(variant.name)}\s*\("),
    ]
    factory_impl = [
      re.compile(
        rf"\b{re.escape(cls)}\s+.*::\s*{re.escape(variant.name)}\s*\(",
      ),
      re.compile(rf"::\s*{re.escape(variant.name)}\s*\("),
    ]
    tag_pats = _enum_member_patterns(variant.name)
    payload_pats = [
      re.compile(
        rf"\b(struct|class)\s+{re.escape(cls)}_Variant_{re.escape(variant.name)}\b",
      ),
    ]
    factory_line = _first_line_match(h_lines, factory_decl)
    tag_line = _first_line_match(h_lines, tag_pats)
    payload_line = _first_line_match(h_lines, payload_pats)
    impl_line = _impl_definition_line(inl_lines, factory_impl, variant.name)
    if impl_line is None:
      impl_line = _impl_definition_line(cpp_lines, factory_impl, variant.name)

    # Q1: 优先工厂声明；无则 Tag；tag/payload 作附加锚点供 both
    primary = factory_line if factory_line is not None else tag_line
    entry = _base_symbol(
      kind="variant",
      module=info.module_path,
      name=variant.name,
      cpp_name=variant.name,
      py_file=_py_file(tr, info.module_path),
      py_span=_py_span(vnode),
      owner=info.name,
      cpp_qual=f"{cls}::{variant.name}",
    )
    if primary is not None:
      entry["cpp"]["decl"] = {"line": primary}
    if impl_line is not None:
      entry["cpp"]["impl"] = {"line": impl_line}
    if tag_line is not None and tag_line != primary:
      entry["cpp"]["tag"] = {"line": tag_line}
    if payload_line is not None:
      entry["cpp"]["payload"] = {"line": payload_line}
    symbols.append(entry)

    for fname in variant.fields:
      fann = variant.field_annotations.get(fname)
      fspan = _py_span(fann) if fann is not None else _py_span(vnode)
      fcpp = fname  # payload 内字段名与 Python 一致
      f_entry = _base_symbol(
        kind="field",
        module=info.module_path,
        name=fname,
        cpp_name=fcpp,
        py_file=_py_file(tr, info.module_path),
        py_span=fspan,
        owner=variant.name,
      )
      f_entry["union"] = info.name
      if payload_line is not None:
        # 字段声明在 payload struct 附近
        f_line = _first_line_match(
          h_lines,
          [re.compile(rf"\b{re.escape(fcpp)}\s*;")],
          start=max(0, payload_line - 1),
        )
        if f_line is not None:
          f_entry["cpp"]["decl"] = {"line": f_line}
      symbols.append(f_entry)
  return symbols


def _collect_mixin_symbols(
  tr: Translator,
  info: ClassInfo,
  h_lines: list[str],
  inl_lines: list[str],
  cpp_lines: list[str],
) -> list[dict[str, Any]]:
  """Q2：mixin 类仅 Python；方法 → Python + 能解析时的宿主 .inl。"""
  symbols: list[dict[str, Any]] = []
  symbols.append(_base_symbol(
    kind="mixin",
    module=info.module_path,
    name=info.name,
    cpp_name=info.cpp_name(),
    py_file=_py_file(tr, info.module_path),
    py_span=_py_span(info.node),
  ))
  hosts = _hosts_using_mixin(tr, info)
  host_artifacts: list[tuple[ClassInfo, list[str], list[str], list[str]]] = []
  for host in hosts:
    arts = _resolve_module_artifacts(tr, host.module_path)
    repo = tr._repo_root()
    host_artifacts.append((
      host,
      _read_lines(repo / arts["h"] if arts["h"] else None),
      _read_lines(repo / arts["inl"] if arts["inl"] else None),
      _read_lines(repo / arts["cpp"] if arts["cpp"] else None),
    ))

  for method in info.iter_methods():
    if _skip_dunder_method(method.name):
      continue
    mcpp = info.cpp_member_name(method.name)
    entry = _base_symbol(
      kind="method",
      module=info.module_path,
      name=method.name,
      cpp_name=mcpp,
      py_file=_py_file(tr, info.module_path),
      py_span=_py_span(method),
      owner=info.name,
      role="mixin",
    )
    for host, hh, hi, hc in host_artifacts:
      host_cpp = host.cpp_member_name(method.name)
      _decl_p, impl_p = _method_cpp_patterns(host, method.name, host_cpp)
      impl_line = _impl_definition_line(hi, impl_p, host_cpp)
      if impl_line is None:
        impl_line = _impl_definition_line(hc, impl_p, host_cpp)
      decl_line = _first_line_match(hh, [re.compile(rf"\b{re.escape(host_cpp)}\s*\(")])
      if impl_line is not None or decl_line is not None:
        entry["cpp"]["implModule"] = host.module_path
        entry["ownerHost"] = host.name
        if decl_line is not None:
          entry["cpp"]["decl"] = {"line": decl_line}
        if impl_line is not None:
          entry["cpp"]["impl"] = {"line": impl_line}
        break
    symbols.append(entry)
  return symbols


def _collect_protocol_symbols(tr: Translator, info: ClassInfo) -> list[dict[str, Any]]:
  """Q3：protocol 仅 Python（含关联类型）。"""
  symbols: list[dict[str, Any]] = [
    _base_symbol(
      kind="protocol",
      module=info.module_path,
      name=info.name,
      cpp_name=info.cpp_name(),
      py_file=_py_file(tr, info.module_path),
      py_span=_py_span(info.node),
    ),
  ]
  symbols.extend(_collect_type_alias_symbols(
    tr,
    module_path=info.module_path,
    owner=info.name,
    aliases=info.type_aliases,
    h_lines=[],
    py_only=True,
  ))
  for method in info.iter_methods():
    if _skip_dunder_method(method.name):
      continue
    symbols.append(_base_symbol(
      kind="method",
      module=info.module_path,
      name=method.name,
      cpp_name=info.cpp_member_name(method.name),
      py_file=_py_file(tr, info.module_path),
      py_span=_py_span(method),
      owner=info.name,
      role="protocol",
    ))
  for prop_name, prop in info.properties.items():
    node = prop.getter or prop.setter or prop.postsetter
    if node is None:
      continue
    symbols.append(_base_symbol(
      kind="property",
      module=info.module_path,
      name=prop_name,
      cpp_name=property_getter_method_for(prop_name),
      py_file=_py_file(tr, info.module_path),
      py_span=_py_span(node),
      owner=info.name,
      role="protocol",
    ))
  return symbols


def _collect_descriptor_symbols(tr: Translator, info: ClassInfo) -> list[dict[str, Any]]:
  """描述符源：仅 Python（宿主展开由宿主 property 索引覆盖）。"""
  symbols: list[dict[str, Any]] = [
    _base_symbol(
      kind="descriptor",
      module=info.module_path,
      name=info.name,
      cpp_name=info.cpp_name(),
      py_file=_py_file(tr, info.module_path),
      py_span=_py_span(info.node),
    ),
  ]
  for method in info.iter_methods():
    if _skip_dunder_method(method.name):
      continue
    symbols.append(_base_symbol(
      kind="method",
      module=info.module_path,
      name=method.name,
      cpp_name=info.cpp_member_name(method.name),
      py_file=_py_file(tr, info.module_path),
      py_span=_py_span(method),
      owner=info.name,
      role="descriptor",
    ))
  return symbols


def _collect_class_symbols(
  tr: Translator,
  info: ClassInfo,
  *,
  h_lines: list[str],
  inl_lines: list[str],
  cpp_lines: list[str],
) -> list[dict[str, Any]]:
  if info.is_annotation or info.is_variant_mixin:
    return []
  if tr._is_type_marker(info):
    return []
  if info.is_protocol:
    return _collect_protocol_symbols(tr, info)
  if info.is_mixin:
    return _collect_mixin_symbols(tr, info, h_lines, inl_lines, cpp_lines)
  if info.is_descriptor:
    return _collect_descriptor_symbols(tr, info)

  symbols: list[dict[str, Any]] = []
  qual = qualify_symbol_in_module(info.module_path, info.cpp_name())
  cls_decl_line = _class_decl_line(h_lines, info)
  cls_kind = "class"
  cls_entry = _base_symbol(
    kind=cls_kind,
    module=info.module_path,
    name=info.name,
    cpp_name=info.cpp_name(),
    py_file=_py_file(tr, info.module_path),
    py_span=_py_span(info.node),
    cpp_qual=qual,
  )
  if info.is_enum:
    cls_entry["role"] = "enum"
  if info.is_union:
    cls_entry["role"] = "union"
  if cls_decl_line is not None:
    cls_entry["cpp"]["decl"] = {"line": cls_decl_line}
  symbols.append(cls_entry)

  if info.is_enum:
    symbols.extend(_collect_enum_member_symbols(tr, info, h_lines))
    return symbols

  if info.is_union:
    symbols.extend(_collect_union_variant_symbols(
      tr, info, h_lines, inl_lines, cpp_lines,
    ))
    # union 上仍可能有方法 / property / type alias
  else:
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
      py_span = _py_span(node) if node is not None else _py_span(info.node)
      decl_line = _first_line_match(h_lines, _field_cpp_patterns(info, field_cpp))
      entry = _base_symbol(
        kind="field",
        module=info.module_path,
        name=field,
        cpp_name=field_cpp,
        py_file=_py_file(tr, info.module_path),
        py_span=py_span,
        owner=info.name,
      )
      if decl_line is not None:
        entry["cpp"]["decl"] = {"line": decl_line}
      symbols.append(entry)

  alias_start = (cls_decl_line - 1) if cls_decl_line is not None else 0
  symbols.extend(_collect_type_alias_symbols(
    tr,
    module_path=info.module_path,
    owner=info.name,
    aliases={
      n: a for n, a in info.type_aliases.items()
      if n != "__base__"
    },
    h_lines=h_lines,
    py_only=False,
    search_start=alias_start,
  ))
  # 类形参自动 ``using Element = _Element``（非手写 type）
  existing_alias = {s["name"] for s in symbols if s.get("kind") == "type_alias" and s.get("owner") == info.name}
  for tp in info.type_params:
    if tp in existing_alias:
      continue
    entry = _base_symbol(
      kind="type_alias",
      module=info.module_path,
      name=tp,
      cpp_name=tp,
      py_file=_py_file(tr, info.module_path),
      py_span=_py_span(info.node),
      owner=info.name,
      role="type_param",
    )
    decl_line = _first_line_match(
      h_lines, _using_alias_patterns(tp), start=alias_start,
    )
    if decl_line is not None:
      entry["cpp"]["decl"] = {"line": decl_line}
    symbols.append(entry)
    existing_alias.add(tp)

  for prop_name, prop in info.properties.items():
    _append_property_symbols(
      tr, info, prop_name, prop, h_lines, inl_lines, cpp_lines, symbols,
    )
  for prop_name, prop in info.static_properties.items():
    _append_property_symbols(
      tr, info, prop_name, prop, h_lines, inl_lines, cpp_lines, symbols,
    )

  if not info.is_enum:
    for method in info.iter_methods():
      if _skip_dunder_method(method.name):
        continue
      mcpp = info.cpp_member_name(method.name)
      decl_p, impl_p = _method_cpp_patterns(info, method.name, mcpp)
      symbols.append(_method_symbol(
        tr, info, method.name, method, mcpp, decl_p, impl_p,
        h_lines, inl_lines, cpp_lines, kind="method",
      ))

  return symbols


def _collect_delegate_symbols(
  tr: Translator,
  module_path: str,
  h_lines: list[str],
) -> list[dict[str, Any]]:
  symbols: list[dict[str, Any]] = []
  for name, dinfo in getattr(tr, "delegates", {}).items():
    if dinfo.module_path != module_path:
      continue
    cpp_name = dinfo.cpp_name()
    entry = _base_symbol(
      kind="delegate",
      module=module_path,
      name=name,
      cpp_name=cpp_name,
      py_file=_py_file(tr, module_path),
      py_span=_py_span(dinfo.node),
      cpp_qual=qualify_symbol_in_module(module_path, cpp_name),
    )
    # ``class UIEvent : public PyDelegate<...>`` 或 ``using UIEvent = ...``
    decl_line = _first_line_match(h_lines, [
      re.compile(rf"\b(class|struct)\s+{re.escape(cpp_name)}\b"),
      re.compile(rf"\busing\s+{re.escape(cpp_name)}\s*="),
    ])
    if decl_line is not None:
      entry["cpp"]["decl"] = {"line": decl_line}
    symbols.append(entry)
  return symbols


def build_module_shard(tr: Translator, module_path: str) -> dict[str, Any] | None:
  artifacts = _resolve_module_artifacts(tr, module_path)
  # protocol / mixin 可能无独立生成物，但仍需写 shard（仅 Python）
  has_py_only = any(
    info.module_path == module_path
    and (info.is_protocol or info.is_mixin or info.is_descriptor)
    for info in tr.classes.values()
  )
  has_delegates = any(
    d.module_path == module_path for d in getattr(tr, "delegates", {}).values()
  )
  if not any(artifacts.values()) and not has_py_only and not has_delegates:
    ma = tr.module_analysis.get(module_path)
    if not ma or not ma.type_aliases:
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

  ma = tr.module_analysis.get(module_path)
  if ma and ma.type_aliases:
    symbols.extend(_collect_type_alias_symbols(
      tr,
      module_path=module_path,
      owner=None,
      aliases=ma.type_aliases,
      h_lines=h_lines,
      py_only=False,
    ))

  symbols.extend(_collect_delegate_symbols(tr, module_path, h_lines))

  for mp, func in tr.module_functions:
    if mp != module_path:
      continue
    if func.name == "main":
      continue
    if func.name in getattr(tr, "delegates", {}):
      continue
    cpp_name = tr._module_function_cpp_name(module_path, func)
    decl_p, impl_p = _module_function_cpp_patterns(tr, module_path, cpp_name)
    decl_line = _first_line_match(h_lines, decl_p)
    impl_line = _impl_definition_line(inl_lines, impl_p, cpp_name)
    if impl_line is None:
      impl_line = _impl_definition_line(cpp_lines, impl_p, cpp_name)
    entry = _base_symbol(
      kind="function",
      module=module_path,
      name=func.name,
      cpp_name=cpp_name,
      py_file=_py_file(tr, module_path),
      py_span=_py_span(func),
    )
    if decl_line is not None:
      entry["cpp"]["decl"] = {"line": decl_line}
    if impl_line is not None:
      entry["cpp"]["impl"] = {"line": impl_line}
    symbols.append(entry)

  if not symbols and not any(artifacts.values()):
    return None

  return {
    "version": NAV_INDEX_VERSION,
    "module": module_path,
    "pyFile": _py_file(tr, module_path),
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
