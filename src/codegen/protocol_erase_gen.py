"""``@protocol`` → 运行时擦除 ``Py{Name}`` / ``make{Name}``（``protocol_erase.h``）。"""
from __future__ import annotations

from ..analysis.stubs.protocol_erase_stubs import (
  ProtocolEraseMethod,
  ProtocolEraseSpec,
  erased_protocol_cpp_name,
  erased_protocol_make_fn,
  protocol_erase_specs_for_header,
)
from ..analysis.ir import codegen_file_header_lines
from .expand_py2cpp_template import expand_template

_SPEC_TEMPLATE = "core/~protocol_erase_spec.inl"
_PREAMBLE_TEMPLATE = "core/~protocol_erase_preamble.inl"


def _base_name(spec: ProtocolEraseSpec) -> str:
  return erased_protocol_cpp_name(spec.name)


def _tpl_decl(spec: ProtocolEraseSpec) -> str:
  if not spec.type_params:
    return ""
  tps = ", ".join(f"typename {p}" for p in spec.type_params)
  return f"template<{tps}>\n"


def _tpl_args(spec: ProtocolEraseSpec) -> str:
  if not spec.type_params:
    return ""
  return "<" + ", ".join(spec.type_params) + ">"


def _qualified(spec: ProtocolEraseSpec) -> str:
  return _base_name(spec) + _tpl_args(spec)


def _type_params_with_impl(spec: ProtocolEraseSpec) -> str:
  if spec.type_params:
    tps = ", ".join(f"typename {p}" for p in spec.type_params)
    return f"{tps}, typename Impl"
  return "typename Impl"


def _emit_public_method(spec: ProtocolEraseSpec, method: ProtocolEraseMethod) -> str:
  params_decl = ", ".join(f"{t} {n}" for n, t in method.params)
  lines: list[str] = []
  if (
    spec.name == "IteratorType"
    and method.name == "__iter__"
    and not method.params
  ):
    lines.append(f"  PyIterator<{spec.type_params[0]}>& __iter__()")
    lines.append("  {")
    lines.append("    return *this;")
    lines.append("  }")
    return "\n".join(lines)
  if (
    spec.name == "AsyncIteratorType"
    and method.name == "__aiter__"
    and not method.params
  ):
    lines.append(f"  PyAsyncIterator<{spec.type_params[0]}>& __aiter__()")
    lines.append("  {")
    lines.append("    return *this;")
    lines.append("  }")
    return "\n".join(lines)
  if method.is_void:
    lines.append(f"  void {method.name}({params_decl})")
  else:
    lines.append(f"  {method.ret_cpp} {method.name}({params_decl})")
  lines.append("  {")
  call = ", ".join(n for n, _ in method.params)
  if method.is_void:
    if call:
      lines.append(f"    _fn_{method.name}(_ctx, {call});")
    else:
      lines.append(f"    _fn_{method.name}(_ctx);")
  elif call:
    lines.append(f"    return _fn_{method.name}(_ctx, {call});")
  else:
    lines.append(f"    return _fn_{method.name}(_ctx);")
  lines.append("  }")
  return "\n".join(lines)


def _identity_protocol_method_names(spec: ProtocolEraseSpec) -> frozenset[str]:
  if spec.name == "IteratorType":
    return frozenset({"__iter__"})
  if spec.name == "AsyncIteratorType":
    return frozenset({"__aiter__"})
  return frozenset()


def _vtable_methods(spec: ProtocolEraseSpec) -> tuple[ProtocolEraseMethod, ...]:
  skip = _identity_protocol_method_names(spec)
  return tuple(m for m in spec.methods if m.name not in skip)


def _emit_vtable_decl(method: ProtocolEraseMethod) -> str:
  ret = "void" if method.is_void else method.ret_cpp
  argty = ", ".join(["void* ctx"] + [f"{t} {n}" for n, t in method.params])
  return f"  {ret} (*_fn_{method.name})({argty});"


def _emit_model_thunk(
  spec: ProtocolEraseSpec, method: ProtocolEraseMethod, *, by_pointer: bool,
) -> str:
  ret = "void" if method.is_void else method.ret_cpp
  argty = ", ".join(["void* ctx"] + [f"{t} {n}" for n, t in method.params])
  call = ", ".join(n for n, _ in method.params)
  recv = "self->impl->" if by_pointer else "self->impl."
  lines: list[str] = []
  lines.append(f"  static {ret} {method.name}({argty})")
  lines.append("  {")
  lines.append("    model_t* self = static_cast<model_t*>(ctx);")
  if method.is_void:
    lines.append(
      f"    {recv}{method.name}({call});" if call else f"    {recv}{method.name}();"
    )
  else:
    ret_line = (
      f"    return {recv}{method.name}({call});"
      if call
      else f"    return {recv}{method.name}();"
    )
    if (
      spec.name == "IterableType"
      and method.name == "__iter__"
      and len(spec.type_params) == 1
    ):
      tp = spec.type_params[0]
      inner = (
        f"self->impl->{method.name}()"
        if not call
        else f"self->impl->{method.name}({call})"
      )
      ret_line = f"    return makeIterator<{tp}>({inner});"
    lines.append(ret_line)
  lines.append("  }")
  return "\n".join(lines)


