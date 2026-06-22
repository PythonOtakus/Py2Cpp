"""``def f[*Args](*args: Args)`` 调用与 ``for x in args`` 递归展开（MSVC：命名空间级 struct）。"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from typing import TYPE_CHECKING

from ..analysis.ir import cpp_param
from ..analysis.type_emit import scope_storage_cpp, bind_scope_var
from .vararg_emit import _VarargSegment, _starred_arg_indices

if TYPE_CHECKING:
  from ..analysis.variadic_template import VariadicTemplateInfo
  from ..translator import Translator

_PYTUPLE_PREFIX = "PyTuple"
_VT_LOOP_CALL = "__call__"


def current_variadic_template(tr: "Translator") -> "VariadicTemplateInfo | None":
  method = tr.current_method
  if method is None:
    return None
  if tr.class_info is not None:
    sig = tr.class_info.method_sig_for(method)
    return sig.variadic_template if sig is not None else None
  mp = tr._active_module_path()
  fsig = tr.function_sigs.get((mp, method.name))
  if fsig is not None:
    return fsig.variadic_template
  return None


def _variadic_template_for_call(
  tr: "Translator",
  func: ast.expr,
  *,
  call: ast.Call | None = None,
) -> "VariadicTemplateInfo | None":
  from ..emit.call_emit import class_info_from_receiver

  match func:
    case ast.Attribute(value=val, attr=method):
      info = class_info_from_receiver(tr, val)
      if info is not None and (
        method in info.methods or method in info.method_overloads
      ):
        method_def = tr._method_def_for_call(info, method, call)
        if method_def is None:
          return None
        sig = info.method_sig_for(method_def)
        return sig.variadic_template if sig is not None else None
    case ast.Name(id=name):
      if tr.class_info and (
        name in tr.class_info.methods
        or name in tr.class_info.method_overloads
      ):
        method_def = tr._method_def_for_call(tr.class_info, name, call)
        if method_def is None:
          return None
        sig = tr.class_info.method_sig_for(method_def)
        return sig.variadic_template if sig is not None else None
      mp = tr._active_module_path()
      fsig = tr.function_sigs.get((mp, name))
      return fsig.variadic_template if fsig is not None else None
    case _:
      return None


def fixed_param_count_vt(
  param_names: list[str] | None,
  vt: "VariadicTemplateInfo | None",
) -> int:
  if not param_names:
    return 0
  if vt is None:
    return len(param_names)
  return len(param_names) - 1


def _classify_starred_vt(
  tr: "Translator",
  starred: ast.Starred,
) -> _VarargSegment:
  if not isinstance(starred.value, ast.Name):
    raise NotImplementedError("* 展开仅支持简单变量名")
  current = current_variadic_template(tr)
  if current is not None and starred.value.id == current.param_name:
    return _VarargSegment("forward", starred.value)
  return _VarargSegment("spread", starred.value)


def _parse_vt_call_parts(
  tr: "Translator",
  node: ast.Call,
  *,
  num_fixed: int,
  param_cpp_types: list[str] | None,
) -> tuple[list[str], list[_VarargSegment]]:
  fixed_parts: list[str] = []
  segments: list[_VarargSegment] = []
  for i, arg in enumerate(node.args):
    if isinstance(arg, ast.Starred):
      if i < num_fixed:
        raise NotImplementedError("定参位置不能使用 * 展开")
      segments.append(_classify_starred_vt(tr, arg))
      continue
    if len(fixed_parts) < num_fixed:
      if param_cpp_types and i < len(param_cpp_types) and param_cpp_types[i]:
        fixed_parts.append(
          tr._visit_value_for_type(arg, param_cpp_types[i]),
        )
      else:
        fixed_parts.append(tr._visit_value_expr(arg))
    else:
      segments.append(_VarargSegment("scalar", arg))
  return fixed_parts, segments


def _pytuple_pack_name_from_cpp_type(cpp_type: str) -> str | None:
  """``PyTuple<Ts...>`` → ``Ts``；定长 ``PyTuple<int, int>`` → ``None``。"""
  if not cpp_type.startswith(_PYTUPLE_PREFIX + "<") or not cpp_type.endswith(">"):
    return None
  inner = cpp_type[len(_PYTUPLE_PREFIX) + 1 : -1].strip()
  if inner.endswith("..."):
    pack = inner[:-3].strip()
    return pack if pack and "," not in pack else None
  return None


def _cpp_tuple_arity(cpp_type: str) -> int | None:
  if _pytuple_pack_name_from_cpp_type(cpp_type) is not None:
    return None
  if not cpp_type.startswith(_PYTUPLE_PREFIX + "<") or not cpp_type.endswith(">"):
    return None
  inner = cpp_type[len(_PYTUPLE_PREFIX) + 1 : -1].strip()
  if not inner:
    return 0
  depth = 0
  commas = 0
  for ch in inner:
    if ch == "<":
      depth += 1
    elif ch == ">":
      depth -= 1
    elif ch == "," and depth == 0:
      commas += 1
  return commas + 1


def _spread_tuple_as_pack_forward(
  tr: "Translator",
  node: ast.expr,
  vt: "VariadicTemplateInfo",
) -> str | None:
  """``*t`` 且 ``t: (*Ts,)`` 与当前形参包同构 → 转发 ``args...``。"""
  if not isinstance(node, ast.Name):
    return None
  cpp_type = ""
  if tr.scope:
    cpp_type = scope_storage_cpp(tr, node.id)
  if not cpp_type:
    cpp_type = tr._infer_expr_cpp_type(node)
  pack = _pytuple_pack_name_from_cpp_type(cpp_type)
  if pack is not None and pack == vt.pack_name:
    return f"{cpp_param(vt.param_name)}..."
  return None


def _emit_spread_tuple_elements(
  tr: "Translator",
  node: ast.expr,
  *,
  vt: "VariadicTemplateInfo | None" = None,
) -> list[str]:
  if not isinstance(node, ast.Name):
    raise NotImplementedError("可变参数包 * 展开仅支持变量名")
  if vt is not None:
    fwd = _spread_tuple_as_pack_forward(tr, node, vt)
    if fwd is not None:
      return [fwd]
  tup = tr._visit_value_expr(node)
  arity: int | None = None
  if tr.scope:
    arity = _cpp_tuple_arity(scope_storage_cpp(tr, node.id))
  if arity is None:
    arity = _cpp_tuple_arity(tr._infer_expr_cpp_type(node))
  if arity is None:
    raise NotImplementedError(
      "可变参数包 * 展开须为编译期已知元数的 PyTuple 变量",
    )
  return [f"{tup}.__getitem__({i})" for i in range(arity)]


def emit_call_args_variadic_template(
  tr: "Translator",
  node: ast.Call,
  *,
  param_cpp_types: list[str] | None,
  param_names: list[str] | None,
  vt: "VariadicTemplateInfo",
) -> str:
  num_fixed = fixed_param_count_vt(param_names, vt)
  fixed_parts, segments = _parse_vt_call_parts(
    tr, node, num_fixed=num_fixed, param_cpp_types=param_cpp_types,
  )
  out = list(fixed_parts)
  for seg in segments:
    if seg.kind == "scalar":
      out.append(tr._visit_value_expr(seg.node))
    elif seg.kind == "forward":
      out.append(f"{cpp_param(seg.node.id)}...")
    else:
      out.extend(_emit_spread_tuple_elements(tr, seg.node, vt=vt))
  return ", ".join(out)


def _for_body_has_break_continue(stmts: list[ast.stmt]) -> bool:
  for child in ast.walk(ast.Module(body=stmts, type_ignores=[])):
    if isinstance(child, (ast.Break, ast.Continue)):
      return True
  return False


def _is_pack_for_node(node: ast.For, vt: "VariadicTemplateInfo") -> bool:
  return (
    isinstance(node.target, ast.Name)
    and isinstance(node.iter, ast.Name)
    and node.iter.id == vt.param_name
  )


def _loop_helper_base(tr: "Translator") -> str:
  from ..analysis.patterns import py2cpp_emit_symbol

  fn = tr.current_method
  if fn is None:
    return py2cpp_emit_symbol("vt_loop")
  safe = "".join(c if c.isalnum() else "_" for c in fn.name)
  return py2cpp_emit_symbol("vt_loop", safe)


def _loop_struct_name(tr: "Translator", node: ast.For) -> str:
  return f"{_loop_helper_base(tr)}_L{node.lineno}"


def _loop_outer_names(body: list[ast.stmt], loop_var: str, locals: dict[str, str]) -> list[str]:
  names: set[str] = set()
  for child in ast.walk(ast.Module(body=body, type_ignores=[])):
    if not isinstance(child, ast.Name):
      continue
    if not isinstance(child.ctx, (ast.Load, ast.Store, ast.Del)):
      continue
    if child.id == loop_var:
      continue
    if child.id in locals:
      names.add(child.id)
  return sorted(names)


def _outer_ref_decls(names: list[str], locals: dict[str, str]) -> str:
  parts: list[str] = []
  for name in names:
    t = locals.get(name, "")
    if not t:
      raise NotImplementedError(
        f"``for x in args`` 循环体引用 ``{name}`` 须有可推断的 C++ 类型",
      )
    parts.append(f"{t}& {cpp_param(name)}")
  return ", ".join(parts)


def _locals_before_for(
  tr: "Translator",
  func: ast.FunctionDef,
  for_node: ast.For,
  *,
  param_types: dict[str, str],
) -> dict[str, str]:
  """函数体内、``for`` 之前的局部名 → C++ 类型（供 peel struct 捕获）。"""
  from ..analysis.ir import cpp_ident

  locals: dict[str, str] = dict(param_types)
  for stmt in func.body:
    if stmt is for_node:
      break
    match stmt:
      case ast.AnnAssign(target=ast.Name(id=name), annotation=ann):
        locals[name] = tr._parse_type(ann, tr._active_type_params()).strip()
      case ast.Assign(targets=targets, value=value):
        for tgt in targets:
          if isinstance(tgt, ast.Name):
            t = tr._infer_expr_cpp_type(value)
            if t:
              locals[tgt.id] = t
      case ast.AugAssign(target=ast.Name(id=name)):
        pass
      case _:
        pass
  pyint = cpp_ident("int")
  for name, t in list(locals.items()):
    if t in ("int", pyint):
      locals[name] = pyint
  return locals


@contextmanager
def _capture_lines(tr: "Translator"):
  saved = tr.source_lines
  saved_level = tr.indent_level
  tr.source_lines = []
  try:
    yield tr.source_lines
  finally:
    tr.source_lines = saved
    tr.indent_level = saved_level


def _emit_vt_loop_struct(
  tr: "Translator",
  func: ast.FunctionDef,
  node: ast.For,
  vt: "VariadicTemplateInfo",
  *,
  param_types: dict[str, str],
) -> str:
  """命名空间级 struct（C++11 / MSVC 可编译）。"""
  if node.orelse:
    raise NotImplementedError("``for x in args`` 不支持 for-else")
  if _for_body_has_break_continue(node.body):
    raise NotImplementedError(
      "``for x in args`` 循环体内不支持 break/continue",
    )
  x_name = node.target.id
  pack = vt.pack_name
  struct_name = _loop_struct_name(tr, node)
  locals = _locals_before_for(tr, func, node, param_types=param_types)
  outer = _loop_outer_names(node.body, x_name, locals)
  outer_decls = _outer_ref_decls(outer, locals)
  outer_args = ", ".join(cpp_param(n) for n in outer)
  step_lead = f"{outer_decls}, " if outer_decls else ""
  tr.write_line(f"struct {struct_name} {{")
  tr.indent_level += 1
  tr.write_line(f"template<typename {pack}Head>")
  tr.write_line(f"static void step({step_lead}{pack}Head head) {{")
  tr.indent_level += 1
  tr.write_line(f"{pack}Head {x_name} = head;")
  with _capture_lines(tr) as buf:
    if tr.scope is not None:
      from ..translator import NameContext

      tr.scope.vars[x_name] = NameContext.Variable
      bind_scope_var(tr.scope, x_name, f"{pack}Head", classes=tr.classes)
      for name in outer:
        tr.scope.vars[name] = NameContext.Variable
        bind_scope_var(tr.scope, name, locals[name], classes=tr.classes)
    tr._emit_body(node.body)
  for line in buf:
    tr.source_lines.append(line if line else "")
  tr.indent_level -= 1
  tr.write_line("}")
  call_lead = f"{outer_decls}, " if outer_decls else ""
  tr.write_line(f"template<typename {pack}Head, typename... {pack}Tail>")
  tr.write_line(
    f"static void {_VT_LOOP_CALL}({call_lead}{pack}Head head, {pack}Tail... tail) {{",
  )
  tr.indent_level += 1
  step_call = f"step({outer_args}, head)" if outer_args else "step(head)"
  tr.write_line(f"{step_call};")
  call_recurse = (
    f"{_VT_LOOP_CALL}({outer_args}, tail...)"
    if outer_args
    else f"{_VT_LOOP_CALL}(tail...)"
  )
  tr.write_line(f"{call_recurse};")
  tr.indent_level -= 1
  tr.write_line("}")
  tr.write_line(f"template<typename... {pack}Tail>")
  tr.write_line(f"static void {_VT_LOOP_CALL}({call_lead}{pack}Tail... tail) {{")
  tr.indent_level += 1
  tr.write_line("(void)sizeof...(tail);")
  tr.indent_level -= 1
  tr.write_line("}")
  tr.indent_level -= 1
  tr.write_line("};")
  tr.write_line()
  return struct_name


def prescan_emit_vt_loop_structs(
  tr: "Translator",
  func: ast.FunctionDef,
  vt: "VariadicTemplateInfo",
  *,
  param_types: dict[str, str],
) -> None:
  """在函数体 ``{`` 之前生成 ``for x in args`` 所需的 peel struct。"""
  emitted: set[str] = set()
  for node in func.body:
    if not isinstance(node, ast.For) or not _is_pack_for_node(node, vt):
      continue
    struct_name = _loop_struct_name(tr, node)
    if struct_name in emitted:
      continue
    emitted.add(struct_name)
    saved_method = tr.current_method
    saved_vars = dict(tr.scope.vars) if tr.scope else None
    from ..analysis.type_emit import snapshot_scope_type_bindings, restore_scope_type_bindings
    saved_types = snapshot_scope_type_bindings(tr.scope) if tr.scope else None
    tr.current_method = func
    try:
      _emit_vt_loop_struct(
        tr, func, node, vt, param_types=param_types,
      )
    finally:
      tr.current_method = saved_method
      if tr.scope is not None and saved_vars is not None:
        tr.scope.vars = saved_vars
      if tr.scope is not None and saved_types is not None:
        restore_scope_type_bindings(tr.scope, saved_types)


def try_emit_vt_pack_to_tuple_ann_assign(tr: "Translator", node: ast.AnnAssign) -> bool:
  """``t: (*Ts,) = args`` → ``PyTuple<Ts...> t(args...);``（形参包按包构造元组）。"""
  from ..analysis.ir import cpp_param
  from ..analysis.variadic_template import (
    cpp_typevar_tuple_as_pytuple,
    typevar_tuple_pack_from_type_node,
  )

  if node.annotation is None or node.value is None:
    return False
  if not isinstance(node.target, ast.Name) or not isinstance(node.value, ast.Name):
    return False
  vt = current_variadic_template(tr)
  if vt is None or node.value.id != vt.param_name:
    return False
  tvt_names = tr._active_typevar_tuple_names()
  pack = typevar_tuple_pack_from_type_node(node.annotation, tvt_names)
  if pack is None or pack != vt.pack_name:
    return False
  t = cpp_typevar_tuple_as_pytuple(pack)
  name = node.target.id
  pname = cpp_param(name)
  pack_actual = cpp_param(vt.param_name)
  if tr._try_declare(name):
    if tr.scope:
      bind_scope_var(tr.scope, name, t, classes=tr.classes)
    tr.write_line(f"{t} {pname}({pack_actual}...);")
  else:
    tr.write_line(f"{pname} = {t}({pack_actual}...);")
    if tr.scope:
      bind_scope_var(tr.scope, name, t, classes=tr.classes)
  return True


def try_emit_variadic_pack_len(tr: "Translator", arg: ast.expr) -> str | None:
  """``len(args)``（当前函数 ``*args`` 为 TypeVarTuple 形参包）→ ``(int)sizeof...(args)``。"""
  vt = current_variadic_template(tr)
  if vt is None or not isinstance(arg, ast.Name) or arg.id != vt.param_name:
    return None
  pack_cpp = cpp_param(vt.param_name)
  return f"(int)sizeof...({pack_cpp})"


def try_emit_variadic_pack_for(tr: "Translator", node: ast.For) -> bool:
  vt = current_variadic_template(tr)
  if vt is None or not _is_pack_for_node(node, vt):
    return False
  if not isinstance(node.target, ast.Name):
    raise NotImplementedError(
      "``for x in args``（可变参数包）循环变量须为简单名字",
    )
  struct_name = _loop_struct_name(tr, node)
  pack_cpp = cpp_param(vt.param_name)
  fn = tr.current_method
  if fn is None:
    raise NotImplementedError("``for x in args`` 须在函数体内")
  param_types: dict[str, str] = {}
  if tr.scope is not None:
    from ..analysis.type_emit import scope_all_storage_bindings
    param_types = scope_all_storage_bindings(tr.scope)
  outer = _loop_outer_names(
    node.body,
    node.target.id,
    _locals_before_for(tr, fn, node, param_types=param_types),
  )
  outer_args = ", ".join(cpp_param(n) for n in outer)
  call_lead = f"{outer_args}, " if outer_args else ""
  tr.write_line(f"{struct_name}::{_VT_LOOP_CALL}({call_lead}{pack_cpp}...);")
  return True
