"""解析 ``import`` / ``from … import``，建立模块级与入口别名字典。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .import_resolver import (
  ImportRequest,
  absolute_dotted_to_module_path,
  import_local_name,
  iter_module_import_requests,
  public_export_names,
  resolve_import_target_path,
  resolve_relative_module_path,
)
from .ir import TYPE_MARKER_CLASSES, TypeAliasInfo, cpp_ident, cpp_type_rename
from ..constant.ffi_layout import is_ffi_module_path
from ..constant.parallel import CONCUR_PARALLEL_MODULE, PRANGE_TRANSLATION_ONLY_FUNCS
from ..constant.stdlib_layout import RUNTIME_PKG
from ..analysis.runtime_symbols import (
  RUNTIME_PKG_QUALIFIED_SYMBOLS,
  TRANSLATION_ONLY_FUNCS,
)
from .module_namespace import namespace_qualifier_for_module, qualify_symbol_in_module
from ..passes.mixins import _mixin_regular_bases

if TYPE_CHECKING:
  from ..translator import Translator


@dataclass(frozen=True)
class ImportUsing:
  """``from m import *`` → ``using namespace m;``；``from m import x`` → ``using m::x;``。"""

  kind: str  # "namespace" | "symbol"
  qualifier: str
  symbol: str | None = None


@dataclass(frozen=True)
class ImportBinding:
  """符号绑定：``local_name`` 在生成代码中映射为 ``cpp_name``。"""

  local_name: str
  symbol: str
  module_path: str
  kind: str  # "class" | "function" | "module"
  cpp_name: str


def dotted_import_to_module_path(dotted: str | None) -> str:
  return absolute_dotted_to_module_path(dotted)


def collect_module_imports(
  tr: Translator,
  module_path: str,
  *,
  project_root,
  runtime_root,
) -> tuple[dict[str, ImportBinding], list[ImportUsing]]:
  """解析单个模块顶层 import（Python 3.13 静态子集）。"""
  bindings: dict[str, ImportBinding] = {}
  usings: list[ImportUsing] = []
  tree = tr.module_asts.get(module_path)
  if tree is None:
    return bindings, usings
  for req in iter_module_import_requests(tree):
    _apply_import_request(
      tr,
      module_path,
      req,
      bindings,
      usings,
      project_root=project_root,
      runtime_root=runtime_root,
    )
  return bindings, usings


def effective_module_type_aliases(
  tr: Translator,
  module_path: str,
) -> dict[str, TypeAliasInfo]:
  """模块自有 + ``from … import`` 的类型别名（供注解解析与 emit）。"""
  out: dict[str, TypeAliasInfo] = {}
  ma = tr.module_analysis.get(module_path)
  if ma:
    for alias in ma.type_aliases:
      if not alias.member_constraint:
        out[alias.name] = alias
  for imp in tr.module_import_bindings.get(module_path, {}).values():
    if imp.kind != "type_alias":
      continue
    src = tr.module_analysis.get(imp.module_path)
    if src is None:
      continue
    for alias in src.type_aliases:
      if alias.name == imp.symbol and not alias.member_constraint:
        out[imp.local_name] = alias
        break
  return out


def collect_all_imports(tr: Translator) -> dict[str, dict[str, ImportBinding]]:
  """所有已加载模块的 import 绑定；入口模块同步到 ``tr.import_bindings``。"""
  per_module: dict[str, dict[str, ImportBinding]] = {}
  per_usings: dict[str, list[ImportUsing]] = {}
  project_root = tr._import_project_root_cache
  runtime_root = tr._runtime_root()
  cached_b = getattr(tr, "_cached_import_bindings", None) or {}
  cached_u = getattr(tr, "_cached_import_usings", None) or {}
  skip = getattr(tr, "skip_cached_analysis_module", None)
  for module_path in tr.module_order:
    mp = module_path.replace("\\", "/")
    if skip is not None and skip(module_path):
      binds = cached_b.get(mp) or cached_b.get(module_path)
      if binds is not None:
        per_module[module_path] = binds
        per_usings[module_path] = list(
          cached_u.get(mp) or cached_u.get(module_path) or []
        )
        continue
    bindings, usings = collect_module_imports(
      tr,
      module_path,
      project_root=project_root,
      runtime_root=runtime_root,
    )
    per_module[module_path] = bindings
    per_usings[module_path] = usings
  tr.module_import_bindings = per_module
  tr.module_import_usings = per_usings
  entry = tr.import_bindings = dict(per_module.get(tr.entry_module_path, {}))
  return per_module


def collect_entry_imports(tr: Translator) -> dict[str, ImportBinding]:
  """兼容旧名：等价于 ``collect_all_imports`` 的入口绑定。"""
  collect_all_imports(tr)
  return tr.import_bindings


def _append_using_namespace(usings: list[ImportUsing], module_path: str) -> None:
  q = namespace_qualifier_for_module(module_path)
  if not q:
    return
  line = ImportUsing("namespace", q)
  if line not in usings:
    usings.append(line)


def _append_using_symbol(
  usings: list[ImportUsing],
  module_path: str,
  symbol: str,
) -> None:
  q = namespace_qualifier_for_module(module_path)
  if not q:
    return
  line = ImportUsing("symbol", q, symbol)
  if line not in usings:
    usings.append(line)


def _apply_import_request(
  tr: Translator,
  importer_path: str,
  req: ImportRequest,
  bindings: dict[str, ImportBinding],
  usings: list[ImportUsing],
  *,
  project_root,
  runtime_root,
) -> None:
  if req.is_plain_import:
    for _dotted, asname in req.names:
      assert req.source_dotted is not None
      local = import_local_name(req.source_dotted, asname)
      target = resolve_import_target_path(
        importer_path, req, project_root=project_root, runtime_root=runtime_root,
      )
      if target is None:
        raise NotImplementedError(
          f"无法解析 import：{req.source_dotted!r}"
          f"（支持 py2cpp 标准库、本仓库用户模块、ffi/**/*.pyi）"
        )
      bindings[local] = ImportBinding(
        local_name=local,
        symbol="",
        module_path=target,
        kind="module",
        cpp_name="",
      )
    return

  if not req.is_plain_import and req.module in (
    "__future__", "typing", "collections", "collections.abc",
  ):
    return
  target = resolve_import_target_path(
    importer_path, req, project_root=project_root, runtime_root=runtime_root,
  )
  if target is None:
    if not req.is_plain_import and req.module in (
      "__future__", "typing", "collections", "collections.abc",
    ):
      return
    mod_display = req.module or "."
    raise NotImplementedError(f"无法解析 from … import（模块 {mod_display!r}）")

  if req.is_star:
    if is_ffi_module_path(target):
      raise NotImplementedError(
        f"禁止 from {req.module or target} import *（FFI 面见 docs/c-ffi-pyi.md §10；"
        f"请显式 import 符号）"
      )
    _append_using_namespace(usings, target)
    for local, binding in _star_exports(tr, target).items():
      if binding.kind == "type_alias":
        _append_using_symbol(usings, binding.module_path, binding.symbol)
      bindings[local] = _binding_with_bare_cpp(binding)
    return

  for name, asname in req.names:
    local = asname or name
    binding = _resolve_symbol(tr, target, name, local)
    if not binding:
      sub = resolve_module_attribute(tr, target, name, local_name=local)
      if sub is None or sub.kind != "module":
        continue
      bindings[local] = sub
      continue
    if asname and asname != name:
      aliased = ImportBinding(
        local_name=local,
        symbol=binding.symbol,
        module_path=binding.module_path,
        kind=binding.kind,
        cpp_name=binding.cpp_name.rsplit("::", 1)[-1],
      )
      bindings[local] = aliased
      if binding.kind == "class":
        _append_using_symbol(usings, binding.module_path, binding.cpp_name)
      continue
    info = tr.classes.get(name)
    if name in TYPE_MARKER_CLASSES:
      bindings[local] = _binding_with_bare_cpp(binding)
      continue
    if info and info.is_mixin:
      for base_name in _mixin_regular_bases(info, tr.classes):
        bi = tr.classes.get(base_name)
        if bi is None or bi.is_mixin or bi.is_annotation or bi.is_protocol:
          continue
        _append_using_symbol(usings, bi.module_path, cpp_ident(base_name))
        if bi.module_path == f"{RUNTIME_PKG}/unittest" and base_name == "TestCase":
          _append_using_symbol(usings, bi.module_path, "TestResult")
      bindings[local] = _binding_with_bare_cpp(binding)
      continue
    if info and info.is_annotation:
      bindings[local] = _binding_with_bare_cpp(binding)
      continue
    if info and info.is_descriptor:
      bindings[local] = _binding_with_bare_cpp(binding)
      continue
    if (
      target == RUNTIME_PKG
      and binding.cpp_name in RUNTIME_PKG_QUALIFIED_SYMBOLS
    ):
      bindings[local] = ImportBinding(
        local_name=local,
        symbol=binding.symbol,
        module_path=target,
        kind=binding.kind,
        cpp_name=qualify_symbol_in_module(target, binding.cpp_name),
      )
      continue
    # 模块常量：.inl 在 namespace 外再开块，短名 using 失效；始终全限定
    if binding.kind == "constant":
      bindings[local] = binding
      continue
    if binding.kind != "function":
      if binding.kind == "type_alias":
        _append_using_symbol(usings, binding.module_path, binding.symbol)
      elif not (info and info.is_protocol and info.module_path == target):
        if not (
          target == RUNTIME_PKG
          and binding.cpp_name in TRANSLATION_ONLY_FUNCS
        ):
          _append_using_symbol(usings, binding.module_path, binding.cpp_name)
    bindings[local] = _binding_with_bare_cpp(binding)


def _binding_with_bare_cpp(binding: ImportBinding) -> ImportBinding:
  """``using`` 已引入时，生成代码用短名。"""
  return ImportBinding(
    local_name=binding.local_name,
    symbol=binding.symbol,
    module_path=binding.module_path,
    kind=binding.kind,
    cpp_name=binding.cpp_name.rsplit("::", 1)[-1],
  )


def _star_exports(
  tr: Translator,
  module_path: str,
) -> dict[str, ImportBinding]:
  out: dict[str, ImportBinding] = {}
  tree = tr.module_asts.get(module_path)
  if tree is None:
    return out
  for sym in public_export_names(tree):
    b = _resolve_symbol(tr, module_path, sym, sym)
    if b:
      out[sym] = b
  for node in tree.body:
    if not isinstance(node, ast.ImportFrom):
      continue
    if node.level:
      from ..translator import Translator

      sub = resolve_relative_module_path(
        module_path,
        level=node.level,
        module=node.module,
        runtime_root=Translator._runtime_root(),
        project_root=tr._import_project_root_cache,
      )
    else:
      sub = absolute_dotted_to_module_path(node.module)
    for alias in node.names:
      if alias.name == "*":
        out.update(_star_exports(tr, sub))
      else:
        local = alias.asname or alias.name
        b = _resolve_symbol(tr, sub, alias.name, local)
        if b:
          out[local] = b
  return out


def _stdlib_defining_module(tr: Translator, module_path: str, symbol: str) -> str:
  """域包 ``__init__`` 再导出（``from .str import str``）→ 定义在 ``…/str`` 子模块。"""
  sub = f"{module_path}/{symbol}"
  if sub in tr.module_asts:
    return sub
  return module_path


def _package_reexport_source(
  tr: Translator,
  module_path: str,
  symbol: str,
) -> tuple[str, str] | None:
  """包 ``__init__`` 的 ``from .path import mkdir`` / ``from .path import baseName as pathBaseName``。

  返回 ``(定义模块, 源符号名)``；``asname`` 须映射回源名，不能只换模块路径。
  """
  tree = tr.module_asts.get(module_path)
  if tree is None:
    return None
  for node in tree.body:
    if not isinstance(node, ast.ImportFrom) or not node.level:
      continue
    for alias in node.names:
      if alias.name == "*":
        continue
      exported = alias.asname or alias.name
      if alias.name != symbol and exported != symbol:
        continue
      dest = resolve_relative_module_path(
        module_path,
        level=node.level,
        module=node.module,
        runtime_root=tr._runtime_root(),
        project_root=getattr(tr, "_import_project_root_cache", None),
      )
      if dest and dest != module_path:
        return dest, alias.name
  return None


def _resolve_symbol(
  tr: Translator,
  module_path: str,
  symbol: str,
  local_name: str,
  *,
  _seen: frozenset[tuple[str, str]] | None = None,
) -> ImportBinding | None:
  """在 ``module_path`` 内解析符号；同名跨模块（如 ``time`` 函数 vs ``datetime.time``）不得被全局 ``classes`` 抢先。"""
  seen = _seen or frozenset()
  key = (module_path, symbol)
  if key in seen:
    return None
  def_mp = _stdlib_defining_module(tr, module_path, symbol)
  if def_mp == CONCUR_PARALLEL_MODULE and symbol in PRANGE_TRANSLATION_ONLY_FUNCS:
    tree = tr.module_asts.get(def_mp)
    if tree and any(
      isinstance(n, ast.FunctionDef) and n.name == symbol for n in tree.body
    ):
      return ImportBinding(
        local_name=local_name,
        symbol=symbol,
        module_path=def_mp,
        kind="function",
        cpp_name=symbol,
      )
  for mp, func in tr.module_functions:
    if mp == def_mp and func.name == symbol:
      bare = tr._module_function_cpp_name(mp, func)
      return ImportBinding(
        local_name=local_name,
        symbol=symbol,
        module_path=def_mp,
        kind="function",
        cpp_name=bare,
      )
  ovs = tr.module_function_overloads.get((def_mp, symbol))
  if ovs:
    bare = tr._module_function_cpp_name(def_mp, ovs[0])
    return ImportBinding(
      local_name=local_name,
      symbol=symbol,
      module_path=def_mp,
      kind="function",
      cpp_name=bare,
    )
  for dname, dinfo in tr.delegates.items():
    if dname == symbol and dinfo.module_path == def_mp:
      return ImportBinding(
        local_name=local_name,
        symbol=symbol,
        module_path=def_mp,
        kind="delegate",
        cpp_name=dinfo.cpp_name(),
      )
  for info in tr.classes.values():
    if info.name == symbol and info.module_path == def_mp:
      return ImportBinding(
        local_name=local_name,
        symbol=symbol,
        module_path=info.module_path,
        kind="class",
        cpp_name=info.cpp_name(),
      )
  info = tr.classes.get(symbol)
  if info is not None and info.module_path == def_mp:
    return ImportBinding(
      local_name=local_name,
      symbol=symbol,
      module_path=info.module_path,
      kind="class",
      cpp_name=info.cpp_name(),
    )
  tr._ensure_class_indexes()
  for info in tr._all_class_infos:
    if info.name == symbol and info.module_path == def_mp:
      return ImportBinding(
        local_name=local_name,
        symbol=symbol,
        module_path=def_mp,
        kind="class",
        cpp_name=info.cpp_name(),
      )
  for mp, ma in tr.module_analysis.items():
    if mp != def_mp and not mp.startswith(f"{def_mp}/"):
      continue
    for alias in ma.type_aliases:
      if alias.name == symbol and not alias.member_constraint:
        return ImportBinding(
          local_name=local_name,
          symbol=symbol,
          module_path=mp,
          kind="type_alias",
          cpp_name=qualify_symbol_in_module(mp, symbol),
        )
  cpp_ren = cpp_type_rename(symbol)
  if cpp_ren is not None and (
    module_path == RUNTIME_PKG or module_path.startswith(f"{RUNTIME_PKG}/")
  ):
    return ImportBinding(
      local_name=local_name,
      symbol=symbol,
      module_path=def_mp,
      kind="class",
      cpp_name=cpp_ren,
    )
  for mp, node in tr.module_constants:
    if mp != def_mp:
      continue
    if isinstance(node.target, ast.Name) and node.target.id == symbol:
      return ImportBinding(
        local_name=local_name,
        symbol=symbol,
        module_path=def_mp,
        kind="constant",
        cpp_name=qualify_symbol_in_module(def_mp, symbol),
      )
  reexp = _package_reexport_source(tr, module_path, symbol)
  if reexp is not None:
    dest, src_name = reexp
    return _resolve_symbol(
      tr, dest, src_name, local_name, _seen=seen | {key},
    )
  return None


def resolve_module_attribute(
  tr: Translator,
  module_path: str,
  attr: str,
  *,
  local_name: str | None = None,
) -> ImportBinding | None:
  """``import pkg`` 后 ``pkg.attr``：子模块或符号。"""
  sub = f"{module_path}/{attr}"
  if sub in tr.module_asts:
    return ImportBinding(
      local_name=local_name or attr,
      symbol="",
      module_path=sub,
      kind="module",
      cpp_name="",
    )
  return _resolve_symbol(tr, module_path, attr, local_name or attr)


def resolve_import_attribute_chain(
  tr: Translator,
  root_name: str,
  attrs: list[str],
) -> ImportBinding | None:
  """``pkg.sub.fn`` 等属性链（``root_name`` 为 ``import`` 绑定名）。"""
  bindings = (
    tr._emit_bindings_scope
    if tr._emit_bindings_scope is not None
    else tr.import_bindings
  )
  binding = bindings.get(root_name)
  if binding is None or binding.kind != "module":
    return None
  path = binding.module_path
  for i, attr in enumerate(attrs):
    if i == len(attrs) - 1:
      return resolve_module_attribute(tr, path, attr)
    sub = resolve_module_attribute(tr, path, attr)
    if sub is None or sub.kind != "module":
      return None
    path = sub.module_path
  return None


def binding_cpp_name(bindings: dict[str, ImportBinding], name: str) -> str | None:
  b = bindings.get(name)
  if b is None or b.kind == "module":
    return None
  return b.cpp_name


def binding_class_cpp_name(bindings: dict[str, ImportBinding], name: str) -> str | None:
  b = bindings.get(name)
  return b.cpp_name if b and b.kind == "class" else None


def resolve_ctor_cpp_type(tr: Translator, name: str) -> str | None:
  eff = tr._effective_import_bindings().get(name)
  if eff is not None and eff.kind in ("function", "delegate"):
    return None
  # 活跃形参（``YieldValue`` / ``T``）保持原名，勿 ``default_py_class_cpp_name``
  if name in tr._active_type_params():
    return name
  cpp = binding_class_cpp_name(tr._effective_import_bindings(), name)
  if cpp:
    return cpp
  mp = tr._active_module_path()
  mod_imp = tr.module_import_bindings.get(mp, {}).get(name)
  if mod_imp is not None and mod_imp.kind in ("function", "delegate"):
    return None
  if name in tr.classes:
    info = tr.classes[name]
    for f_mp, func in tr.module_functions:
      if func.name == name and f_mp != info.module_path:
        return None
    return info.cpp_name()
  if name in tr.delegates:
    return tr.delegates[name].cpp_name()
  # ``type Frac = Fraction[int]`` 也可以像目标类型一样构造。
  # 使用当前 TypeParser，保证其与注解、方法签名共享别名展开规则。
  parser = getattr(tr, "type_parser", None)
  if parser is not None:
    expanded = parser.parse_type(
      ast.Name(id=name, ctx=ast.Load()), tr._active_type_params(),
    )
    if expanded != cpp_ident(name):
      return expanded
  mapped = cpp_ident(name)
  builtins = (
    "list", "dict", "set", "frozenset", "deque", "tuple", "str", "bytes", "slice", "range",
    "array", "array2d", "array3d",
    "int", "int16", "int64", "uint16", "uint", "uint64", "uintptr", "float", "float64", "bool", "char", "byte", "object",
    "RefCount", "IterResult", "Optional",
  )
  if name in builtins:
    return cpp_ident(name)
  if name[0].isupper() or name.startswith("_"):
    return mapped
  return None


def resolve_class_ref_cpp(tr: Translator, name: str) -> str:
  cpp = binding_class_cpp_name(tr.import_bindings, name)
  if cpp:
    return cpp
  if name in tr.classes:
    return tr.classes[name].cpp_name()
  return cpp_ident(name)
