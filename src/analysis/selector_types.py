"""``SelectorPlan`` + TypeGraph 校验（``@dataclass`` / ``list`` 首版）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..passes.selector_parse import (
  FILTER_BIND_PREFIX,
  FILTER_ELEM_PLACEHOLDER,
  BindStep,
  CountStep,
  DescendantStep,
  FieldStep,
  FilterStep,
  GroupStep,
  IndexStep,
  MultiBracketStep,
  PostStep,
  ProjectionStep,
  RefStep,
  SelectorChainPlan,
  SelectorPlan,
  SliceStep,
  SortStep,
  StrIndexStep,
)
from ..translation_error import raise_translation_error
from .ir import (
  ClassInfo,
  cpp_ident,
  cpp_template_type,
  strip_cpp_ref,
)
from .type_extract import dict_type_args, frozendict_type_args, list_elem_type
from .type_emit import field_ann_ast, field_storage_cpp
from .type_pred import (
  is_dict_type,
  is_float64_type,
  is_float_type,
  is_frozendict_type,
  is_int64_type,
  is_int_type,
  is_list_type,
  is_str_type,
)

if TYPE_CHECKING:
  from ..translator import Translator


@dataclass
class _NavCtx:
  cpp_t: str
  info: ClassInfo | None


@dataclass
class SelectorWalkResult:
  """导航元素类型 + 后处理折叠后的返回 C++ 类型。"""
  elem_cpp: str
  struct_info: ClassInfo | None
  result_cpp: str


def _field_ann(info: ClassInfo, name: str) -> ast.expr | None:
  return field_ann_ast(info, name)


def _field_cpp_type(tr: Translator, info: ClassInfo, name: str) -> str:
  from .type_emit import field_storage_cpp

  if name not in info.fields:
    raise_translation_error(tr, None, f"{info.name} 无字段 {name!r}")
  resolved = field_storage_cpp(info, name)
  if resolved:
    return resolved
  ann = _field_ann(info, name)
  if ann is not None:
    return tr._parse_type(ann, info.type_params)
  specs = getattr(info, "dataclass_field_specs", None)
  if specs:
    for spec in specs:
      if spec.name == name:
        return tr._parse_type(spec.annotation, info.type_params)
  raise_translation_error(tr, None, f"{info.name}.{name} 缺少类型信息")


def _validate_filter_bind_refs(
  tr: Translator,
  expr: ast.expr,
  env: dict[str, _NavCtx],
  *,
  node: ast.AST | None = None,
) -> None:
  class Validator(ast.NodeVisitor):
    def visit_Name(self, node: ast.Name) -> None:
      if isinstance(node.ctx, ast.Load) and node.id.startswith(FILTER_BIND_PREFIX):
        bind_name = node.id[len(FILTER_BIND_PREFIX):]
        if bind_name not in env:
          raise_translation_error(
            tr, node,
            f"filter 内 ${bind_name!r} 须来自同链祖先节点的 : ${bind_name!r} 绑定（非路径根引用）",
          )
      self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
      if (
        isinstance(node.value, ast.Name)
        and node.value.id.startswith(FILTER_BIND_PREFIX)
      ):
        bind_name = node.value.id[len(FILTER_BIND_PREFIX):]
        if bind_name not in env:
          raise_translation_error(
            tr, node,
            f"filter 内 ${bind_name!r} 须来自同链祖先节点的 : ${bind_name!r} 绑定（非路径根引用）",
          )
        info = env[bind_name].info
        if info is not None and node.attr not in info.fields:
          raise_translation_error(
            tr, node,
            f"过滤表达式引用未知字段 {node.attr!r}（{info.name} 无此字段）",
          )
      self.generic_visit(node)

  Validator().visit(expr)


def _validate_filter_fields(
  tr: Translator,
  expr: ast.expr,
  info: ClassInfo | None,
  *,
  node: ast.AST | None = None,
) -> None:
  if info is None:
    return

  class Validator(ast.NodeVisitor):
    def visit_Attribute(self, node: ast.Attribute) -> None:
      if (
        isinstance(node.value, ast.Name)
        and node.value.id == FILTER_ELEM_PLACEHOLDER
        and node.attr not in info.fields
      ):
        raise_translation_error(
          tr, node,
          f"过滤表达式引用未知字段 {node.attr!r}（{info.name} 无此字段）",
        )
      self.generic_visit(node)

  Validator().visit(expr)


def _attr_chain_root(node: ast.expr) -> tuple[str, list[str]] | None:
  """``_sel.a.b`` / ``_bind_t.x`` → (root_name, [a, b])。"""
  attrs: list[str] = []
  cur = node
  while isinstance(cur, ast.Attribute):
    attrs.insert(0, cur.attr)
    cur = cur.value
  if isinstance(cur, ast.Name):
    return cur.id, attrs
  return None


def _unify_numeric_cpp_types(
  tr: Translator,
  left: str,
  right: str,
  *,
  node: ast.AST | None,
) -> str:
  if is_float64_type(left) or is_float64_type(right):
    return cpp_ident("float64")
  if is_float_type(left) or is_float_type(right):
    return cpp_ident("float")
  if is_int64_type(left) or is_int64_type(right):
    return cpp_ident("int64")
  if is_int_type(left) and is_int_type(right):
    return cpp_ident("int")
  raise_translation_error(
    tr, node, f"后处理键算术操作数类型不兼容: {left!r} 与 {right!r}",
  )


def _infer_elem_expr_cpp(
  tr: Translator,
  expr: ast.expr,
  info: ClassInfo | None,
  env: dict[str, _NavCtx],
  *,
  node: ast.AST | None = None,
) -> str:
  """后处理键与 ``{filter}`` 同子集：合法 Py2Cpp 表达式 + 元素 ``.field`` / ``$bind``。"""
  _validate_filter_bind_refs(tr, expr, env, node=node)
  _validate_filter_fields(tr, expr, info, node=node)

  class TypeInfer(ast.NodeVisitor):
    def visit_Constant(self, node: ast.Constant) -> str:
      if isinstance(node.value, bool):
        return cpp_ident("bool")
      if isinstance(node.value, int):
        return cpp_ident("int")
      if isinstance(node.value, float):
        return cpp_ident("float")
      if isinstance(node.value, str):
        return cpp_ident("str")
      raise_translation_error(tr, node, "后处理键不支持该字面量类型")

    def visit_Name(self, node: ast.Name) -> str:
      if not isinstance(node.ctx, ast.Load):
        raise_translation_error(tr, node, "后处理键表达式无效名称")
      if node.id == FILTER_ELEM_PLACEHOLDER:
        if info is None:
          raise_translation_error(tr, node, "后处理键缺少 struct 元素上下文")
        return info.cpp_name()
      if node.id in {"True", "False"}:
        return cpp_ident("bool")
      if node.id.startswith(FILTER_BIND_PREFIX):
        raise_translation_error(
          tr, node, f"后处理键须写 ${node.id[len(FILTER_BIND_PREFIX):]!r}.field",
        )
      t = tr._infer_expr_cpp_type(node)
      if not t:
        raise_translation_error(
          tr, node, f"后处理键无法推断标识符 {node.id!r} 的类型",
        )
      return t

    def visit_Attribute(self, node: ast.Attribute) -> str:
      root = _attr_chain_root(node)
      if root is None:
        t = tr._infer_expr_cpp_type(node)
        if not t:
          raise_translation_error(tr, node, "后处理键属性类型无法推断")
        return t
      root_name, attrs = root
      if root_name == FILTER_ELEM_PLACEHOLDER:
        owner_info = info
      elif root_name.startswith(FILTER_BIND_PREFIX):
        bind_name = root_name[len(FILTER_BIND_PREFIX):]
        if bind_name not in env:
          raise_translation_error(
            tr, node,
            f"后处理键 ${bind_name!r} 须来自同链祖先节点的 : ${bind_name!r} 绑定",
          )
        owner_info = env[bind_name].info
      else:
        t = tr._infer_expr_cpp_type(node)
        if not t:
          raise_translation_error(tr, node, "后处理键属性类型无法推断")
        return t
      if owner_info is None:
        raise_translation_error(tr, node, "后处理键缺少 struct 上下文")
      cur_info = owner_info
      cur_t = ""
      for attr in attrs:
        cur_t = _field_cpp_type(tr, cur_info, attr)
        cur_info = tr._class_info_for_type(strip_cpp_ref(cur_t))
      return cur_t

    def visit_BinOp(self, node: ast.BinOp) -> str:
      left_t = self.visit(node.left)
      right_t = self.visit(node.right)
      if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod)):
        return _unify_numeric_cpp_types(tr, left_t, right_t, node=node)
      if isinstance(node.op, (ast.BitOr, ast.BitAnd, ast.BitXor)):
        if left_t == right_t:
          return left_t
        raise_translation_error(tr, node, "后处理键位运算操作数类型须一致")
      raise_translation_error(
        tr, node, f"后处理键不支持运算符 {type(node.op).__name__}",
      )

    def visit_UnaryOp(self, node: ast.UnaryOp) -> str:
      operand_t = self.visit(node.operand)
      if isinstance(node.op, ast.Not):
        return cpp_ident("bool")
      if isinstance(node.op, (ast.UAdd, ast.USub)):
        if (
          is_int_type(operand_t)
          or is_int64_type(operand_t)
          or is_float_type(operand_t)
          or is_float64_type(operand_t)
        ):
          return operand_t
      raise_translation_error(
        tr, node, f"后处理键不支持一元 {type(node.op).__name__}",
      )

    def visit_BoolOp(self, node: ast.BoolOp) -> str:
      for val in node.values:
        self.visit(val)
      return cpp_ident("bool")

    def visit_Compare(self, node: ast.Compare) -> str:
      left_t = self.visit(node.left)
      for comp, right in zip(node.ops, node.comparators):
        right_t = self.visit(right)
        if isinstance(comp, ast.In) or isinstance(comp, ast.NotIn):
          continue
        if left_t != right_t and not (
          is_int_type(left_t) and is_int_type(right_t)
        ):
          _unify_numeric_cpp_types(tr, left_t, right_t, node=node)
        left_t = right_t
      return cpp_ident("bool")

    def visit_IfExp(self, node: ast.IfExp) -> str:
      self.visit(node.test)
      body_t = self.visit(node.body)
      orelse_t = self.visit(node.orelse)
      if body_t == orelse_t:
        return body_t
      if (
        is_int_type(body_t)
        or is_int64_type(body_t)
        or is_float_type(body_t)
        or is_float64_type(body_t)
      ) and (
        is_int_type(orelse_t)
        or is_int64_type(orelse_t)
        or is_float_type(orelse_t)
        or is_float64_type(orelse_t)
      ):
        return _unify_numeric_cpp_types(tr, body_t, orelse_t, node=node)
      if is_str_type(body_t) and is_str_type(orelse_t):
        return cpp_ident("str")
      raise_translation_error(tr, node, "后处理键条件表达式分支类型须一致")

    def generic_visit(self, node: ast.AST) -> str:
      if not isinstance(node, ast.expr):
        raise_translation_error(
          tr, node, f"后处理键表达式不支持 {type(node).__name__}",
        )
      t = tr._infer_expr_cpp_type(node)
      if not t:
        raise_translation_error(
          tr, node, f"后处理键表达式类型无法推断: {type(node).__name__}",
        )
      return t

  return TypeInfer().visit(expr)


def _fold_post_result_cpp(
  tr: Translator,
  elem_cpp: str,
  struct_info: ClassInfo | None,
  post_steps: tuple[PostStep, ...],
  env: dict[str, _NavCtx],
  *,
  node: ast.AST | None = None,
) -> str:
  cur = select_result_cpp_type(elem_cpp)
  cur_is_dict = False
  dict_key_cpp = ""
  for step in post_steps:
    if isinstance(step, SortStep):
      if cur_is_dict:
        raise_translation_error(tr, node, "@sort 要求 list 输入")
      for key in step.keys:
        _infer_elem_expr_cpp(
          tr, key.expr, struct_info, env, node=node,
        )
    elif isinstance(step, GroupStep):
      if cur_is_dict:
        raise_translation_error(tr, node, "@group 要求 list 输入")
      key_cpp = _infer_elem_expr_cpp(
        tr, step.expr, struct_info, env, node=node,
      )
      cur = cpp_template_type("dict", f"{key_cpp}, {cur}")
      cur_is_dict = True
      dict_key_cpp = key_cpp
    elif isinstance(step, CountStep):
      if cur_is_dict:
        raise_translation_error(
          tr, node,
          "@group 后不支持 @count；按字段频数请用 @count(.field)",
        )
      if step.expr is None:
        cur = cpp_ident("int")
      else:
        key_cpp = _infer_elem_expr_cpp(
          tr, step.expr, struct_info, env, node=node,
        )
        cur = cpp_template_type("Counter", key_cpp)
  return cur


def _collect_nav_env(
  tr: Translator,
  recv_type: str,
  root_info: ClassInfo | None,
  plan: SelectorPlan | SelectorChainPlan,
  *,
  node: ast.AST | None = None,
) -> dict[str, _NavCtx]:
  """收集 ``: $ident`` 绑定表，供后处理键内 ``$ident`` 校验。"""
  env: dict[str, _NavCtx] = {}
  start_ctx = _NavCtx(recv_type, root_info)

  def walk_collect(steps: tuple, ctx: _NavCtx) -> None:
    for step in steps:
      if isinstance(step, BindStep):
        env[step.name] = ctx
      elif isinstance(step, RefStep):
        if step.name in env:
          ctx = env[step.name]
      elif isinstance(step, (ProjectionStep, DescendantStep)):
        return
      elif isinstance(step, FilterStep):
        elem_cpp, info = _list_elem_ctx(tr, ctx, node=node, what="过滤")
        ctx = _NavCtx(elem_cpp, info)
      else:
        ctx = _walk_nav_step(tr, ctx, step, env, node=node)

  if isinstance(plan, SelectorChainPlan):
    ctx = start_ctx
    for step in plan.bind_prefix:
      if isinstance(step, BindStep):
        env[step.name] = ctx
      else:
        ctx = _walk_nav_step(tr, ctx, step, env, node=node)
    walk_collect(plan.steps, start_ctx)
  else:
    walk_collect(plan.steps, start_ctx)
  return env


def _list_elem_ctx(
  tr: Translator,
  ctx: _NavCtx,
  *,
  node: ast.AST | None,
  what: str,
) -> tuple[str, ClassInfo | None]:
  if not is_list_type(ctx.cpp_t):
    raise_translation_error(
      tr, node, f"select {what} 要求 list，当前为 {ctx.cpp_t}",
    )
  elem = list_elem_type(ctx.cpp_t)
  if not elem:
    raise_translation_error(tr, node, "无法解析 list 元素类型")
  elem_cpp = elem.strip()
  return elem_cpp, tr._class_info_for_type(elem_cpp)


def _dict_value_ctx(
  tr: Translator,
  ctx: _NavCtx,
  *,
  node: ast.AST | None,
  what: str,
) -> tuple[str, ClassInfo | None]:
  if is_dict_type(ctx.cpp_t):
    inner = dict_type_args(ctx.cpp_t) or ""
  elif is_frozendict_type(ctx.cpp_t):
    inner = frozendict_type_args(ctx.cpp_t) or ""
  else:
    raise_translation_error(
      tr, node, f"select {what} 要求 dict，当前为 {ctx.cpp_t}",
    )
  parts = [p.strip() for p in inner.split(",")]
  if len(parts) < 2 or not parts[1]:
    raise_translation_error(tr, node, "无法解析 dict 值类型")
  val_cpp = parts[1]
  return val_cpp, tr._class_info_for_type(strip_cpp_ref(val_cpp))


def _walk_field(
  tr: Translator,
  ctx: _NavCtx,
  step: FieldStep,
  *,
  node: ast.AST | None,
) -> _NavCtx:
  if ctx.info is None:
    raise_translation_error(
      tr, node, f"select 路径字段 {step.name!r} 无 struct 上下文",
    )
  if step.name not in ctx.info.fields:
    raise_translation_error(
      tr, node, f"{ctx.info.name} 无字段 {step.name!r}",
    )
  cpp_t = _field_cpp_type(tr, ctx.info, step.name)
  return _NavCtx(cpp_t, tr._class_info_for_type(strip_cpp_ref(cpp_t)))


def _collect_descendant_relative_paths(
  tr: Translator,
  ctx: _NavCtx,
  target: str,
  *,
  node: ast.AST | None = None,
) -> list[tuple]:
  """自 ``ctx`` 起递归收集到达 ``target`` 字段的相对步序列。"""
  results: list[tuple] = []
  if ctx.info is not None:
    for fname in ctx.info.fields:
      sub = _walk_field(tr, ctx, FieldStep(fname), node=node)
      if fname == target:
        results.append((FieldStep(fname),))
      for inner in _collect_descendant_relative_paths(tr, sub, target, node=node):
        results.append((FieldStep(fname),) + inner)
  if is_list_type(ctx.cpp_t):
    elem_cpp, info = _list_elem_ctx(
      tr, ctx, node=node, what=f"递归下降 ..{target}",
    )
    for inner in _collect_descendant_relative_paths(
      tr, _NavCtx(elem_cpp, info), target, node=node,
    ):
      results.append((SliceStep(None, None),) + inner)
  return results


def _walk_nav_step(
  tr: Translator,
  ctx: _NavCtx,
  step: object,
  env: dict[str, _NavCtx],
  *,
  node: ast.AST | None = None,
) -> _NavCtx:
  if isinstance(step, BindStep):
    if step.name in env:
      raise_translation_error(
        tr, node, f"select 绑定 ${step.name!r} 重复",
      )
    env[step.name] = ctx
    return ctx
  if isinstance(step, RefStep):
    if step.name not in env:
      raise_translation_error(
        tr, node, f"${step.name!r} 须来自同链祖先节点的 : ${step.name!r} 绑定",
      )
    return env[step.name]
  if isinstance(step, FieldStep):
    return _walk_field(tr, ctx, step, node=node)
  if isinstance(step, IndexStep):
    elem_cpp, info = _list_elem_ctx(
      tr, ctx, node=node, what=f"下标 [{step.index}]",
    )
    return _NavCtx(elem_cpp, info)
  if isinstance(step, StrIndexStep):
    val_cpp, info = _dict_value_ctx(
      tr, ctx, node=node, what=f"下标 [{step.key!r}]",
    )
    return _NavCtx(val_cpp, info)
  if isinstance(step, SliceStep):
    elem_cpp, info = _list_elem_ctx(tr, ctx, node=node, what="切片")
    return _NavCtx(elem_cpp, info)
  if isinstance(step, MultiBracketStep):
    if step.items and isinstance(step.items[0], StrIndexStep):
      val_cpp, info = _dict_value_ctx(tr, ctx, node=node, what="多字符串下标")
      return _NavCtx(val_cpp, info)
    elem_cpp, info = _list_elem_ctx(tr, ctx, node=node, what="多下标")
    return _NavCtx(elem_cpp, info)
  if isinstance(step, FilterStep):
    elem_cpp, info = _list_elem_ctx(tr, ctx, node=node, what="过滤")
    _validate_filter_fields(tr, step.expr, info, node=node)
    _validate_filter_bind_refs(tr, step.expr, env, node=node)
    return _NavCtx(elem_cpp, info)
  if isinstance(step, ProjectionStep):
    if ctx.info is None:
      raise_translation_error(tr, node, "投影要求 struct 上下文")
    return ctx
  if isinstance(step, DescendantStep):
    return ctx
  raise_translation_error(tr, node, f"未知 select 步: {step!r}")


def _walk_nav_steps(
  tr: Translator,
  ctx: _NavCtx,
  steps: tuple,
  env: dict[str, _NavCtx],
  *,
  node: ast.AST | None = None,
) -> _NavCtx:
  for step in steps:
    ctx = _walk_nav_step(tr, ctx, step, env, node=node)
  return ctx


def _walk_value_types(
  tr: Translator,
  ctx: _NavCtx,
  steps: tuple,
  env: dict[str, _NavCtx] | None = None,
  *,
  node: ast.AST | None = None,
) -> list[str]:
  if env is None:
    env = {}
  if not steps:
    if is_list_type(ctx.cpp_t):
      elem_cpp, _ = _list_elem_ctx(tr, ctx, node=node, what="枚举")
      return [elem_cpp]
    return [strip_cpp_ref(ctx.cpp_t)]

  step = steps[0]
  rest = steps[1:]

  if isinstance(step, BindStep):
    if step.name in env:
      raise_translation_error(
        tr, node, f"select 绑定 ${step.name!r} 重复",
      )
    env = dict(env)
    env[step.name] = ctx
    return _walk_value_types(tr, ctx, rest, env, node=node)

  if isinstance(step, RefStep):
    if step.name not in env:
      raise_translation_error(
        tr, node, f"${step.name!r} 须来自同链祖先节点的 : ${step.name!r} 绑定",
      )
    return _walk_value_types(tr, env[step.name], rest, env, node=node)

  if isinstance(step, FieldStep):
    return _walk_value_types(
      tr, _walk_field(tr, ctx, step, node=node), rest, env, node=node,
    )

  if isinstance(step, IndexStep):
    elem_cpp, info = _list_elem_ctx(tr, ctx, node=node, what=f"下标 [{step.index}]")
    return _walk_value_types(tr, _NavCtx(elem_cpp, info), rest, env, node=node)

  if isinstance(step, StrIndexStep):
    val_cpp, info = _dict_value_ctx(tr, ctx, node=node, what=f"下标 [{step.key!r}]")
    return _walk_value_types(tr, _NavCtx(val_cpp, info), rest, env, node=node)

  if isinstance(step, SliceStep):
    elem_cpp, info = _list_elem_ctx(tr, ctx, node=node, what="切片")
    return _walk_value_types(tr, _NavCtx(elem_cpp, info), rest, env, node=node)

  if isinstance(step, MultiBracketStep):
    if step.items and isinstance(step.items[0], StrIndexStep):
      val_cpp, info = _dict_value_ctx(tr, ctx, node=node, what="多字符串下标")
      out: list[str] = []
      for _item in step.items:
        sub = _NavCtx(val_cpp, info)
        out.extend(_walk_value_types(tr, sub, rest, env, node=node))
      return out
    elem_cpp, info = _list_elem_ctx(tr, ctx, node=node, what="多下标")
    out: list[str] = []
    for _item in step.items:
      sub = _NavCtx(elem_cpp, info)
      out.extend(_walk_value_types(tr, sub, rest, env, node=node))
    return out

  if isinstance(step, FilterStep):
    elem_cpp, info = _list_elem_ctx(tr, ctx, node=node, what="过滤")
    _validate_filter_fields(tr, step.expr, info, node=node)
    _validate_filter_bind_refs(tr, step.expr, env, node=node)
    return _walk_value_types(tr, _NavCtx(elem_cpp, info), rest, env, node=node)

  if isinstance(step, ProjectionStep):
    if ctx.info is None:
      raise_translation_error(tr, node, "投影要求 struct 上下文")
    out: list[str] = []
    for arm in step.arms:
      out.extend(_walk_value_types(tr, ctx, arm.steps + rest, env, node=node))
    return out

  if isinstance(step, DescendantStep):
    paths = _collect_descendant_relative_paths(tr, ctx, step.field, node=node)
    if not paths:
      raise_translation_error(
        tr, node, f"递归下降 ..{step.field!r} 未找到任何匹配字段",
      )
    out: list[str] = []
    for rel in paths:
      out.extend(_walk_value_types(tr, ctx, rel + rest, env, node=node))
    return out

  raise_translation_error(tr, node, f"未知 select 步: {step!r}")


def walk_selector_plan(
  tr: Translator,
  recv: ast.expr,
  recv_type: str,
  root_info: ClassInfo | None,
  plan: SelectorPlan | SelectorChainPlan,
  *,
  node: ast.AST | None = None,
) -> SelectorWalkResult:
  if isinstance(plan, SelectorChainPlan):
    env: dict[str, _NavCtx] = {}
    start_ctx = _NavCtx(recv_type, root_info)
    if plan.bind_prefix:
      _walk_nav_steps(tr, start_ctx, plan.bind_prefix, env, node=node)
    types = _walk_value_types(tr, start_ctx, plan.steps, env, node=node)
  else:
    env = {}
    types = _walk_value_types(
      tr, _NavCtx(recv_type, root_info), plan.steps, env, node=node,
    )
  if not types:
    raise_translation_error(tr, node, "select 路径未产生任何值")
  uniq = set(types)
  if len(uniq) != 1:
    raise_translation_error(
      tr, node, f"select 路径各分支末步类型须一致：{types!r}",
    )
  elem_cpp = types[0]
  struct_info = tr._class_info_for_type(elem_cpp)
  nav_env = _collect_nav_env(tr, recv_type, root_info, plan, node=node)
  post_steps = plan.post_steps
  result_cpp = _fold_post_result_cpp(
    tr, elem_cpp, struct_info, post_steps, nav_env, node=node,
  )
  return SelectorWalkResult(
    elem_cpp=elem_cpp,
    struct_info=struct_info,
    result_cpp=result_cpp,
  )


def select_result_cpp_type(elem_cpp: str) -> str:
  return cpp_template_type("list", elem_cpp)


def select_expected_ann(walk: SelectorWalkResult) -> str:
  return walk.result_cpp