def _spec_template_ctx(spec: ProtocolEraseSpec) -> dict[str, object]:
  vtable = _vtable_methods(spec)
  base = _base_name(spec)
  access = f"py2cpp_{spec.name.lower()}_access"
  return {
    "ctx_TplDecl": _tpl_decl(spec),
    "ctx_Base": base,
    "ctx_Qualified": _qualified(spec),
    "ctx_TplArgs": _tpl_args(spec),
    "ctx_MakeFn": erased_protocol_make_fn(spec.name),
    "ctx_Access": access,
    "ctx_HasTypeParams": bool(spec.type_params),
    "ctx_TypeParamsWithImpl": _type_params_with_impl(spec),
    "ctx_TypeParamsMakeArgs": ", ".join(spec.type_params),
    "ctx_PublicMethods": "\n\n".join(
      _emit_public_method(spec, method) for method in spec.methods
    ),
    "ctx_CtorVtableInits": "".join(f", _fn_{m.name}(0)" for m in vtable),
    "ctx_VtableDecls": "\n".join(_emit_vtable_decl(m) for m in vtable),
    "ctx_ModelThunks": "\n".join(_emit_model_thunk(spec, m, by_pointer=True) for m in vtable),
    "ctx_ResetClears": "\n".join(f"  _fn_{m.name} = 0;" for m in vtable),
    "ctx_CopyCtorInits": "".join(
      f", _fn_{m.name}(other._fn_{m.name})" for m in vtable
    ),
    "ctx_CopyAssignStmts": "\n".join(
      f"    _fn_{m.name} = other._fn_{m.name};" for m in vtable
    ),
    "ctx_MoveCtorInits": "".join(
      f", _fn_{m.name}(other._fn_{m.name})" for m in vtable
    ),
    "ctx_MoveCtorOtherClears": "\n".join(
      f"  other._fn_{m.name} = 0;" for m in vtable
    ),
    "ctx_MoveAssignStmts": "\n".join(
      f"    _fn_{m.name} = other._fn_{m.name};" for m in vtable
    ),
    "ctx_MoveAssignOtherClears": "\n".join(
      f"    other._fn_{m.name} = 0;" for m in vtable
    ),
    "ctx_MakeLvalueFnAssigns": "\n".join(
      f"    out._fn_{m.name} = &model_t::{m.name};" for m in vtable
    ),
    "ctx_MakeRvalueFnAssigns": "\n".join(
      f"    out._fn_{m.name} = &model_t::{m.name};" for m in vtable
    ),
  }


def _render_spec(spec: ProtocolEraseSpec) -> str:
  return expand_template(_SPEC_TEMPLATE, _spec_template_ctx(spec), apply_allman=True)


def _protocol_erase_body_lines(specs: tuple[ProtocolEraseSpec, ...]) -> list[str]:
  lines: list[str] = []
  for spec in specs:
    lines.extend(_render_spec(spec).splitlines())
    lines.append("")
  if lines and lines[-1] == "":
    lines.pop()
  return lines


def protocol_erase_header_lines(*, generated_at: str) -> list[str]:
  preamble = expand_template(_PREAMBLE_TEMPLATE, apply_allman=True).strip()
  # 擦除头在全局命名空间，且早于 bulk ``list.h``；库 TU 跳过 ``str.inl``
  # 后不再有 ``using PyList``。自包含声明 + using，勿依赖其它模块 ``.inl``。
  lines: list[str] = [
    *codegen_file_header_lines("py2cpp/**/protocols.py（运行时擦除）", generated_at),
    "#ifndef PY2CPP_PROTOCOL_ERASE_H",
    "#define PY2CPP_PROTOCOL_ERASE_H",
    "",
    '#include "py2cpp/core/none.h"',
    '#include "py2cpp/text/str.h"',
    '#include "py2cpp/util/list.h"',
    '#include "py2cpp/util/tuple.h"',
    "",
    "using ::py2cpp::core::none::PyNone;",
    "using ::py2cpp::text::str::PyStr;",
    "using ::py2cpp::util::list::PyList;",
    "",
    preamble,
    "",
  ]
  lines.extend(_protocol_erase_body_lines(protocol_erase_specs_for_header(late=False)))
  lines.append("#endif // PY2CPP_PROTOCOL_ERASE_H")
  lines.append("")
  return lines


def protocol_erase_domain_header_lines(*, generated_at: str) -> list[str]:
  specs = protocol_erase_specs_for_header(late=True)
  if not specs:
    return []
  lines: list[str] = [
    *codegen_file_header_lines(
      "py2cpp/serde/protocols.py 等（运行时擦除 · long 域）",
      generated_at,
    ),
    "#ifndef PY2CPP_PROTOCOL_ERASE_DOMAIN_H",
    "#define PY2CPP_PROTOCOL_ERASE_DOMAIN_H",
    "",
  ]
  lines.extend(_protocol_erase_body_lines(specs))
  lines.append("#endif // PY2CPP_PROTOCOL_ERASE_DOMAIN_H")
  lines.append("")
  return lines
