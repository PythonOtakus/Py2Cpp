"""``@protocol`` → SFINAE traits（探测逻辑在此；C++ 壳见 ``templates/~protocol_traits*.inl``）。"""
from __future__ import annotations

from ..analysis.ir import ProtocolMemberConstraint, cpp_ident, escape_cpp_param
from ..emit.compile_diagnostic_emit import (
  compile_diag_c_utf8_literal,
  compile_diag_protocol_unsatisfied,
)
from ..constant.stdlib_layout import STR_PYSTR
from ..constant.dunder_ops import (
  BINARY_DUNDER_TO_CPP_OP,
  BINARY_DUNDER_TO_REVERSE,
  UNARY_DUNDER_TO_CPP_OP,
)
from .expand_py2cpp_template import expand_template

_REVERSE_TO_FORWARD_DUNDER = {rev: fwd for fwd, rev in BINARY_DUNDER_TO_REVERSE.items()}

GLOBAL_UNARY_PROBE: dict[str, str] = {
  "__len__": "len",
  "__iter__": "iter",
  "__next__": "next",
  "__aiter__": "aiter",
  "__anext__": "anext",
  "__reversed__": "reversed",
  "__hash__": "hash",
}

GLOBAL_BINARY_PROBE: dict[str, str] = {
  "__pow__": "pow",
  "__matmul__": "__matmul__",
  "__contains__": "__contains__",
  "__mod__": "__mod__",
  "__truediv__": "__truediv__",
  "__floordiv__": "__floordiv__",
}

_GLOBAL_BINARY_DUNDERS = frozenset({"__mod__", "__truediv__", "__floordiv__"})

ProtocolMethodSpec = tuple[str, str]
ProtocolStaticMethodSpec = tuple[str, str, tuple[str, ...], tuple[str, ...]]


def compare_ops_no_pybool_only_helper_lines() -> list[str]:
  text = expand_template("~protocol_compare_ops.inl", apply_allman=True)
  return [ln for ln in text.splitlines() if ln.strip()]


def protocol_module_preamble_lines() -> list[str]:
  text = expand_template("~protocol_module_preamble.inl", apply_allman=False)
  return [ln for ln in text.splitlines() if ln.strip()]


def _probe_ret_cpp(ret_cpp: str) -> str:
  return "U" if ret_cpp == "Self" else ret_cpp


def _probe_param_cpp(param_cpp: str) -> str:
  return "U" if param_cpp == "Self" else param_cpp


def _ret_type_check(expr: str, ret_cpp: str) -> str:
  want = _probe_ret_cpp(ret_cpp)
  return f"(void)std::is_same<decltype({expr}), {want}>::value"


def _operator_probe_not_pybool_only() -> str:
  return "(void)(_Compare_ops_no_pybool_only<U>::ok)"


def _probe_dunder(dunder: str) -> str:
  return _REVERSE_TO_FORWARD_DUNDER.get(dunder, dunder)


def _sfinae_cast_probe(dunder: str, ret_cpp: str) -> str | None:
  want = _probe_ret_cpp(ret_cpp)
  u = "U"
  if dunder == "__float__" and want == cpp_ident("float"):
    return _ret_type_check(f"(PyFloat)std::declval<const {u}&>()", ret_cpp)
  if dunder == "__int__" and want == cpp_ident("int"):
    return _ret_type_check(f"(PyInt)std::declval<const {u}&>()", ret_cpp)
  if dunder == "__complex__" and want == cpp_ident("complex"):
    return (
      f"(void)(std::is_same<{u}, PyFloat>::value || std::is_same<{u}, PyInt>::value "
      f"|| std::is_same<decltype(std::declval<{u}&>().__complex__()), PyComplex<PyFloat>>::value)"
    )
  return None


