"""Runtime bootstrap：改少量 ``py2cpp/*.py`` 时按模块增量 analyze/emit。

译器 / ``templates/`` / ``ffi/`` / ``__init__.py`` / ``@mixin`` / ``@protocol``
变更仍全量。叶子脏时清洁模块跳过 import / 部分 expand / checks，签名缓存
``generated/runtime/.cache/analyze_sigs.pkl``。``PY2CPP_FORCE_BOOTSTRAP=1`` 强制全量。
"""
from __future__ import annotations

import hashlib
import os
import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .bootstrap_stamp import (
  FORCE_ENV,
  iter_bootstrap_input_files,
  repo_root,
  stamp_path,
)

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo, FunctionSig, ModuleAnalysis
  from ..translator import Translator

CACHE_REL = Path("generated") / "runtime" / ".cache" / "analyze_sigs.pkl"
_DECORATOR_FORCE_FULL = re.compile(r"(?m)^@(mixin|protocol)\b")


@dataclass
class BootstrapPlan:
  """全量或按模块增量。"""

  full: bool
  reason: str
  dirty_modules: set[str] = field(default_factory=set)


def cache_path(root: Path | None = None) -> Path:
  return (root or repo_root()) / CACHE_REL


def _file_sig(path: Path) -> str:
  st = path.stat()
  return f"{st.st_mtime_ns}:{st.st_size}"


def translator_fingerprint(root: Path | None = None) -> str:
  """译器 / templates / ffi / main.py 指纹；变则签名缓存作废。"""
  root = root or repo_root()
  parts: list[str] = []
  for f in iter_bootstrap_input_files(root):
    rel = f.relative_to(root).as_posix()
    if rel.startswith("py2cpp/"):
      continue
    try:
      parts.append(f"{rel}:{_file_sig(f)}")
    except OSError:
      continue
  parts.sort()
  return hashlib.blake2b("\n".join(parts).encode(), digest_size=16).hexdigest()


def py_rel_to_module_path(rel: str) -> str | None:
  """``py2cpp/io/path.py`` → ``py2cpp/io/path``。"""
  norm = rel.replace("\\", "/")
  if not norm.startswith("py2cpp/") or not norm.endswith(".py"):
    return None
  if norm.endswith("/__init__.py"):
    return norm[: -len("/__init__.py")]
  return norm[: -len(".py")]


def _forces_full_py2cpp_rel(rel: str, text: str) -> bool:
  name = rel.replace("\\", "/")
  if name == "py2cpp/__init__.py" or name.endswith("/__init__.py"):
    return True
  return _DECORATOR_FORCE_FULL.search(text) is not None


