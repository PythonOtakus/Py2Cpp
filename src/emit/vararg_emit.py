"""``*args: T[:]`` 调用侧打包（空包 ``T()``；非空与堆数组字面量相同）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import cpp_array_elem_type, cpp_ident
from .iife_emit import emit_iife

if TYPE_CHECKING:
  from ..analysis.vararg_pack import VarargPackInfo
  from ..translator import Translator


def current_vararg_pack(tr: "Translator") -> "VarargPackInfo | None":
  """当前正在生成的函数/方法上的 ``*args: T[:]`` 整包信息。"""
  method = tr.current_method
  if method is None:
    return None
  if tr.class_info is not None:
    sig = tr.class_info.method_sig_for(method)
    return sig.vararg_pack if sig is not None else None
  mp = tr._active_module_path()
  fsig = tr.function_sigs.get((mp, method.name))
  if fsig is not None:
    return fsig.vararg_pack
  return None


def emit_vararg_forward_expr(
  tr: "Translator",
  starred: ast.Starred,
  callee_pack: "VarargPackInfo",
) -> str:
  """``callee(*args)``：将本函数 ``*args: T[:]`` 整包按值转发（位置须与形参一致）。"""
  current = current_vararg_pack(tr)
  if current is None:
    raise NotImplementedError(
      "*args 转发仅能在声明了 *args: T[:] 的函数体内使用",
    )
  if not isinstance(starred.value, ast.Name):
    raise NotImplementedError("*args 转发仅支持简单变量名")
  if starred.value.id != current.param_name:
    raise NotImplementedError(
      f"*args 转发须使用本函数可变参数名 {current.param_name!r}，"
      f"不能写 *{starred.value.id!r}",
    )
  if current.cpp_type != callee_pack.cpp_type:
    raise NotImplementedError(
      f"可变参数包类型不匹配：{current.cpp_type} 与 {callee_pack.cpp_type}",
    )
  return tr._visit_value_for_type(starred.value, callee_pack.cpp_type)


def _starred_arg_indices(node: ast.Call) -> list[int]:
  return [i for i, a in enumerate(node.args) if isinstance(a, ast.Starred)]


@dataclass(frozen=True)
class _VarargSegment:
  kind: str  # "scalar" | "forward" | "spread"
  node: ast.expr


def _classify_starred_value(
  tr: "Translator",
  starred: ast.Starred,
  callee_pack: "VarargPackInfo",
) -> _VarargSegment:
  if not isinstance(starred.value, ast.Name):
    raise NotImplementedError("* 展开仅支持简单变量名")
  current = current_vararg_pack(tr)
  if current is not None and starred.value.id == current.param_name:
    if current.cpp_type != callee_pack.cpp_type:
      raise NotImplementedError(
        f"可变参数包类型不匹配：{current.cpp_type} 与 {callee_pack.cpp_type}",
      )
    return _VarargSegment("forward", starred.value)
  return _VarargSegment("spread", starred.value)


def _parse_vararg_call_parts(
  tr: "Translator",
  node: ast.Call,
  *,
  num_fixed: int,
  param_cpp_types: list[str] | None,
  vararg_pack: "VarargPackInfo",
) -> tuple[list[str], list[_VarargSegment]]:
  fixed_parts: list[str] = []
  segments: list[_VarargSegment] = []
  for i, arg in enumerate(node.args):
    if isinstance(arg, ast.Starred):
      if i < num_fixed:
        raise NotImplementedError("定参位置不能使用 * 展开")
      segments.append(_classify_starred_value(tr, arg, vararg_pack))
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


def emit_vararg_concat_expr(
  tr: "Translator",
  vararg_pack: "VarargPackInfo",
  segments: list[_VarargSegment],
) -> str:
  """将标量 + ``*pack`` 片段按序拼成单个 ``PyArray``。"""
  from ..translator import temp_name

  cpp_type = vararg_pack.cpp_type
  elem_t = vararg_pack.elem_cpp_type or ""
  pyint = cpp_ident("int")
  n_var = temp_name("n")
  off_var = temp_name("off")
  out_var = temp_name("vap")
  stmts: list[str] = [f"{pyint} {n_var} = 0;"]
  for seg in segments:
    if seg.kind == "scalar":
      stmts.append(f"{n_var} += 1;")
    else:
      arr = tr._visit_value_for_type(seg.node, cpp_type)
      stmts.append(f"{n_var} += {arr}.__len__();")
  stmts.append(f"{cpp_type} {out_var}({n_var});")
  stmts.append(f"{pyint} {off_var} = 0;")
  for seg in segments:
    if seg.kind == "scalar":
      val = (
        tr._visit_value_for_type(seg.node, elem_t)
        if elem_t
        else tr._visit_value_expr(seg.node)
      )
      stmts.append(f"{out_var}.__setitem__({off_var}, {val});")
      stmts.append(f"{off_var} += 1;")
    else:
      arr = tr._visit_value_for_type(seg.node, cpp_type)
      i_var = temp_name("i")
      stmts.append(
        f"for ({pyint} {i_var} = 0; {i_var} < {arr}.__len__(); {i_var} += 1) {{",
      )
      stmts.append(
        f"  {out_var}.__setitem__({off_var}, {arr}.__getitem__({i_var}));",
      )
      stmts.append(f"  {off_var} += 1;")
      stmts.append("}")
  stmts.append(f"return {out_var};")
  return emit_iife(cpp_type, stmts)


def _emit_vararg_pack_from_segments(
  tr: "Translator",
  vararg_pack: "VarargPackInfo",
  segments: list[_VarargSegment],
) -> str:
  if not segments:
    return f"{vararg_pack.cpp_type}()"
  if len(segments) == 1:
    seg = segments[0]
    if seg.kind == "forward":
      return emit_vararg_forward_expr(
        tr, ast.Starred(value=seg.node), vararg_pack,
      )
    if seg.kind == "spread":
      return tr._visit_value_for_type(seg.node, vararg_pack.cpp_type)
    return emit_vararg_pack_expr(
      tr,
      vararg_pack.cpp_type,
      [seg.node],
      elem_cpp_type=vararg_pack.elem_cpp_type,
    )
  return emit_vararg_concat_expr(tr, vararg_pack, segments)


def emit_call_args_with_vararg_starred(
  tr: "Translator",
  node: ast.Call,
  *,
  param_cpp_types: list[str] | None,
  param_names: list[str] | None,
  vararg_pack: "VarargPackInfo",
) -> str:
  """含 ``*name`` 的调用：定参 + 可变段（标量 / ``*T[:]`` 解包 / 本函数 ``*args`` 转发）。"""
  num_fixed = _fixed_param_count(param_names, vararg_pack)
  fixed_parts, segments = _parse_vararg_call_parts(
    tr,
    node,
    num_fixed=num_fixed,
    param_cpp_types=param_cpp_types,
    vararg_pack=vararg_pack,
  )
  pack_expr = _emit_vararg_pack_from_segments(tr, vararg_pack, segments)
  return ", ".join(fixed_parts + [pack_expr])


def emit_vararg_pack_expr(
  tr: "Translator",
  cpp_type: str,
  elts: list[ast.expr],
  *,
  elem_cpp_type: str | None = None,
) -> str:
  if not elts:
    return f"{cpp_type}()"
  from ..translator import temp_name

  elem_t = elem_cpp_type or cpp_array_elem_type(cpp_type) or ""
  n = len(elts)
  var = temp_name("vap")
  stmts = [f"{cpp_type} {var}({n});"]
  for i, elt in enumerate(elts):
    val = (
      tr._visit_value_for_type(elt, elem_t)
      if elem_t
      else tr._visit_value_expr(elt)
    )
    stmts.append(f"{var}.__setitem__({i}, {val});")
  stmts.append(f"return {var};")
  return emit_iife(cpp_type, stmts)


def _fixed_param_count(
  param_names: list[str] | None,
  vararg_pack: "VarargPackInfo | None",
) -> int:
  if not param_names:
    return 0
  if vararg_pack is None:
    return len(param_names)
  return len(param_names) - 1


def fixed_param_count(
  param_names: list[str] | None,
  vararg_pack: "VarargPackInfo | None",
) -> int:
  return _fixed_param_count(param_names, vararg_pack)


def emit_named_call_args_with_vararg(
  tr: "Translator",
  node: ast.Call,
  param_names: list[str],
  param_cpp_types: list[str],
  vararg_pack: "VarargPackInfo",
) -> str:
  num_fixed = _fixed_param_count(param_names, vararg_pack)
  if _starred_arg_indices(node):
    raise NotImplementedError(
      "关键字与可变参数混用时暂不支持位置段内的 * 展开",
    )
  bound: dict[str, str] = {}
  for i, arg in enumerate(node.args[:num_fixed]):
    if i >= len(param_names):
      raise NotImplementedError("位置参数过多")
    name = param_names[i]
    v = tr._visit_value_expr(arg)
    if i < len(param_cpp_types) and param_cpp_types[i]:
      v = tr._coerce_expr_to_cpp_type(
        v, param_cpp_types[i], rhs_node=arg,
      )
    bound[name] = v
  extra = node.args[num_fixed:]
  kw_pack: str | None = None
  for kw in node.keywords:
    if kw.arg is None:
      raise NotImplementedError("变体构造不支持 **kwargs")
    if kw.arg == vararg_pack.param_name:
      kw_pack = tr._visit_value_for_type(kw.value, vararg_pack.cpp_type)
      continue
    if kw.arg not in param_names[:num_fixed]:
      raise NotImplementedError(f"未知关键字参数: {kw.arg}")
    idx = param_names.index(kw.arg)
    if idx < len(param_cpp_types) and param_cpp_types[idx]:
      v = tr._visit_value_for_type(kw.value, param_cpp_types[idx])
    else:
      v = tr._visit_value_expr(kw.value)
    bound[kw.arg] = v
  if kw_pack is not None:
    bound[vararg_pack.param_name] = kw_pack
  else:
    bound[vararg_pack.param_name] = emit_vararg_pack_expr(
      tr,
      vararg_pack.cpp_type,
      extra,
      elem_cpp_type=vararg_pack.elem_cpp_type,
    )
  return ", ".join(bound[n] for n in param_names if n in bound)