def _sfinae_abs_probe(dunder: str, ret_cpp: str) -> str | None:
  if dunder != "__abs__":
    return None
  u = "U"
  expr = (
    f"(std::declval<{u}>() < 0 ? -std::declval<const {u}&>() "
    f": std::declval<const {u}&>())"
  )
  if ret_cpp:
    return _ret_type_check(expr, ret_cpp)
  return f"(void)({expr})"


def _sfinae_unary_operator_probe(dunder: str, ret_cpp: str) -> str | None:
  op = UNARY_DUNDER_TO_CPP_OP.get(_probe_dunder(dunder))
  if not op:
    return None
  u = "U"
  expr = f"{op}std::declval<const {u}&>()"
  if ret_cpp:
    return _ret_type_check(expr, ret_cpp)
  return f"(void)({expr})"


def _sfinae_operator_probe(
  dunder: str,
  ret_cpp: str,
  *,
  reject_pybool_only: bool = False,
) -> str | None:
  dunder = _probe_dunder(dunder)
  if dunder in _GLOBAL_BINARY_DUNDERS:
    return None
  op = BINARY_DUNDER_TO_CPP_OP.get(dunder)
  if not op:
    return None
  u = "U"
  expr = f"std::declval<const {u}&>() {op} std::declval<const {u}&>()"
  guard = _operator_probe_not_pybool_only() if reject_pybool_only else None
  if ret_cpp:
    parts = [_ret_type_check(expr, ret_cpp)]
    if guard:
      parts.append(guard)
    return ",\n    ".join(parts)
  if guard:
    return f"(void)({expr}),\n    {guard}"
  return f"(void)({expr})"


def _sfinae_complex_probe(dunder: str, ret_cpp: str) -> str | None:
  if dunder != "__complex__":
    return None
  u = "U"
  return (
    f"(void)(std::is_same<{u}, PyFloat>::value || std::is_same<{u}, PyInt>::value "
    f"|| std::is_same<decltype(std::declval<{u}&>().__complex__()), PyComplex<PyFloat>>::value)"
  )


def _sfinae_member_call_probe(dunder: str, ret_cpp: str) -> str | None:
  if not (dunder.startswith("__") and dunder.endswith("__")):
    return None
  u = "U"
  expr = f"std::declval<{u}&>().{dunder}()"
  if ret_cpp:
    return _ret_type_check(expr, ret_cpp)
  return f"(void)({expr})"


def _type_alias_member_ty(
  alias: str,
  *,
  member_specs: list[ProtocolMemberConstraint] | None,
) -> str:
  u = "U"
  if member_specs and any(
    m.kind == "type_alias" and m.name == alias for m in member_specs
  ):
    return f"const typename {u}::{alias}&"
  return f"const {alias}&"


def _sfinae_protocol_static_method_probe(
  name: str,
  ret_cpp: str,
  param_cpp_types: tuple[str, ...],
  *,
  impl_tpl: str = "U",
  method_type_params: tuple[str, ...] = (),
) -> str:
  u = impl_tpl
  mcpp = escape_cpp_param(name)
  if param_cpp_types:
    args = ", ".join(
      f"std::declval<{_probe_param_cpp(t)}>()" for t in param_cpp_types
    )
  else:
    args = ""
  if len(method_type_params) == 1:
    tpl = method_type_params[0]
    if args:
      expr = f"{u}::template {mcpp}<{tpl}>({args})"
    else:
      expr = f"{u}::template {mcpp}<{tpl}>()"
  elif args:
    expr = f"{u}::{mcpp}({args})"
  else:
    expr = f"{u}::{mcpp}()"
  if ret_cpp and ret_cpp not in ("PyNone", "void"):
    return _ret_type_check(expr, ret_cpp)
  return f"(void)({expr})"


