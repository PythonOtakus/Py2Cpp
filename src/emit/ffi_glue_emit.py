"""``ffi/**/*.pyi`` 的 ``@native`` / ``@native_name`` → 薄 ``.inl`` 转发到 C 符号。

命名空间为 ``ffi::…``（不挂 ``py2cpp::``）。句柄按 ``uint64`` 存；
``Pointer[opaque]`` 出参经临时 C 指针再写回。

默认仅对 ``ffi_glue_allowlist`` 内符号生成体（避免全量 ``uintptr``/回调签名在 MSVC 上 C2664）；
未列入的声明仍留在 ``.h``，调用时链接期报错。
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import (
  cpp_param,
  decorator_string_arg,
  format_fn_sig,
  has_named_decorator,
)
from ..analysis.module_namespace import namespace_qualifier_for_module
from ..constant.ffi_layout import (
  ffi_c_header_include,
  ffi_glue_allowlist,
  ffi_opaque_c_tag,
  is_ffi_module_path,
)

if TYPE_CHECKING:
  from ..translator import Translator


_SCALAR_CAST: dict[str, str] = {
  "int": "PyInt",
  "int64": "PyInt64",
  "uint": "PyUInt",
  "uint64": "PyUInt64",
  "uintptr": "PyUPtr",
  "float": "PyFloat",
  "float64": "PyFloat64",
  "bool": "PyBool",
  "c_str": "c_str",
}


@dataclass(frozen=True)
class _Ann:
  kind: str  # void|scalar|cstr|opaque|ptr_opaque|ptr_scalar|ptr_cstr|ptr_ptr|unsupported
  name: str = ""


def _parse_ann(node: ast.expr | None) -> _Ann:
  if node is None:
    return _Ann("void")
  if isinstance(node, ast.Constant) and node.value is None:
    return _Ann("void")
  if isinstance(node, ast.Name):
    if node.id == "None":
      return _Ann("void")
    if node.id == "c_str":
      return _Ann("cstr")
    if node.id in _SCALAR_CAST:
      return _Ann("scalar", node.id)
    return _Ann("opaque", node.id)
  if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
    if node.value.id != "Pointer":
      return _Ann("unsupported")
    sl = node.slice
    if isinstance(sl, ast.Name):
      if sl.id == "c_str":
        return _Ann("ptr_cstr")
      if sl.id in _SCALAR_CAST:
        return _Ann("ptr_scalar", sl.id)
      return _Ann("ptr_opaque", sl.id)
    if isinstance(sl, ast.Subscript):
      return _Ann("ptr_ptr")
  return _Ann("unsupported")


def _c_name(func: ast.FunctionDef) -> str:
  n = decorator_string_arg(func, "native_name") or func.name
  return n[2:] if n.startswith("::") else n


def _emit_arg_expr(pname: str, ann: _Ann, *, c_name: str) -> tuple[list[str], str]:
  if ann.kind == "cstr":
    return [], pname
  if ann.kind == "scalar":
    if ann.name == "uintptr":
      # 回调 / void* / 销毁器：统一经 void* 再交 C（允许 list 内函数自行收窄）
      if c_name == "sqlite3_exec" and pname in ("callback", "arg3"):
        if pname == "callback":
          return [], (
            f"reinterpret_cast<int(__cdecl*)(void*,int,char**,char**)>"
            f"(static_cast<uintptr_t>({pname}))"
          )
        return [], f"reinterpret_cast<void*>(static_cast<uintptr_t>({pname}))"
      return [], f"reinterpret_cast<void*>(static_cast<uintptr_t>({pname}))"
    return [], pname
  if ann.kind == "opaque":
    # Python 句柄为 ``*_h``（``sqlite3_h``）；``struct`` 须用 C 标签（``sqlite3``）
    c_tag = ffi_opaque_c_tag(ann.name)
    return [], f"(struct {c_tag}*)(uintptr_t){pname}"
  if ann.kind == "ptr_opaque":
    tmp = f"__ffi_o_{pname}"
    c_tag = ffi_opaque_c_tag(ann.name)
    return [f"struct {c_tag}* {tmp} = nullptr;"], f"&{tmp}"
  if ann.kind == "ptr_scalar":
    return [], pname
  if ann.kind == "ptr_cstr":
    # ``c_str*`` ≈ ``const char**``；个别 API（如 ``sqlite3_exec`` errmsg）要 ``char**``
    if c_name == "sqlite3_exec":
      return [], f"reinterpret_cast<char**>(static_cast<void*>({pname}))"
    return [], f"reinterpret_cast<const char**>(static_cast<void*>({pname}))"
  if ann.kind == "ptr_ptr":
    return [], f"(void*){pname}"
  if ann.kind == "unsupported":
    return [], f"reinterpret_cast<void*>(static_cast<uintptr_t>({pname}))"
  return [], pname


def _emit_out_writes(pname: str, ann: _Ann) -> list[str]:
  if ann.kind == "ptr_opaque":
    tmp = f"__ffi_o_{pname}"
    return [f"if ({pname}) {{ *{pname} = (PyUInt64)(uintptr_t){tmp}; }}"]
  return []


def _ret_store_type(ann: _Ann, fallback: str) -> str:
  if ann.kind == "void":
    return "void"
  if ann.kind == "opaque":
    return "PyUInt64"
  if ann.kind == "cstr":
    return "c_str"
  if ann.kind == "scalar":
    return _SCALAR_CAST.get(ann.name, fallback)
  return fallback


def _wrap_c_call_as_ret(c_call: str, ann: _Ann, store: str) -> str:
  if ann.kind == "opaque":
    return f"(PyUInt64)(uintptr_t)({c_call})"
  if ann.kind == "cstr":
    return f"(c_str)({c_call})"
  if ann.kind == "scalar":
    return f"({store})({c_call})"
  return f"({store})({c_call})"


def emit_ffi_module_glue(tr: Translator, module_path: str) -> None:
  if not is_ffi_module_path(module_path):
    return
  c_inc = ffi_c_header_include(module_path)
  if c_inc is None:
    return
  allow = ffi_glue_allowlist(module_path)
  funcs = [
    f
    for f in tr._module_emit_functions_for(module_path)
    if has_named_decorator(f, "native") and not has_named_decorator(f, "overload")
  ]
  if allow is not None:
    funcs = [f for f in funcs if _c_name(f) in allow]
  if not funcs:
    return
  lines = tr.per_module_inl_lines.setdefault(module_path, [])
  if lines and any("py2cpp FFI glue" in ln for ln in lines):
    return
  lines.append(f'// py2cpp FFI glue → C ({c_inc})')
  # 尖括号：勿用引号，否则同目录生成的 ``sqlite3.h`` 会自包含（guard 已定义 → C API 被跳过）
  lines.append(f"#include <{c_inc}>")
  lines.append("#include <stdint.h>")
  lines.append("")
  ns = namespace_qualifier_for_module(module_path)
  for func in funcs:
    fsig = tr._function_sig_for(module_path, func)
    cpp_name = tr._module_function_cpp_name(module_path, func)
    if "::" in cpp_name:
      continue
    qname = f"{ns}::{cpp_name}" if ns else cpp_name
    ret = tr._sig_return_storage(fsig)
    params = tr._function_sig_params_impl(fsig.params)
    sig = "inline " + format_fn_sig(ret, fsig.ret_trail, qname, params)
    ret_ann = _parse_ann(func.returns)
    cnm = _c_name(func)
    pre: list[str] = []
    call_args: list[str] = []
    post: list[str] = []
    for arg in func.args.args:
      pname = cpp_param(arg.arg)
      ann = _parse_ann(arg.annotation)
      pref, expr = _emit_arg_expr(pname, ann, c_name=cnm)
      pre.extend(pref)
      call_args.append(expr)
      post.extend(_emit_out_writes(pname, ann))
    c_call = f"::{cnm}({', '.join(call_args)})"
    lines.append(f"{sig}")
    lines.append("{")
    for ln in pre:
      lines.append(f"  {ln}")
    store = _ret_store_type(ret_ann, ret)
    if ret_ann.kind == "void":
      lines.append(f"  {c_call};")
      for ln in post:
        lines.append(f"  {ln}")
    elif post:
      lines.append(f"  {store} __ffi_r = {_wrap_c_call_as_ret(c_call, ret_ann, store)};")
      for ln in post:
        lines.append(f"  {ln}")
      lines.append("  return __ffi_r;")
    else:
      lines.append(f"  return {_wrap_c_call_as_ret(c_call, ret_ann, store)};")
    lines.append("}")
    lines.append("")


def emit_all_ffi_glue(tr: Translator) -> None:
  for module_path in tr.module_order:
    emit_ffi_module_glue(tr, module_path)
