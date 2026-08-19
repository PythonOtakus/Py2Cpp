"""``ffi/**/*.pyi`` 的 ``@native`` / ``@native_name`` → 薄 ``.inl`` 转发到 C 符号。

命名空间为 ``ffi::…``（不挂 ``py2cpp::``）。结构体类型为 ``Pyi_*``（``using`` 到 C）；glue 对指针/按值尽量直传。

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
  ffi_header_symbol_allowlist,
  ffi_msvc_comment_libs,
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
  "CStr": "CStr",
}


# ``CStr`` is represented as ``const char*`` in generated C++.  A small
# set of C APIs uses a ``char*`` output buffer but is emitted as ``CStr`` by
# the header generator, so glue performs the only required mutable cast.
_MUTABLE_CSTR_PARAMS: frozenset[tuple[str, str]] = frozenset({
  ("fgets", "_Buffer"),
  ("snprintf", "_Buffer"),
  ("vsnprintf", "_Buffer"),
  ("GetEnvironmentVariableA", "lpBuffer"),
  ("GetWindowTextA", "lpString"),
  ("FreeEnvironmentStringsA", "penv"),
  ("WideCharToMultiByte", "lpMultiByteStr"),
  ("strftime", "_Buffer"),
  ("_getcwd", "_DstBuf"),
  ("GetFullPathNameA", "lpBuffer"),
  ("GetFinalPathNameByHandleA", "lpszFilePath"),
})

_WIDE_CHAR_POINTER_PARAMS: frozenset[tuple[str, str]] = frozenset({
  ("CommandLineToArgvW", "lpCmdLine"),
  ("WideCharToMultiByte", "lpWideCharStr"),
})

@dataclass(frozen=True)
class _Ann:
  kind: str  # void|scalar|cstr|struct|fn|ptr_struct|ptr_scalar|ptr_cstr|ptr_ptr|unsupported
  name: str = ""


def _parse_ann(node: ast.expr | None) -> _Ann:
  if node is None:
    return _Ann("void")
  if isinstance(node, ast.Constant) and node.value is None:
    return _Ann("void")
  if isinstance(node, ast.Name):
    if node.id == "None":
      return _Ann("void")
    if node.id == "CStr":
      return _Ann("cstr")
    if node.id in _SCALAR_CAST:
      return _Ann("scalar", node.id)
    # 按值结构体 / 历史 *_h 名（剥后缀得 C 标签）
    return _Ann("struct", node.id)
  if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
    if node.value.id == "Function":
      return _Ann("fn")
    if node.value.id != "Pointer":
      return _Ann("unsupported")
    sl = node.slice
    if isinstance(sl, ast.Name):
      if sl.id == "CStr":
        return _Ann("ptr_cstr")
      if sl.id in _SCALAR_CAST:
        return _Ann("ptr_scalar", sl.id)
      return _Ann("ptr_struct", sl.id)
    if isinstance(sl, ast.Subscript):
      # Pointer[Pointer[T]] → 直接传 T**
      return _Ann("ptr_ptr")
  return _Ann("unsupported")


def _c_name(func: ast.FunctionDef) -> str:
  n = decorator_string_arg(func, "native_name") or func.name
  return n[2:] if n.startswith("::") else n


def _emit_arg_expr(pname: str, ann: _Ann, *, c_name: str) -> tuple[list[str], str]:
  if ann.kind == "cstr":
    if c_name == "vsnprintf" and pname == "_ArgList":
      return [], f"reinterpret_cast<va_list>(const_cast<char*>({pname}))"
    if (c_name, pname) in _MUTABLE_CSTR_PARAMS:
      return [], f"const_cast<char*>({pname})"
    return [], pname
  if ann.kind == "fn":
    # C 回调签名与 Py Function 指针布局一致但类型名不同，按需收窄
    if c_name == "sqlite3_exec" and pname == "callback":
      return [], (
        f"reinterpret_cast<int(__cdecl*)(void*,int,char**,char**)>({pname})"
      )
    return [], pname
  if ann.kind == "scalar":
    if ann.name == "uintptr":
      # void* / 上下文指针：统一经 void* 再交 C
      if c_name == "sqlite3_exec" and pname == "arg3":
        return [], f"reinterpret_cast<void*>(static_cast<uintptr_t>({pname}))"
      return [], f"reinterpret_cast<void*>(static_cast<uintptr_t>({pname}))"
    return [], pname
  if ann.kind == "struct":
    # 按值传递；若误传不完整类型会在 C++ 编译期失败
    return [], pname
  if ann.kind == "ptr_struct":
    # 已是 Pyi_T*（using → C）；直传
    return [], pname
  if ann.kind == "ptr_scalar":
    # PyFloat* / PyFloat64* → C float* / double*（与 py2cpp 标量宽度一致）
    if ann.name == "float":
      return [], f"reinterpret_cast<float*>({pname})"
    if ann.name == "float64":
      return [], f"reinterpret_cast<double*>({pname})"
    if ann.name == "uint" and (c_name, pname) in _WIDE_CHAR_POINTER_PARAMS:
      return [], f"reinterpret_cast<const wchar_t*>({pname})"
    if c_name == "ReleaseSemaphore" and pname == "lpPreviousCount":
      return [], f"reinterpret_cast<LONG*>({pname})"
    return [], pname
  if ann.kind == "ptr_cstr":
    # ``CStr*`` ≈ ``const char**``；个别 API（如 ``sqlite3_exec`` errmsg）要 ``char**``
    if c_name == "sqlite3_exec" or (c_name, pname) in {("GetFullPathNameA", "lpFilePart")}:
      return [], f"reinterpret_cast<char**>(static_cast<void*>({pname}))"
    return [], f"reinterpret_cast<const char**>(static_cast<void*>({pname}))"
  if ann.kind == "ptr_ptr":
    return [], pname
  if ann.kind == "unsupported":
    return [], f"reinterpret_cast<void*>(static_cast<uintptr_t>({pname}))"
  return [], pname


def _emit_out_writes(pname: str, ann: _Ann) -> list[str]:
  _ = (pname, ann)
  return []


def _ret_store_type(ann: _Ann, fallback: str) -> str:
  if ann.kind == "void":
    return "void"
  if ann.kind == "struct":
    return fallback
  if ann.kind == "cstr":
    return "CStr"
  if ann.kind == "fn":
    return fallback
  if ann.kind == "scalar":
    return _SCALAR_CAST.get(ann.name, fallback)
  return fallback


def _wrap_c_call_as_ret(c_call: str, ann: _Ann, store: str) -> str:
  if ann.kind == "cstr":
    return f"(CStr)({c_call})"
  if ann.kind == "fn":
    return f"({store})({c_call})"
  if ann.kind == "scalar":
    return f"({store})({c_call})"
  if ann.kind == "struct":
    return f"({store})({c_call})"
  return f"({store})({c_call})"


def _qualify_pyi_types(cpp_type: str, ns: str) -> str:
  """``.inl`` 在命名空间闭合后包含：返回类型在限定名之前，须写 ``ns::Pyi…``。"""
  if not ns or not cpp_type:
    return cpp_type
  import re

  return re.sub(
    r"(?<![:\w])(Pyi[A-Z][A-Za-z0-9_]*)",
    rf"{ns}::\1",
    cpp_type,
  )


def emit_ffi_module_glue(tr: Translator, module_path: str) -> None:
  if not is_ffi_module_path(module_path):
    return
  c_inc = ffi_c_header_include(module_path)
  if c_inc is None:
    return
  allow = ffi_glue_allowlist(module_path)
  native_funcs = [
    f
    for f in tr._module_emit_functions_for(module_path)
    if has_named_decorator(f, "native")
  ]
  funcs = [f for f in native_funcs if not has_named_decorator(f, "overload")]
  if allow is not None:
    funcs = [f for f in funcs if _c_name(f) in allow]
    emitted = {(f.name, _c_name(f)) for f in funcs}
    funcs.extend(
      f
      for f in native_funcs
      if has_named_decorator(f, "overload")
      and _c_name(f) in allow
      and (f.name, _c_name(f)) not in emitted
    )
  if not funcs:
    return
  lines = tr.per_module_inl_lines.setdefault(module_path, [])
  if lines and any("py2cpp FFI glue" in ln for ln in lines):
    return
  lines.append(f'// py2cpp FFI glue → C ({c_inc})')
  # 尖括号：勿用引号，否则同目录生成的 ``sqlite3.h`` 会自包含（guard 已定义 → C API 被跳过）
  if norm := module_path.replace("\\", "/").strip("/"):
    if norm == "ffi/gl/gl":
      lines.append("#ifdef _WIN32")
      lines.append("#ifndef WIN32_LEAN_AND_MEAN")
      lines.append("#define WIN32_LEAN_AND_MEAN")
      lines.append("#endif")
      lines.append("#include <windows.h>")
      lines.append("#endif")
  lines.append(f"#include <{c_inc}>")
  lines.append("#include <stdint.h>")
  for lib in ffi_msvc_comment_libs(module_path):
    lines.append(f'#pragma comment(lib, "{lib}")')
  lines.append("")
  ns = namespace_qualifier_for_module(module_path)
  for func in funcs:
    fsig = tr._function_sig_for(module_path, func)
    cpp_name = tr._module_function_cpp_name(module_path, func)
    if "::" in cpp_name:
      continue
    qname = f"{ns}::{cpp_name}" if ns else cpp_name
    ret = _qualify_pyi_types(tr._sig_return_storage(fsig), ns)
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
    # C ``printf(fmt, ...)`` ← ``def pyiPrintf(_Format: CStr, *_)``
    if func.args.vararg is not None:
      call_args.append(f"{cpp_param(func.args.vararg.arg)}...")
    c_call = f"::{cnm}({', '.join(call_args)})"
    if func.args.vararg is not None:
      lines.append("template<typename... __Ts>")
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

  # C 头在上方 #include 后会重新定义与 FFI 常量同名的宏；再 #undef，
  # 否则 ``::ffi::…::GLFW_TRUE`` 等限定名仍被预处理成 ``::ffi::…::1``。
  const_names = [
    node.target.id
    for mp, node in tr.module_constants
    if mp == module_path
    and isinstance(node.target, ast.Name)
    and node.target.id != "__all__"
  ]
  header_symbols = ffi_header_symbol_allowlist(module_path)
  if header_symbols is not None:
    const_names = [name for name in const_names if name in header_symbols]
  if const_names:
    lines.append("// 撤销 C 头对 FFI 常量对应宏的再定义（PyiX → X）")
    seen_c: set[str] = set()
    # 常量节点在 tr.module_constants；优先注解 ``@native_name``
    from ..analysis.ir import parse_native_name_type_annotation

    const_by_name = {
      n.target.id: n
      for mp, n in tr.module_constants
      if mp == module_path and isinstance(n.target, ast.Name)
    }
    for name in const_names:
      node = const_by_name.get(name)
      c_macro = (
        parse_native_name_type_annotation(node.annotation)
        if node is not None
        else None
      )
      if not c_macro:
        if name.startswith("Pyi_"):
          c_macro = name[4:]
        else:
          c_macro = name
      # FFI constants retain their ``Pyi…`` C++ name.  A C macro only needs
      # removal when the emitted declaration itself has that exact name.
      if c_macro != name or c_macro in seen_c:
        continue
      seen_c.add(c_macro)
      lines.append(f"#ifdef {c_macro}")
      lines.append(f"#undef {c_macro}")
      lines.append("#endif")
    lines.append("")


def emit_all_ffi_glue(tr: Translator) -> None:
  for module_path in tr.module_order:
    emit_ffi_module_glue(tr, module_path)
