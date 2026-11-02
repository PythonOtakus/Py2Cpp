"""``@delegate`` 译期子类：``DelegateInfo`` → ctx → ``templates/core/~delegate_class.inl``。"""
from __future__ import annotations

from ..analysis.delegates import DelegateInfo
from .expand_py2cpp_template import expand_template


def emit_delegate_class(info: DelegateInfo, *, lines: list[str]) -> None:
  ret = info.ret_cpp
  base_args = _base_args(info)
  base = f"PyDelegate<{ret}, {base_args}>" if base_args else f"PyDelegate<{ret}>"
  params = info.call_param_decls()
  args = info.call_args()
  template_decl = ""
  if info.is_template():
    tdecl = ", ".join(f"typename {p}" for p in info.all_template_names)
    template_decl = f"template<{tdecl}>"
  if params:
    op_decl = f"{ret} operator()({params}) const {{"
  else:
    op_decl = f"{ret} operator()() const {{"
  if ret == "void":
    invoke = f"Base::_invoke({args});" if args else "Base::_invoke();"
  else:
    invoke = f"return Base::_invoke({args});" if args else "return Base::_invoke();"
  text = expand_template(
    "core/~delegate_class.inl",
    {
      "ctx_Name": info.cpp_name(),
      "ctx_Base": base,
      "ctx_TplDecl": template_decl,
      "ctx_OperatorDecl": op_decl,
      "ctx_InvokeBody": invoke,
      "module_rel": "core/delegate",
    },
    apply_allman=True,
  )
  lines.extend(text.splitlines())
  lines.append("")


def _base_args(info: DelegateInfo) -> str:
  if not info.params:
    return ""
  return ", ".join(p.cpp_type for p in info.params)