def _sfinae_protocol_plain_method_probe(
  name: str,
  ret_cpp: str,
  *,
  member_specs: list[ProtocolMemberConstraint] | None = None,
) -> str | None:
  u = "U"
  if name == "append":
    item_ty = _type_alias_member_ty("Element", member_specs=member_specs)
    expr = f"std::declval<{u}&>().append(std::declval<{item_ty}>())"
    if ret_cpp:
      return _ret_type_check(expr, ret_cpp)
    return f"(void)({expr})"
  if name == "__setitem__":
    key_ty = _type_alias_member_ty("Key", member_specs=member_specs)
    val_ty = _type_alias_member_ty("Value", member_specs=member_specs)
    expr = (
      f"std::declval<{u}&>().__setitem__(std::declval<{key_ty}>(), "
      f"std::declval<{val_ty}>())"
    )
    if ret_cpp:
      return _ret_type_check(expr, ret_cpp)
    return f"(void)({expr})"
  return None


def _sfinae_unary_global_probe(
  dunder: str,
  ret_cpp: str,
  *,
  member_specs: list[ProtocolMemberConstraint] | None = None,
) -> str | None:
  fn = GLOBAL_UNARY_PROBE.get(dunder)
  if not fn:
    return None
  u = "U"
  expr = f"{fn}(std::declval<{u}&>())"
  if ret_cpp and dunder == "__next__":
    elem = ret_cpp
    if member_specs and any(
      m.kind == "type_alias" and m.name == ret_cpp for m in member_specs
    ):
      elem = f"typename U::{ret_cpp}"
    want = elem if elem.startswith("PyIterResult<") else f"PyIterResult<{elem}>"
    return _ret_type_check(expr, want)
  if ret_cpp and dunder in ("__len__", "__hash__"):
    return _ret_type_check(expr, ret_cpp)
  return f"(void)({expr})"


def _sfinae_binary_global_probe(
  dunder: str,
  ret_cpp: str,
  *,
  member_specs: list[ProtocolMemberConstraint] | None = None,
) -> str | None:
  dunder = _probe_dunder(dunder)
  fn = GLOBAL_BINARY_PROBE.get(dunder)
  if not fn:
    return None
  if dunder == "__contains__":
    item_ty = "const PyInt&"
    if member_specs and any(
      m.kind == "type_alias" and m.name == "Element" for m in member_specs
    ):
      item_ty = "const typename U::Element&"
    expr = f"::__contains__(std::declval<U&>(), std::declval<{item_ty}>())"
    if ret_cpp:
      return _ret_type_check(expr, ret_cpp)
    return f"(void)({expr})"
  ps = STR_PYSTR
  if dunder == "__mod__" and _probe_ret_cpp(ret_cpp) in (ps, cpp_ident("str")):
    expr = (
      f"::__mod__(std::declval<const {ps}&>(), "
      f"std::declval<const PyTuple<{cpp_ident('int')}>&>())"
    )
    return _ret_type_check(expr, ps)
  u = "U"
  expr = f"::{fn}(std::declval<const {u}&>(), std::declval<const {u}&>())"
  if ret_cpp:
    return _ret_type_check(expr, ret_cpp)
  return f"(void)({expr})"


def _sfinae_parametric_protocol_plain_method_probe(
  name: str,
  ret_cpp: str,
  *,
  impl_tpl: str = "Impl",
  node_tpl: str = "Node",
) -> str | None:
  u, n = impl_tpl, node_tpl
  if name == "vertex_count":
    return _ret_type_check(f"std::declval<const {u}&>().vertex_count()", ret_cpp)
  if name == "to_index":
    return _ret_type_check(
      f"std::declval<const {u}&>().to_index(std::declval<const {n}&>())", ret_cpp,
    )
  if name == "from_index":
    return _ret_type_check(
      f"std::declval<const {u}&>().from_index(std::declval<PyInt>())", ret_cpp,
    )
  if name == "neighbors":
    return _ret_type_check(
      f"std::declval<const {u}&>().neighbors(std::declval<const {n}&>())", ret_cpp,
    )
  if name == "move_cost":
    return _ret_type_check(
      f"std::declval<const {u}&>().move_cost("
      f"std::declval<const {n}&>(), std::declval<const {n}&>())",
      ret_cpp,
    )
  if name == "heuristic":
    return _ret_type_check(
      f"std::declval<const {u}&>().heuristic("
      f"std::declval<const {n}&>(), std::declval<const {n}&>())",
      ret_cpp,
    )
  return None


