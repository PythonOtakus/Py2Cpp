"""由 dunder 方法生成 C++ ``operator`` 重载，以及基本类型的全局 dunder 函数。

映射见 ``constant/dunder_ops.py``；有 ``__cmp__`` 时比较运算符由 ``cmp_ops_emit`` 生成。
非 ``@immutable`` 的 dunder 仍生成对应 ``operator``（成员无 ``const``）；``__r*__`` 友元在非
``const`` 时对右操作数按值传参以便 ``n * s`` 等用法可编译。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..codegen.brace_style import kr_to_allman
from ..analysis.type_emit import method_param_types_map, sig_return_full_cpp
from ..constant.dunder_ops import (
  BINARY_DUNDER_TO_CPP_OP,
  BINARY_DUNDER_TO_INPLACE,
  BINARY_DUNDER_TO_REVERSE,
  COMPARE_DUNDERS,
  SKIP_OPERATOR_DUNDERS,
  UNARY_DUNDER_TO_CPP_OP,
)
from .cmp_ops_emit import emit_cmp_operator_overloads

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo, MethodSig


def _other_param_type(msig: MethodSig) -> str:
  for name, cpp_t in method_param_types_map(msig).items():
    if name != "self":
      return cpp_t
  return "void*"


def _operator_param_decl(cpp_t: str, name: str) -> str:
  """``operator`` 形参：已是 ``const T&`` 时勿再包 ``const … &``。"""
  t = cpp_t.strip()
  if t.endswith("&"):
    return f"{t} {name}"
  return f"const {t}& {name}"


def _operator_other_decl(msig: MethodSig) -> str:
  return _operator_param_decl(_other_param_type(msig), "other")


def _ret_cpp_type(msig: MethodSig) -> str:
  return sig_return_full_cpp(msig)


def _has_binary_dunder(info: ClassInfo, dunder: str) -> bool:
  return dunder in info.methods or dunder in info.method_overloads


def _binary_dunder_overload_sigs(info: ClassInfo, dunder: str) -> list[MethodSig]:
  sigs: list[MethodSig] = []
  seen: set[int] = set()
  for method in info.method_overloads.get(dunder, []):
    sig = info.method_sig_for(method)
    if sig is not None and id(sig) not in seen:
      sigs.append(sig)
      seen.add(id(sig))
  if dunder in info.methods:
    sig = info.method_sig_for(info.methods[dunder])
    if sig is not None and id(sig) not in seen:
      sigs.append(sig)
  return sigs


def _emit_member_binary(
  cpp_class: str,
  dunder: str,
  cpp_op: str,
  msig: MethodSig,
  *,
  is_bool: bool,
  is_const: bool,
) -> list[str]:
  other = _operator_other_decl(msig)
  ret = _ret_cpp_type(msig)
  const = " const" if is_const else ""
  if is_bool and "bool" not in ret:
    ret = "bool"
  lines = [
    f"{ret} operator{cpp_op}({other}){const}",
    "{",
    f"  return {dunder}(other);",
    "}",
  ]
  return lines


def _skip_reverse_friend(cpp_class: str, other: str) -> bool:
  """``__radd__(Self)`` 等仅 ``other + self``，同类型已有成员 ``operator``，勿再生成 friend。"""
  o = other.strip()
  c = cpp_class.strip()
  if o == c:
    return True
  if o.startswith(f"{c}<"):
    return True
  return False


def _emit_reverse_binary(
  cpp_class: str, rdunder: str, cpp_op: str, msig: MethodSig
) -> list[str]:
  other = _other_param_type(msig)
  lhs = _operator_param_decl(other, "lhs")
  ret = _ret_cpp_type(msig)
  # 非 ``@immutable`` 的 ``__r*__`` 无法在 ``const`` 接收方上调用；右操作数按值传入再委托。
  rhs_param = f"const {cpp_class}& rhs" if msig.is_const else f"{cpp_class} rhs"
  lines = [
    f"friend {ret} operator{cpp_op}({lhs}, {rhs_param})",
    "{",
    f"  return rhs.{rdunder}(lhs);",
    "}",
  ]
  return lines


def _emit_inplace_binary(cpp_class: str, idunder: str, cpp_op: str, msig: MethodSig) -> list[str]:
  other = _operator_other_decl(msig)
  lines = [
    f"{cpp_class}& operator{cpp_op}({other})",
    "{",
    f"  return {idunder}(other);",
    "}",
  ]
  return lines


def _emit_unary(
  cpp_class: str, dunder: str, cpp_op: str, msig: MethodSig, *, is_const: bool
) -> list[str]:
  ret = _ret_cpp_type(msig)
  const = " const" if is_const else ""
  lines = [
    f"{ret} operator{cpp_op}(){const}",
    "{",
    f"  return {dunder}();",
    "}",
  ]
  return lines


def emit_class_operator_overloads(info: ClassInfo) -> list[str]:
  """在类声明 public 段末尾插入的 ``operator`` 重载（Allman）。"""
  cpp = info.cpp_name()
  chunks: list[str] = []
  has_cmp = "__cmp__" in info.methods
  has_eq = "__eq__" in info.methods

  if has_cmp:
    chunks.extend(emit_cmp_operator_overloads(cpp, has_eq=has_eq))

  emitted_member_ops: set[tuple[str, str]] = set()
  for dunder, cpp_op in BINARY_DUNDER_TO_CPP_OP.items():
    if dunder in SKIP_OPERATOR_DUNDERS or not _has_binary_dunder(info, dunder):
      continue
    if has_cmp and dunder in COMPARE_DUNDERS:
      continue
    for msig in _binary_dunder_overload_sigs(info, dunder):
      if msig.func_ft.template_names:
        continue
      other = _other_param_type(msig)
      key = (cpp_op, other)
      if key in emitted_member_ops:
        continue
      emitted_member_ops.add(key)
      chunks.extend(
        _emit_member_binary(
          cpp,
          dunder,
          cpp_op,
          msig,
          is_bool=dunder in COMPARE_DUNDERS,
          is_const=msig.is_const,
        )
      )

  emitted_reverse_ops: set[tuple[str, str]] = set()
  for dunder, cpp_op in BINARY_DUNDER_TO_CPP_OP.items():
    rdunder = BINARY_DUNDER_TO_REVERSE.get(dunder)
    if dunder in SKIP_OPERATOR_DUNDERS or not rdunder or not _has_binary_dunder(info, rdunder):
      continue
    for msig in _binary_dunder_overload_sigs(info, rdunder):
      if msig.func_ft.template_names:
        continue
      other = _other_param_type(msig)
      if _skip_reverse_friend(cpp, other):
        continue
      key = (cpp_op, other)
      if key in emitted_reverse_ops:
        continue
      emitted_reverse_ops.add(key)
      chunks.extend(_emit_reverse_binary(cpp, rdunder, cpp_op, msig))

  for base_dunder, idunder in BINARY_DUNDER_TO_INPLACE.items():
    if idunder not in info.methods:
      continue
    cpp_op = BINARY_DUNDER_TO_CPP_OP.get(base_dunder)
    if not cpp_op:
      continue
    msig = info.method_sig_for(info.methods[idunder])
    if msig is None:
      continue
    op = cpp_op if cpp_op.endswith("=") else f"{cpp_op}="
    chunks.extend(_emit_inplace_binary(cpp, idunder, op, msig))

  for dunder, cpp_op in UNARY_DUNDER_TO_CPP_OP.items():
    if dunder not in info.methods:
      continue
    msig = info.method_sig_for(info.methods[dunder])
    if msig is None:
      continue
    chunks.extend(_emit_unary(cpp, dunder, cpp_op, msig, is_const=msig.is_const))

  if not chunks:
    return []
  return kr_to_allman("\n".join(chunks)).splitlines()