def plan_bootstrap_incremental(
  *,
  root: Path | None = None,
  stamp_mtime: float | None = None,
) -> BootstrapPlan:
  """相对 stamp 的脏文件 → 全量或脏模块集合。"""
  if os.environ.get(FORCE_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
    return BootstrapPlan(full=True, reason="PY2CPP_FORCE_BOOTSTRAP")
  root = root or repo_root()
  stamp = stamp_path(root)
  if stamp_mtime is None:
    if not stamp.is_file():
      return BootstrapPlan(full=True, reason="no stamp")
    try:
      stamp_mtime = stamp.stat().st_mtime
    except OSError:
      return BootstrapPlan(full=True, reason="stamp unreadable")

  dirty: set[str] = set()
  any_changed = False
  for f in iter_bootstrap_input_files(root):
    try:
      m = f.stat().st_mtime
    except OSError:
      continue
    if m <= stamp_mtime:
      continue
    any_changed = True
    rel = f.relative_to(root).as_posix()
    if not rel.startswith("py2cpp/"):
      return BootstrapPlan(full=True, reason=rel)
    try:
      text = f.read_text(encoding="utf-8")
    except OSError:
      return BootstrapPlan(full=True, reason=rel)
    if _forces_full_py2cpp_rel(rel, text):
      return BootstrapPlan(full=True, reason=rel)
    mp = py_rel_to_module_path(rel)
    if mp is None:
      return BootstrapPlan(full=True, reason=rel)
    dirty.add(mp)

  if not any_changed:
    return BootstrapPlan(full=False, reason="unchanged", dirty_modules=set())
  if not dirty:
    return BootstrapPlan(full=True, reason="unmapped dirty")
  return BootstrapPlan(full=False, reason="stdlib py", dirty_modules=dirty)


def _empty_cache(fp: str) -> dict[str, Any]:
  return {
    "translator_fp": fp,
    "modules": {},
    "function_sigs": {},
    "overload_sigs": {},
    "module_analysis": {},
    "classes": {},
    "import_bindings": {},
    "import_usings": {},
  }


def load_analysis_cache(root: Path | None = None) -> dict[str, Any] | None:
  path = cache_path(root)
  if not path.is_file():
    return None
  try:
    with path.open("rb") as fh:
      data = pickle.load(fh)
  except (OSError, pickle.PickleError, EOFError, AttributeError):
    return None
  if not isinstance(data, dict) or "translator_fp" not in data:
    return None
  return data


def save_analysis_cache(data: dict[str, Any], root: Path | None = None) -> None:
  path = cache_path(root)
  path.parent.mkdir(parents=True, exist_ok=True)
  tmp = path.with_suffix(".pkl.tmp")
  with tmp.open("wb") as fh:
    pickle.dump(data, fh, protocol=4)
  tmp.replace(path)


def snapshot_class_payload(info: ClassInfo) -> dict[str, Any]:
  return {
    "method_sigs": info.method_sigs,
    "init_sigs": info.init_sigs,
    "method_overload_sigs": info.method_overload_sigs,
    "field_types": dict(info.field_types),
    "field_type_nodes": dict(info.field_type_nodes),
    "field_annotations": dict(info.field_annotations),
    "owned_fields": dict(info.owned_fields),
    "owned_array_sizes": dict(info.owned_array_sizes),
    "property_sigs": {
      name: (p.getter_sig, p.setter_sig, p.postsetter_sig)
      for name, p in info.properties.items()
    },
    "static_property_sigs": {
      name: (p.getter_sig, p.setter_sig, p.postsetter_sig)
      for name, p in info.static_properties.items()
    },
  }


def apply_class_payload(info: ClassInfo, payload: dict[str, Any]) -> None:
  info.method_sigs = payload["method_sigs"]
  info.init_sigs = list(payload["init_sigs"])
  info.method_overload_sigs = payload["method_overload_sigs"]
  info.field_types = dict(payload["field_types"])
  info.field_type_nodes = dict(payload["field_type_nodes"])
  info.field_annotations = dict(payload["field_annotations"])
  info.owned_fields = dict(payload["owned_fields"])
  info.owned_array_sizes = dict(payload["owned_array_sizes"])
  for name, sigs in payload.get("property_sigs", {}).items():
    prop = info.properties.get(name)
    if prop is None:
      continue
    prop.getter_sig, prop.setter_sig, prop.postsetter_sig = sigs
  for name, sigs in payload.get("static_property_sigs", {}).items():
    prop = info.static_properties.get(name)
    if prop is None:
      continue
    prop.getter_sig, prop.setter_sig, prop.postsetter_sig = sigs


def attach_incremental_to_translator(tr: Translator, plan: BootstrapPlan) -> None:
  """设置 emit 过滤并从磁盘恢复清洁模块签名。"""
  tr.emit_module_filter = None
  tr.cached_analysis_modules = set()
  tr._cached_class_payloads = {}
  tr._cached_function_sigs = {}
  tr._cached_overload_sigs = {}
  tr._cached_module_analysis = {}
  tr._cached_import_bindings = {}
  tr._cached_import_usings = {}
  if plan.full or not tr._is_runtime_bootstrap():
    return
  cache = load_analysis_cache()
  fp = translator_fingerprint()
  if cache is None or cache.get("translator_fp") != fp:
    tr.emit_module_filter = set(plan.dirty_modules)
    return
  dirty = {m.replace("\\", "/") for m in plan.dirty_modules}
  classes = cache.get("classes") or {}
  cached_ok: set[str] = set()
  payloads: dict[tuple[str, str], dict[str, Any]] = {}
  for k, v in classes.items():
    if not isinstance(k, tuple) or len(k) != 2:
      continue
    mp = k[0].replace("\\", "/")
    payloads[(mp, k[1])] = v
    if mp not in dirty:
      cached_ok.add(mp)
  modules_meta: dict[str, dict[str, Any]] = cache.get("modules") or {}
  for mp in modules_meta:
    norm = mp.replace("\\", "/")
    if norm not in dirty:
      cached_ok.add(norm)
  for key in (cache.get("function_sigs") or {}):
    if isinstance(key, tuple) and len(key) == 2:
      mp = key[0].replace("\\", "/")
      if mp not in dirty:
        cached_ok.add(mp)
  for mp in (cache.get("import_bindings") or {}):
    norm = str(mp).replace("\\", "/")
    if norm not in dirty:
      cached_ok.add(norm)
  tr.emit_module_filter = set(plan.dirty_modules)
  tr.cached_analysis_modules = cached_ok
  tr._cached_class_payloads = payloads
  import os
  import sys
  if os.environ.get("PY2CPP_PROFILE", "").strip().lower() in ("1", "true", "yes", "on"):
    print(
      f"    attach modules={len(modules_meta)} classes={len(classes)} "
      f"cached_ok={len(cached_ok)} payloads={len(payloads)} dirty={len(dirty)}",
      file=sys.stderr,
    )
  fn_sigs: dict[tuple[str, str], FunctionSig] = {}
  for key, sig in (cache.get("function_sigs") or {}).items():
    if not isinstance(key, tuple) or len(key) != 2:
      continue
    mp = key[0].replace("\\", "/")
    if mp in cached_ok:
      fn_sigs[(mp, key[1])] = sig
  tr._cached_function_sigs = fn_sigs
  ov_sigs: dict[tuple[str, str], list[FunctionSig]] = {}
  for key, sigs in (cache.get("overload_sigs") or {}).items():
    if not isinstance(key, tuple) or len(key) != 2:
      continue
    mp = key[0].replace("\\", "/")
    if mp in cached_ok:
      ov_sigs[(mp, key[1])] = sigs
  tr._cached_overload_sigs = ov_sigs
  ma_map: dict[str, dict[str, list[str]]] = {}
  for mp, ma in (cache.get("module_analysis") or {}).items():
    if mp.replace("\\", "/") in cached_ok:
      ma_map[mp.replace("\\", "/")] = ma
  tr._cached_module_analysis = ma_map
  ib_map: dict[str, Any] = {}
  iu_map: dict[str, Any] = {}
  for mp, binds in (cache.get("import_bindings") or {}).items():
    norm = str(mp).replace("\\", "/")
    if norm in cached_ok:
      ib_map[norm] = binds
  for mp, usings in (cache.get("import_usings") or {}).items():
    norm = str(mp).replace("\\", "/")
    if norm in cached_ok:
      iu_map[norm] = usings
  tr._cached_import_bindings = ib_map
  tr._cached_import_usings = iu_map


def store_analysis_cache(tr: Translator, *, full: bool) -> None:
  """analyze 结束后写入 / 合并签名缓存。"""
  if not tr._is_runtime_bootstrap():
    return
  root = repo_root()
  fp = translator_fingerprint(root)
  prev = load_analysis_cache(root)
  if prev is None or prev.get("translator_fp") != fp or full:
    data = _empty_cache(fp)
  else:
    data = prev
  data["translator_fp"] = fp
  classes_out: dict[tuple[str, str], dict[str, Any]] = dict(data.get("classes") or {})
  modules_meta: dict[str, dict[str, Any]] = dict(data.get("modules") or {})
  fn_out: dict[tuple[str, str], FunctionSig] = dict(data.get("function_sigs") or {})
  ov_out: dict[tuple[str, str], list[FunctionSig]] = dict(data.get("overload_sigs") or {})
  ma_out: dict[str, dict[str, list[str]]] = dict(data.get("module_analysis") or {})
  ib_out: dict[str, Any] = dict(data.get("import_bindings") or {})
  iu_out: dict[str, Any] = dict(data.get("import_usings") or {})

  filt = tr.emit_module_filter
  cached = getattr(tr, "cached_analysis_modules", None) or set()
  for info in tr.classes.values():
    mp = info.module_path
    if filt is not None and mp not in filt and mp in cached:
      continue
    key = (mp, info.class_registry_key())
    classes_out[key] = snapshot_class_payload(info)

  for mp in tr.module_order:
    if filt is not None and mp not in filt and mp in cached:
      continue
    py = root / f"{mp}.py"
    if not py.is_file():
      py = root / mp / "__init__.py"
    src_sig = ""
    if py.is_file():
      try:
        src_sig = _file_sig(py)
      except OSError:
        src_sig = ""
    modules_meta[mp] = {"src_sig": src_sig}
    ma = tr.module_analysis.get(mp)
    if ma is not None:
      ma_out[mp] = {
        "includes": list(ma.includes),
        "forward_decls": list(ma.forward_decls),
        "post_class_includes": list(ma.post_class_includes),
      }

  for (mp, name), sig in tr.function_sigs.items():
    if filt is not None and mp not in filt and mp in cached:
      continue
    fn_out[(mp, name)] = sig
  for (mp, name), sigs in tr.module_function_overload_sigs.items():
    if filt is not None and mp not in filt and mp in cached:
      continue
    ov_out[(mp, name)] = sigs

  for mp, binds in tr.module_import_bindings.items():
    if filt is not None and mp not in filt and mp in cached:
      continue
    ib_out[mp] = binds
    iu_out[mp] = list(tr.module_import_usings.get(mp, []))

  data["classes"] = classes_out
  data["modules"] = modules_meta
  data["function_sigs"] = fn_out
  data["overload_sigs"] = ov_out
  data["module_analysis"] = ma_out
  data["import_bindings"] = ib_out
  data["import_usings"] = iu_out
  try:
    save_analysis_cache(data, root)
  except (OSError, pickle.PickleError, TypeError, AttributeError):
    pass
