"""``BuildPlan`` + TypeGraph 校验（``@dataclass`` / ``list`` 首版）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..passes.build_parse import (
  BUILD_INDEX_PREFIX,
  AssignSegment,
  BuildBody,
  BuildPlan,
  BuildValue,
  ExprValue,
  IndexRefValue,
  ListDescentSegment,
  ListRootPlan,
  LiteralValue,
  StructDescentSegment,
  StructRootPlan,
)
from ..translation_error import raise_translation_error
from .ir import (
  ClassInfo,
  cpp_template_type,
  strip_cpp_ref,
)
from .type_extract import list_elem_type
from .type_pred import is_int64_type, is_int_type, is_list_type

if TYPE_CHECKING:
  from ..translator import Translator


@dataclass
class _BuildCtx:
  cpp_t: str
  info: ClassInfo | None


@dataclass
class BuildWalkResult:
  result_cpp: str


def _field_cpp_type(tr: Translator, info: ClassInfo, name: str) -> str:
  from ..analysis.type_emit import field_ann_ast, field_storage_cpp

  if name not in info.fields:
    raise_translation_error(tr, None, f"{info.name} 无字段 {name!r}")
  resolved = field_storage_cpp(info, name)
  if resolved:
    return resolved
  ann = field_ann_ast(info, name)
  if ann is not None:
    return tr._parse_type(ann, info.type_params)
  specs = getattr(info, "dataclass_field_specs", None)
  if specs:
    for spec in specs:
      if spec.name == name:
        return tr._parse_type(spec.annotation, info.type_params)
  raise_translation_error(tr, None, f"{info.name}.{name} 缺少类型信息")


def _require_struct(
  tr: Translator,
  ctx: _BuildCtx,
  *,
  what: str,
  node: ast.AST | None = None,
) -> ClassInfo:
  if ctx.info is None:
    raise_translation_error(
      tr, node, f"build {what} 要求 struct，当前为 {ctx.cpp_t}",
    )
  return ctx.info


def _child_ctx(
  tr: Translator,
  parent: _BuildCtx,
  field: str,
  *,
  node: ast.AST | None = None,
) -> _BuildCtx:
  info = _require_struct(tr, parent, what=f"字段 {field!r}", node=node)
  cpp_t = _field_cpp_type(tr, info, field)
  child_info = tr._class_info_for_type(strip_cpp_ref(cpp_t))
  return _BuildCtx(cpp_t, child_info)


def _validate_index_ref_in_env(
  tr: Translator,
  name: str,
  env: dict[str, str],
  *,
  node: ast.AST | None = None,
) -> None:
  if name not in env:
    raise_translation_error(
      tr, node,
      f"${name!r} 须来自外层 [:N]: ${name!r} 下标绑定",
    )


def _validate_expr_index_refs(
  tr: Translator,
  expr: ast.expr,
  env: dict[str, str],
  *,
  node: ast.AST | None = None,
) -> None:
  class Validator(ast.NodeVisitor):
    def visit_Name(self, node: ast.Name) -> None:
      if isinstance(node.ctx, ast.Load) and node.id.startswith(BUILD_INDEX_PREFIX):
        bind_name = node.id[len(BUILD_INDEX_PREFIX):]
        _validate_index_ref_in_env(tr, bind_name, env, node=node)
      self.generic_visit(node)

  Validator().visit(expr)


def _validate_value_refs(
  tr: Translator,
  value: BuildValue,
  env: dict[str, str],
  *,
  node: ast.AST | None = None,
) -> None:
  if isinstance(value, IndexRefValue):
    _validate_index_ref_in_env(tr, value.name, env, node=node)
  elif isinstance(value, ExprValue):
    for name in value.index_refs:
      _validate_index_ref_in_env(tr, name, env, node=node)
    _validate_expr_index_refs(tr, value.expr, env, node=node)


def _check_index_value_type(
  tr: Translator,
  field_cpp: str,
  *,
  node: ast.AST | None = None,
) -> None:
  t = strip_cpp_ref(field_cpp)
  if not (is_int_type(t) or is_int64_type(t)):
    raise_translation_error(
      tr, node,
      f"裸 $ 下标引用仅可赋给 int/int64 字段，当前字段为 {field_cpp}",
    )


def _walk_body(
  tr: Translator,
  ctx: _BuildCtx,
  body: BuildBody,
  env: dict[str, str],
  *,
  node: ast.AST | None = None,
) -> None:
  for seg in body.segments:
    if isinstance(seg, AssignSegment):
      info = _require_struct(tr, ctx, what=f"赋值 {seg.field!r}", node=node)
      if seg.field not in info.fields:
        raise_translation_error(
          tr, node, f"{info.name} 无字段 {seg.field!r}",
        )
      _validate_value_refs(tr, seg.value, env, node=node)
      if isinstance(seg.value, IndexRefValue):
        ft = _field_cpp_type(tr, info, seg.field)
        _check_index_value_type(tr, ft, node=node)
    elif isinstance(seg, StructDescentSegment):
      child = _child_ctx(tr, ctx, seg.field, node=node)
      if is_list_type(child.cpp_t):
        raise_translation_error(
          tr, node,
          f"build struct 段 field > 要求非 list 字段，{seg.field!r} 为 list",
        )
      _walk_body(tr, child, seg.body, env, node=node)
    elif isinstance(seg, ListDescentSegment):
      child = _child_ctx(tr, ctx, seg.field, node=node)
      if not is_list_type(child.cpp_t):
        raise_translation_error(
          tr, node,
          f"build list 段 field[:N] > 要求 list 字段，{seg.field!r} 不是 list",
        )
      elem_cpp = list_elem_type(child.cpp_t) or ""
      elem_info = tr._class_info_for_type(strip_cpp_ref(elem_cpp))
      loop_env = dict(env)
      if seg.index_bind is not None:
        if seg.index_bind in loop_env:
          raise_translation_error(
            tr, node, f"build 下标绑定 ${seg.index_bind!r} 重复",
          )
        loop_env[seg.index_bind] = seg.index_bind
      elem_ctx = _BuildCtx(elem_cpp, elem_info)
      _walk_body(tr, elem_ctx, seg.body, loop_env, node=node)


def walk_build_plan(
  tr: Translator,
  plan: BuildPlan,
  target_cpp: str,
  target_info: ClassInfo | None,
  *,
  node: ast.AST | None = None,
) -> BuildWalkResult:
  if isinstance(plan, ListRootPlan):
    if not is_list_type(target_cpp):
      raise_translation_error(
        tr, node, "list[T].build 目标须为 list[T]",
      )
    elem_cpp = list_elem_type(target_cpp) or ""
    elem_info = tr._class_info_for_type(strip_cpp_ref(elem_cpp))
    env: dict[str, str] = {}
    if plan.index_bind is not None:
      env[plan.index_bind] = plan.index_bind
    elem_ctx = _BuildCtx(elem_cpp, elem_info)
    _walk_body(tr, elem_ctx, plan.body, env, node=node)
    return BuildWalkResult(result_cpp=target_cpp)
  if not isinstance(plan, StructRootPlan):
    raise_translation_error(tr, node, f"未知 build plan: {plan!r}")
  if target_info is None:
    raise_translation_error(tr, node, "Type.build 目标须为 @dataclass")
  _walk_body(tr, _BuildCtx(target_cpp, target_info), plan.body, {}, node=node)
  return BuildWalkResult(result_cpp=target_cpp)


def build_result_cpp_type(target_cpp: str) -> str:
  return target_cpp
