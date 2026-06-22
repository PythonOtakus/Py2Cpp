"""列表/字典字面量（含 ``*`` 解包）与推导式（``[... for ...]`` / ``{... for ...}``）代码生成。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Callable

from ..analysis.ir import (
  cpp_result_type,
  iter_result_done_cpp,
  iter_result_value_cpp,
)
from .loops_emit import (
  _cpp_native_for_range_header,
  _index_for_loop_plan,
  _iterator_ctor_type,
  element_type_of_iterable,
  emit_index_enumerate_for_from_iter,
  emit_index_for_from_iter,
  emit_native_range_loop_from_call,
  index_for_getitem_at,
  is_direct_range_call,
)

from ..analysis.patterns import temp_name as _temp_name
from ..analysis.type_emit import bind_scope_var

if TYPE_CHECKING:
  from ..translator import Translator


def _bind_comp_target_scope(tr: Translator, name: str, elem_t: str) -> None:
  if not tr.scope:
    return
  from ..translator import NameContext

  bind_scope_var(tr.scope, name, elem_t, classes=tr.classes)
  tr.scope.vars[name] = NameContext.Variable


def append_for_comprehension_target(
  tr: Translator,
  stmts: list[str],
  target: ast.expr,
  iter_expr: ast.expr,
  inner: list[str],
) -> str:
  """``for target in iter: inner`` → 追加 C++ 循环语句；返回绑定名元素类型。"""
  if not isinstance(target, ast.Name):
    raise NotImplementedError("推导式 for 目标仅支持简单变量名，如 ``for x in ...``")
  name = target.id
  if is_direct_range_call(iter_expr):
    from ..analysis.ir import cpp_ident

    match iter_expr.args:
      case [stop]:
        start_s, stop_s, step_s = "0", tr.visit(stop), "1"
      case [start, stop]:
        start_s, stop_s, step_s = tr.visit(start), tr.visit(stop), "1"
      case [start, stop, step]:
        start_s, stop_s, step_s = (
          tr.visit(start),
          tr.visit(stop),
          tr.visit(step),
        )
      case _:
        raise NotImplementedError("range 仅支持 1～3 个位置参数")
    header = _cpp_native_for_range_header(name, start_s, stop_s, step_s)
    stmts.append(f"{header} {{ {' '.join(inner)} }}")
    elem_t = cpp_ident("int")
    _bind_comp_target_scope(tr, name, elem_t)
    return elem_t
  plan = _index_for_loop_plan(tr, iter_expr)
  if plan is not None:
    iter_cpp, iter_ty, elem_t, reversed_loop = plan
    fi = _temp_name("fi")
    if reversed_loop:
      header = (
        f"for (PyInt {fi} = {iter_cpp}.__len__() - 1; "
        f"{fi} >= 0; {fi} -= 1)"
      )
      at = f"({iter_cpp}.__len__() - 1 - {fi})"
    else:
      header = f"for (PyInt {fi} = 0; {fi} < {iter_cpp}.__len__(); {fi} += 1)"
      at = fi
    getitem = index_for_getitem_at(iter_cpp, iter_ty, at)
    stmts.append(
      f"{header} {{ {elem_t} {name} = {getitem}; {' '.join(inner)} }}"
    )
    _bind_comp_target_scope(tr, name, elem_t)
    return elem_t
  elem_t = element_type_of_iterable(tr, iter_expr) or "auto"
  iter_cpp = tr.visit(iter_expr)
  it = _temp_name("it")
  res = _temp_name("r")
  value_t = elem_t if elem_t != "auto" else "auto"
  sep = tr._member_access(iter_cpp)
  if elem_t != "auto":
    stmts.append(f"{_iterator_ctor_type(tr, iter_expr, elem_t)} {it}(&{iter_cpp});")
    loop = (
      f"while (true) {{ "
      f"{cpp_result_type(elem_t)} {res} = {it}.__next__(); "
      f"if ({iter_result_done_cpp(res)}) break; "
      f"{value_t} {name} = {iter_result_value_cpp(res)}; "
      f"{' '.join(inner)} "
      f"}}"
    )
  else:
    stmts.append(f"auto& {it} = {iter_cpp}{sep}__iter__();")
    loop = (
      f"while (true) {{ "
      f"auto {res} = {it}.__next__(); "
      f"if ({iter_result_done_cpp(res)}) break; "
      f"auto {name} = {iter_result_value_cpp(res)}; "
      f"{' '.join(inner)} "
      f"}}"
    )
  stmts.append(loop)
  _bind_comp_target_scope(tr, name, value_t)
  return value_t


def append_comprehension_generators(
  tr: Translator,
  stmts: list[str],
  generators: list[ast.comprehension],
  inner: Callable[[], list[str]],
) -> None:
  if any(getattr(g, "is_async", False) for g in generators):
    raise NotImplementedError("异步推导式（``async for``）尚未支持")

  def build_body(depth: int) -> list[str]:
    if depth >= len(generators):
      return inner()
    gen = generators[depth]
    body = build_body(depth + 1)
    if gen.ifs:
      for if_expr in reversed(gen.ifs):
        body = [f"if ({tr.visit(if_expr)}) {{ {' '.join(body)} }}"]
    loop_stmts: list[str] = []
    append_for_comprehension_target(tr, loop_stmts, gen.target, gen.iter, body)
    return loop_stmts

  stmts.extend(build_body(0))


def append_generator_exp_loops(
  tr: Translator,
  stmts: list[str],
  genexp: ast.GeneratorExp,
  inner: Callable[[], list[str]],
) -> None:
  """将 ``GeneratorExp`` 的 ``generators`` 展开为嵌套 ``for``（无临时容器）。"""
  append_comprehension_generators(tr, stmts, genexp.generators, inner)


def infer_generator_exp_elem_type(tr: Translator, genexp: ast.GeneratorExp) -> str:
  if not tr.scope:
    return tr._infer_expr_cpp_type(genexp.elt) or "auto"
  from ..translator import NameContext

  saved_types = dict(tr.scope.var_types)
  saved_vars = dict(tr.scope.vars)
  try:
    for gen in genexp.generators:
      if not isinstance(gen.target, ast.Name):
        raise NotImplementedError("生成器表达式 for 目标仅支持简单变量名")
      et = element_type_of_iterable(tr, gen.iter) or "auto"
      bind_scope_var(tr.scope, gen.target.id, et, classes=tr.classes)
      tr.scope.vars[gen.target.id] = NameContext.Variable
    t = tr._infer_expr_cpp_type(genexp.elt)
    return t or "auto"
  finally:
    tr.scope.var_types.clear()
    tr.scope.var_types.update(saved_types)
    tr.scope.vars.clear()
    tr.scope.vars.update(saved_vars)


def emit_for_comprehension_target(
  tr: Translator,
  target: ast.expr,
  iter_expr: ast.expr,
  body: Callable[[], None],
) -> None:
  """``for target in iter: body()``；``for i in range(...)`` 直译为 C++ 原生 ``for``。"""
  if (
    isinstance(iter_expr, ast.Call)
    and isinstance(iter_expr.func, ast.Name)
    and iter_expr.func.id == "enumerate"
    and emit_index_enumerate_for_from_iter(tr, target, iter_expr, body)
  ):
    return
  if not isinstance(target, ast.Name):
    raise NotImplementedError("推导式 for 目标仅支持简单变量名，如 ``for x in ...``")
  name = target.id
  if is_direct_range_call(iter_expr):
    emit_native_range_loop_from_call(tr, name, iter_expr, body)
    return
  if emit_index_for_from_iter(tr, target, iter_expr, body):
    return
  elem_t = element_type_of_iterable(tr, iter_expr)
  iter_cpp = tr.visit(iter_expr)
  it = _temp_name("it")
  sep = tr._member_access(iter_cpp)
  tr.write_line(f"auto& {it} = {iter_cpp}{sep}__iter__();")
  res = _temp_name("r")
  value_t = elem_t or "auto"
  with tr._use_block("while (true)"):
    tr.write_line(f"auto {res} = {it}.__next__();")
    tr.write_line(f"if ({iter_result_done_cpp(res)}) break;")
    if elem_t:
      tr.write_line(f"{elem_t} {name} = {iter_result_value_cpp(res)};")
    else:
      tr.write_line(f"auto {name} = {iter_result_value_cpp(res)};")
    _bind_comp_target_scope(tr, name, value_t)
    body()


def emit_comprehension_generators(
  tr: Translator,
  generators: list[ast.comprehension],
  body: Callable[[], None],
) -> None:
  if any(getattr(g, "is_async", False) for g in generators):
    raise NotImplementedError("异步推导式（``async for``）尚未支持")

  def emit_level(depth: int) -> None:
    if depth >= len(generators):
      body()
      return
    gen = generators[depth]

    def after_bind() -> None:
      if gen.ifs:
        for if_expr in gen.ifs:
          with tr._use_block(f"if ({tr.visit(if_expr)})"):
            emit_level(depth + 1)
      else:
        emit_level(depth + 1)

    emit_for_comprehension_target(tr, gen.target, gen.iter, after_bind)

  emit_level(0)


def emit_starred_extend(
  tr: Translator,
  *,
  list_name: str,
  elem_t: str,
  starred: ast.expr,
) -> None:
  """``*iterable``：按 CPython 3.13 将可迭代对象元素依次 ``append``。"""
  loop_var = _temp_name("x")

  def append_body() -> None:
    from ..analysis.ir import cpp_param

    tr.write_line(f"{cpp_param(list_name)}.append({loop_var});")

  fake = ast.comprehension(
    target=ast.Name(id=loop_var, ctx=ast.Store()),
    iter=starred,
    ifs=[],
    is_async=False,
  )
  emit_for_comprehension_target(tr, fake.target, fake.iter, append_body)


def emit_sequence_literal(
  tr: Translator,
  *,
  cpp_spec: str,
  name: str,
  elem_t: str,
  elts: list[ast.expr],
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param
  from ..emit.literal_ctor_emit import (
    _declare_addable_var,
    _emit_list_literal_init,
  )

  _declare_addable_var(tr, cpp_spec, name, elem_t, declare=declare)
  pname = cpp_param(name)
  for elt in elts:
    if isinstance(elt, ast.Starred):
      emit_starred_extend(tr, list_name=name, elem_t=elem_t, starred=elt.value)
    elif isinstance(elt, ast.List):
      tmp: str = _temp_name("nest_lit")
      inner_et: str = tr._infer_list_elem_type(elt.elts)
      _emit_list_literal_init(tr, tmp, inner_et, elt.elts, declare=True)
      tr.write_line(f"{pname}.append({cpp_param(tmp)});")
    else:
      tr.write_line(f"{pname}.append({tr.visit(elt)});")


def emit_list_comprehension(
  tr: Translator,
  *,
  name: str,
  cpp_spec: str,
  elem_t: str,
  comp: ast.ListComp,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param
  from ..emit.literal_ctor_emit import _declare_addable_var

  _declare_addable_var(tr, cpp_spec, name, elem_t, declare=declare)
  pname = cpp_param(name)

  def append_elt() -> None:
    tr.write_line(f"{pname}.append({tr.visit(comp.elt)});")

  emit_comprehension_generators(tr, comp.generators, append_elt)


def emit_dict_literal(
  tr: Translator,
  *,
  name: str,
  cpp_spec: str,
  node: ast.Dict,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param
  from ..emit.literal_ctor_emit import _declare_mapping_var

  _declare_mapping_var(tr, name, cpp_spec, declare=declare)
  pname = cpp_param(name)
  keys = node.keys or []
  values = node.values or []
  for key, val in zip(keys, values):
    if key is None:
      tr.write_line(f"{pname}.update({tr.visit(val)});")
    else:
      tr.write_line(
        f"{pname}.__setitem__({tr.visit(key)}, {tr._visit_value_expr(val)});"
      )


def emit_dict_comprehension(
  tr: Translator,
  *,
  name: str,
  cpp_spec: str,
  comp: ast.DictComp,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param
  from ..emit.literal_ctor_emit import _declare_mapping_var

  _declare_mapping_var(tr, name, cpp_spec, declare=declare)
  pname = cpp_param(name)

  def set_item() -> None:
    tr.write_line(
      f"{pname}.__setitem__({tr.visit(comp.key)}, {tr._visit_value_expr(comp.value)});"
    )

  emit_comprehension_generators(tr, comp.generators, set_item)


def emit_set_literal(
  tr: Translator,
  *,
  name: str,
  cpp_spec: str,
  elem_t: str,
  node: ast.Set,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param
  from ..emit.literal_ctor_emit import _declare_addable_var

  _declare_addable_var(tr, cpp_spec, name, elem_t, declare=declare)
  pname = cpp_param(name)
  for elt in node.elts:
    tr.write_line(f"{pname}.add({tr.visit(elt)});")


def emit_frozenset_literal(
  tr: Translator,
  *,
  name: str,
  elem_t: str,
  node: ast.Set,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param, cpp_template_type

  tmp = _temp_name("fs_lit")
  set_spec = cpp_template_type("set", elem_t)
  emit_set_literal(
    tr, name=tmp, cpp_spec=set_spec, elem_t=elem_t, node=node, declare=True,
  )
  spec = cpp_template_type("frozenset", elem_t)
  pname = cpp_param(name)
  if declare:
    if tr.scope:
      bind_scope_var(tr.scope, name, spec, classes=tr.classes)
      from ..translator import NameContext

      tr.scope.vars[name] = NameContext.Variable
    tr.write_line(f"{spec} {pname};")
  else:
    tr.write_line(f"{pname} = {spec}();")
  tr.write_line(f"{pname}.init_from_set({cpp_param(tmp)});")


def emit_frozenlist_literal(
  tr: Translator,
  *,
  name: str,
  elem_t: str,
  elts: list[ast.expr],
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param, cpp_template_type

  tmp = _temp_name("fl_lit")
  emit_sequence_literal(
    tr,
    cpp_spec=cpp_template_type("list", elem_t),
    name=tmp,
    elem_t=elem_t,
    elts=elts,
    declare=True,
  )
  spec = cpp_template_type("frozenlist", elem_t)
  pname = cpp_param(name)
  if declare:
    if tr.scope:
      bind_scope_var(tr.scope, name, spec, classes=tr.classes)
      from ..translator import NameContext

      tr.scope.vars[name] = NameContext.Variable
    tr.write_line(f"{spec} {pname};")
  else:
    tr.write_line(f"{pname} = {spec}();")
  tr.write_line(f"{pname}.init_from_list({cpp_param(tmp)});")


def emit_frozendict_literal(
  tr: Translator,
  *,
  name: str,
  inner: str,
  node: ast.Dict,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param, cpp_template_type

  tmp = _temp_name("fd_lit")
  emit_dict_literal(
    tr,
    name=tmp,
    cpp_spec=cpp_template_type("dict", inner),
    node=node,
    declare=True,
  )
  spec = cpp_template_type("frozendict", inner)
  pname = cpp_param(name)
  if declare:
    if tr.scope:
      bind_scope_var(tr.scope, name, spec, classes=tr.classes)
      from ..translator import NameContext

      tr.scope.vars[name] = NameContext.Variable
    tr.write_line(f"{spec} {pname};")
  else:
    tr.write_line(f"{pname} = {spec}();")
  tr.write_line(f"{pname}.init_from_dict({cpp_param(tmp)});")


def emit_set_comprehension(
  tr: Translator,
  *,
  name: str,
  cpp_spec: str,
  elem_t: str,
  comp: ast.SetComp,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param
  from ..emit.literal_ctor_emit import _declare_addable_var

  _declare_addable_var(tr, cpp_spec, name, elem_t, declare=declare)
  pname = cpp_param(name)

  def add_elt() -> None:
    tr.write_line(f"{pname}.add({tr.visit(comp.elt)});")

  emit_comprehension_generators(tr, comp.generators, add_elt)


def emit_frozenlist_comprehension(
  tr: Translator,
  *,
  name: str,
  elem_t: str,
  comp: ast.ListComp,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param, cpp_template_type

  tmp = _temp_name("fl_comp")
  emit_list_comprehension(
    tr,
    name=tmp,
    cpp_spec=cpp_template_type("list", elem_t),
    elem_t=elem_t,
    comp=comp,
    declare=True,
  )
  spec = cpp_template_type("frozenlist", elem_t)
  pname = cpp_param(name)
  if declare:
    if tr.scope:
      bind_scope_var(tr.scope, name, spec, classes=tr.classes)
      from ..translator import NameContext

      tr.scope.vars[name] = NameContext.Variable
    tr.write_line(f"{spec} {pname};")
  else:
    tr.write_line(f"{pname} = {spec}();")
  tr.write_line(f"{pname}.init_from_list({cpp_param(tmp)});")


def emit_frozenset_comprehension(
  tr: Translator,
  *,
  name: str,
  elem_t: str,
  comp: ast.SetComp,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param, cpp_template_type

  tmp = _temp_name("fs_comp")
  emit_set_comprehension(
    tr,
    name=tmp,
    cpp_spec=cpp_template_type("set", elem_t),
    elem_t=elem_t,
    comp=comp,
    declare=True,
  )
  spec = cpp_template_type("frozenset", elem_t)
  pname = cpp_param(name)
  if declare:
    if tr.scope:
      bind_scope_var(tr.scope, name, spec, classes=tr.classes)
      from ..translator import NameContext

      tr.scope.vars[name] = NameContext.Variable
    tr.write_line(f"{spec} {pname};")
  else:
    tr.write_line(f"{pname} = {spec}();")
  tr.write_line(f"{pname}.init_from_set({cpp_param(tmp)});")


def emit_frozendict_comprehension(
  tr: Translator,
  *,
  name: str,
  inner: str,
  comp: ast.DictComp,
  declare: bool,
) -> None:
  from ..analysis.ir import cpp_param, cpp_template_type

  tmp = _temp_name("fd_comp")
  emit_dict_comprehension(
    tr,
    name=tmp,
    cpp_spec=cpp_template_type("dict", inner),
    comp=comp,
    declare=True,
  )
  spec = cpp_template_type("frozendict", inner)
  pname = cpp_param(name)
  if declare:
    if tr.scope:
      bind_scope_var(tr.scope, name, spec, classes=tr.classes)
      from ..translator import NameContext

      tr.scope.vars[name] = NameContext.Variable
    tr.write_line(f"{spec} {pname};")
  else:
    tr.write_line(f"{pname} = {spec}();")
  tr.write_line(f"{pname}.init_from_dict({cpp_param(tmp)});")