def _parametric_assoc_template_name(
  protocol_name: str,
  member_specs: list[tuple[ProtocolMemberConstraint, str]] | None,
  protocol_type_params: list[str],
) -> str:
  if protocol_name == "Navigatable":
    return "Node"
  if member_specs and any(s.kind == "type_alias" and s.name == "Node" for s, _ in member_specs):
    return "Node"
  return protocol_type_params[0] if protocol_type_params else "Node"


def _collect_probe_parts(
  protocol_name: str,
  method_specs: list[ProtocolMethodSpec],
  *,
  static_method_specs: list[ProtocolStaticMethodSpec] | None = None,
  member_specs: list[tuple[ProtocolMemberConstraint, str]] | None = None,
  protocol_type_params: list[str] | None = None,
  impl_tpl: str = "U",
) -> list[str]:
  members = member_specs or []
  probe_parts = [
    p
    for spec, ret_cpp in members
    if (p := _sfinae_protocol_member_probe(spec, ret_cpp))
  ]
  member_constraint_list = [s for s, _ in members]
  reject_pybool_only = protocol_name in ("Comparable", "Equatable")
  node_tpl = None
  if protocol_type_params:
    node_tpl = _parametric_assoc_template_name(
      protocol_name, members, protocol_type_params,
    )
  for method_name, ret in method_specs:
    ret_for_probe = (
      ""
      if method_name in ("__next__", "__contains__") and protocol_type_params
      else ret
    )
    p = None
    if protocol_type_params and node_tpl:
      p = _sfinae_parametric_protocol_plain_method_probe(
        method_name, ret_for_probe, impl_tpl=impl_tpl, node_tpl=node_tpl,
      )
    if p is None:
      p = _sfinae_protocol_plain_method_probe(
        method_name,
        ret_for_probe,
        member_specs=member_constraint_list,
      )
    if p is None:
      p = _sfinae_probe_for_method(
        method_name,
        ret_for_probe,
        member_specs=member_constraint_list,
        reject_pybool_only=reject_pybool_only,
      )
    if p is not None:
      probe_parts.append(p.replace("U", impl_tpl) if impl_tpl != "U" else p)
  for item in static_method_specs or []:
    method_name, ret, params = item[0], item[1], item[2]
    method_type_params = item[3] if len(item) > 3 else ()
    probe_parts.append(
      _sfinae_protocol_static_method_probe(
        method_name,
        ret,
        params,
        impl_tpl=impl_tpl,
        method_type_params=method_type_params,
      )
    )
  return probe_parts


def _probe_ops_private_section(probe_parts: list[str]) -> str:
  if not probe_parts:
    return (
      "  template<typename>\n"
      "  static std::false_type probe_ops(...);"
    )
  joined = ",\n    ".join(probe_parts) + ","
  return (
    "  template<typename U>\n"
    "  static auto probe_ops(int) -> decltype(\n"
    f"    {joined}\n"
    "    std::true_type());\n"
    "  template<typename>\n"
    "  static std::false_type probe_ops(...);"
  )


