"""codegen 模板插入时机：hook 名 → ``templates/<rel>``（C++ 体在模板，Python 只拼 ctx / 调用 ``expand_template``）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodegenInsertHook:
  template_rel: str
  note: str
  module_rel: str | None = None


CODEGEN_INSERT_HOOKS: dict[str, CodegenInsertHook] = {
  "layout.primitive_headers": CodegenInsertHook(
    "operators.h",
    "``write_primitive_type_headers``：char/byte/CStr/py_types/member_access/operators",
  ),
  "layout.umbrella_header": CodegenInsertHook(
    "minimal.h",
    "``build_py2cpp_umbrella_header`` → ``generated/runtime/py2cpp/minimal.h``",
  ),
  "translator.debug_inject": CodegenInsertHook(
    "debug.inl",
    "``Translator`` 在翻译 TU 内联 debug 跟踪（``--debug``）",
  ),
  "class_decl.protocol_preamble": CodegenInsertHook(
    "~protocol_module_preamble.inl",
    "``_emit_module_protocol_traits`` 模块头前导 include/声明",
  ),
  "class_decl.protocol_compare_ops": CodegenInsertHook(
    "~protocol_compare_ops.inl",
    "``ComparableType``/``EquatableType`` 模块 traits 前的 ``_Compare_ops_no_pybool_only``",
  ),
  "class_decl.protocol_traits": CodegenInsertHook(
    "~protocol_traits.inl",
    "``protocol_traits_lines`` 单类型参数协议 SFINAE 壳",
  ),
  "class_decl.protocol_traits_parametric": CodegenInsertHook(
    "~protocol_traits_parametric.inl",
    "``protocol_traits_lines`` 多类型参数协议（如 ``NavigatableType``）",
  ),
  "class_decl.exception_forward_decls": CodegenInsertHook(
    "core/~exception_forward_decls.inl",
    "``Exception`` 类声明前向声明",
    module_rel="core/exceptions",
  ),
  "class_decl.exception_pystr_ctor": CodegenInsertHook(
    "core/~exception_pystr_ctor.inl",
    "``core/exceptions`` 各类 ``PyStr`` 构造",
    module_rel="core/exceptions",
  ),
  "class_decl.exception_group_header": CodegenInsertHook(
    "core/~exception_group_dynamic_header.inl",
    "``ExcTypeUnion`` 存在时 ``ExceptionGroup`` 类尾 inject",
    module_rel="core/exceptions",
  ),
  "stdlib_inject.exception_group_impl": CodegenInsertHook(
    "core/~exception_group_dynamic_impl.inl",
    "``paste_after`` ``core/exceptions`` 模块 ``.inl``",
    module_rel="core/exceptions",
  ),
  "translator.delegate_subclass": CodegenInsertHook(
    "core/~delegate_class.inl",
    "``@delegate`` 译期具体子类（``DelegateInfo`` ctx）",
    module_rel="core/delegate",
  ),
}