def _protocol_traits_lines_parametric(
  protocol_name: str,
  method_specs: list[ProtocolMethodSpec],
  *,
  protocol_type_params: list[str],
  member_specs: list[tuple[ProtocolMemberConstraint, str]] | None = None,
  static_method_specs: list[ProtocolStaticMethodSpec] | None = None,
) -> list[str]:
  impl_tpl = "Impl"
  node_tpl = _parametric_assoc_template_name(
    protocol_name, member_specs or [], protocol_type_params,
  )
  probe_parts = _collect_probe_parts(
    protocol_name,
    method_specs,
    static_method_specs=static_method_specs,
    member_specs=member_specs,
    protocol_type_params=protocol_type_params,
    impl_tpl=impl_tpl,
  )
  text = expand_template(
    "~protocol_traits_parametric.inl",
    {
      "ctx_ProtocolName": protocol_name,
      "ctx_ImplTpl": impl_tpl,
      "ctx_NodeTpl": node_tpl,
      "ctx_ProbePrivate": _probe_ops_private_section(probe_parts),
      "ctx_HasProbes": bool(probe_parts),
      "ctx_StaticAssertLit": compile_diag_c_utf8_literal(
        compile_diag_protocol_unsatisfied(protocol_name),
      ),
    },
    apply_allman=True,
  )
  return [ln for ln in text.splitlines() if ln.strip()]


def _sfinae_probe_for_method(
  dunder: str,
  ret_cpp: str,
  *,
  member_specs: list[ProtocolMemberConstraint] | None = None,
  reject_pybool_only: bool = False,
) -> str | None:
  return (
    _sfinae_complex_probe(dunder, ret_cpp)
    or _sfinae_cast_probe(dunder, ret_cpp)
    or _sfinae_abs_probe(dunder, ret_cpp)
    or _sfinae_unary_operator_probe(dunder, ret_cpp)
    or _sfinae_operator_probe(
      dunder, ret_cpp, reject_pybool_only=reject_pybool_only,
    )
    or _sfinae_unary_global_probe(
      dunder, ret_cpp, member_specs=member_specs,
    )
    or _sfinae_binary_global_probe(
      dunder, ret_cpp, member_specs=member_specs,
    )
    or _sfinae_member_call_probe(dunder, ret_cpp)
  )


def _sfinae_type_alias_member_probe(name: str) -> str:
  return f"(void)sizeof(typename U::{name})"


def _sfinae_protocol_member_probe(spec: ProtocolMemberConstraint, ret_cpp: str) -> str | None:
  if spec.kind == "type_alias":
    return _sfinae_type_alias_member_probe(spec.name)
  if spec.kind == "field":
    expr = f"std::declval<const U&>().{spec.name}"
    if ret_cpp:
      return _ret_type_check(expr, ret_cpp)
    return f"(void)({expr})"
  if spec.kind == "property":
    expr = f"std::declval<U&>().{spec.name}__get()"
    if ret_cpp:
      return _ret_type_check(expr, ret_cpp)
    return f"(void)({expr})"
  return None


def protocol_traits_lines(
  protocol_name: str,
  method_specs: list[ProtocolMethodSpec],
  *,
  protocol_type_params: list[str] | None = None,
  member_specs: list[tuple[ProtocolMemberConstraint, str]] | None = None,
  static_method_specs: list[ProtocolStaticMethodSpec] | None = None,
) -> list[str]:
  if protocol_type_params:
    return _protocol_traits_lines_parametric(
      protocol_name,
      method_specs,
      protocol_type_params=protocol_type_params,
      member_specs=member_specs,
      static_method_specs=static_method_specs,
    )
  probe_parts = _collect_probe_parts(
    protocol_name,
    method_specs,
    static_method_specs=static_method_specs,
    member_specs=member_specs,
  )
  text = expand_template(
    "~protocol_traits.inl",
    {
      "ctx_ProtocolName": protocol_name,
      "ctx_ProbePrivate": _probe_ops_private_section(probe_parts),
      "ctx_HasProbes": bool(probe_parts),
      "ctx_StaticAssertLit": compile_diag_c_utf8_literal(
        compile_diag_protocol_unsatisfied(protocol_name),
      ),
    },
    apply_allman=True,
  )
  return [ln for ln in text.splitlines() if ln.strip()]
