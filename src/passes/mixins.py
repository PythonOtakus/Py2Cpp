"""混入类与字段注解展开：``@mixin`` / ``@annotation`` 类不生成 C++，方法内联到宿主类。"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo
from ..analysis.ir import (
  merge_concrete_oneof_constraint,
  merge_decorator_type_constraint,
  merge_oneof_type_constraint,
  strip_type_annotation_markers,
)
from ..analysis.type_emit import field_ann_ast, write_field_ann_ast, write_field_storage
from ..analysis.ir import cpp_ident
from .fixed_vararg import expand_fixed_vararg, method_has_fixed_vararg
from .inline_range import expand_inline_range
from .match_case import (
  _clone_body_replace_names,
  expand_iter_fields_loops,
  expand_iter_fields_meta,
  expand_str_annotation_match,
  extract_field_annotation_meta,
  field_default_expr,
  fold_self_get_field_type_calls,
  is_simple_match,
)
from .method_meta import (
  expand_iter_methods_loop,
  expand_iter_methods_subscript_loop,
  expand_iter_methods_subscript_meta,
  expand_method_signature_reflect,
  expand_mixin_method_meta_closures,
)
from .static_reflect import fold_static_reflect
from .varstack import expand_varstack, method_uses_varstack, method_has_unexpanded_varstack

if TYPE_CHECKING:
  from ..translator import Translator

ANNOTATION_DECORATOR = "annotation"
MIXIN_DECORATOR = "mixin"


def is_annotation_class(info: ClassInfo) -> bool:
  return _has_decorator(info.node, ANNOTATION_DECORATOR)


def is_mixin_class(info: ClassInfo) -> bool:
  return _has_decorator(info.node, MIXIN_DECORATOR)


def _has_decorator(node: ast.ClassDef, name: str) -> bool:
  for dec in node.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == name:
      return True
    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == name:
      return True
  return False


def parse_matmult_annotation(node: ast.expr | None) -> tuple[ast.expr, str] | None:
  """``float @ ArithmeticComponent`` → (类型 AST, 注解类名)。"""
  if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.MatMult):
    return None
  right = node.right
  if isinstance(right, ast.Name):
    return node.left, right.id
  if isinstance(right, ast.Call) and isinstance(right.func, ast.Name):
    return node.left, right.func.id
  return None


def extract_field_annotations(info: ClassInfo) -> None:
  extract_field_annotation_meta(info)


def annotated_fields(
  host: ClassInfo,
  annotation_class: str,
  classes: dict[str, ClassInfo] | None = None,
  *,
  mro: bool = False,
) -> list[str]:
  """字段 ``T @Ann``，或容器类 ``@Ann`` 修饰的 ``ContainerType[...]`` 字段（保持声明序）。"""
  from .annotation_options import annotation_options_for, walk_entity_bases

  extract_field_annotation_meta(host)

  def marked_on(ci: ClassInfo) -> set[str]:
    extract_field_annotation_meta(ci)
    marked = {
      f
      for f in ci.fields
      if annotation_class in ci.field_annotation_markers.get(f, [])
      or ci.field_annotations.get(f) == annotation_class
    }
    if classes is not None:
      marked.update(
        fields_with_annotated_container(
          ci,
          annotation_class,
          classes,
          mro=mro,
        )
      )
    return marked

  out: list[str] = []
  seen: set[str] = set()
  for f in host.fields:
    if f in marked_on(host):
      out.append(f)
      seen.add(f)

  if mro and classes is not None:
    opts = annotation_options_for(classes, annotation_class)
    if opts is not None and opts.inheritable:
      for bi in walk_entity_bases(host, classes):
        for f in bi.fields:
          if f in seen:
            continue
          if f in marked_on(bi):
            out.append(f)
            seen.add(f)
  return out


def _field_container_base_name(stripped_ann: ast.expr | None) -> str | None:
  if isinstance(stripped_ann, ast.Subscript) and isinstance(stripped_ann.value, ast.Name):
    return stripped_ann.value.id
  if isinstance(stripped_ann, ast.Name):
    return stripped_ann.id
  return None


def fields_with_annotated_container(
  host: ClassInfo,
  marker: str,
  classes: dict[str, ClassInfo],
  *,
  mro: bool = False,
) -> list[str]:
  """字段类型为 ``ContainerType[...]`` 且 ``ContainerType`` 类定义带 ``@marker``（``mro`` 时查实体基类）。"""
  from .annotation_options import annotation_options_for, _class_has_marker

  inheritable = False
  if mro:
    opts = annotation_options_for(classes, marker)
    inheritable = opts is not None and opts.inheritable

  out: list[str] = []
  for field_name in host.fields:
    ann = field_ann_ast(host, field_name)
    stripped = strip_type_annotation_markers(ann)
    base = _field_container_base_name(stripped)
    if base is None:
      continue
    container = classes.get(base)
    if container is not None and _class_has_marker(
      container,
      marker,
      classes,
      mro=mro,
      inheritable=inheritable,
      has_decorator=_has_decorator,
    ):
      out.append(field_name)
  return out


def _iter_fields_subscript_annotation(iter_node: ast.expr) -> str | None:
  if not isinstance(iter_node, ast.Call):
    return None
  func = iter_node.func
  if not isinstance(func, ast.Subscript):
    return None
  value = func.value
  if not (
    isinstance(value, ast.Attribute)
    and isinstance(value.value, ast.Name)
    and value.value.id == "Self"
    and value.attr in ("iter_fields", "iterFields")
  ):
    return None
  sl = func.slice
  if isinstance(sl, ast.Name):
    return sl.id
  if isinstance(sl, ast.Call) and isinstance(sl.func, ast.Name):
    return sl.func.id
  return None


def _parse_iter_fields_subscript_options(
  iter_node: ast.expr,
) -> tuple[str, "IterReflectOptions"] | None:
  from .annotation_options import IterReflectOptions, parse_self_iter_call_options

  ann = _iter_fields_subscript_annotation(iter_node)
  if ann is None:
    return None
  opts = parse_self_iter_call_options(
    iter_node,
    allowed=frozenset({"mro", "glob"}),
    label="Self.iter_fields",
  )
  return ann, opts or IterReflectOptions()


def expand_iter_fields_subscript_loop(
  method: ast.FunctionDef,
  host: ClassInfo,
  classes: dict[str, ClassInfo],
) -> ast.FunctionDef | None:
  """``for field in Self.iter_fields[Ann]([mro=…, glob=…]):`` → 按匹配字段展开循环体。"""
  for_idx: int | None = None
  for i, stmt in enumerate(method.body):
    if isinstance(stmt, ast.For):
      parsed = _parse_iter_fields_subscript_options(stmt.iter)
      if parsed is not None:
        for_idx = i
        break
  if for_idx is None:
    return None
  for_node = method.body[for_idx]
  parsed_opts = _parse_iter_fields_subscript_options(for_node.iter)
  assert parsed_opts is not None
  ann, opts = parsed_opts
  if not isinstance(for_node.target, ast.Name):
    return None
  field_var = for_node.target.id
  fields = annotated_fields(host, ann, classes, mro=opts.mro)
  from .annotation_options import filter_iter_names

  fields = filter_iter_names(fields, opts.glob)
  if not fields:
    return None
  known = frozenset(host.fields)
  unrolled: list[ast.stmt] = []
  for field_name in fields:
    renames = {field_var: ast.Constant(value=field_name)}
    cloned = _clone_body_replace_names(for_node.body, renames, known_fields=known)
    cloned = fold_self_get_field_type_calls(
      cloned,
      lambda name: field_ann_ast(host, name),
      known_fields=known,
      default_for_field=lambda name: field_default_expr(host, name, all_classes=classes),
    )
    unrolled.extend(cloned)
  out = copy.deepcopy(method)
  out.body = method.body[:for_idx] + unrolled + method.body[for_idx + 1 :]
  return out


def _setattr_field_binop(stmt: ast.stmt) -> tuple[str, ast.operator, str] | None:
  """``setattr(result, field, getattr(self, f) + getattr(other, f))``。"""
  if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
    return None
  call = stmt.value
  if not (isinstance(call.func, ast.Name) and call.func.id == "setattr" and len(call.args) == 3):
    return None
  target, field_node, value = call.args
  if not (isinstance(target, ast.Name) and isinstance(field_node, ast.Name)):
    return None
  if not isinstance(value, ast.BinOp):
    return None
  left, op, right = value.left, value.op, value.right
  if not (
    isinstance(left, ast.Call)
    and isinstance(left.func, ast.Name)
    and left.func.id == "getattr"
    and len(left.args) == 2
    and isinstance(right, ast.Call)
    and isinstance(right.func, ast.Name)
    and right.func.id == "getattr"
    and len(right.args) == 2
  ):
    return None
  ls, lfield = left.args
  rs, rfield = right.args
  if not (
    isinstance(ls, ast.Name)
    and isinstance(lfield, ast.Name)
    and isinstance(rs, ast.Name)
    and isinstance(rfield, ast.Name)
    and lfield.id == rfield.id == field_node.id
    and ls.id == "self"
    and rs.id == "other"
  ):
    return None
  return field_node.id, op, target.id


def _build_fieldwise_ctor_return(
  host_name: str,
  fields: list[str],
  op: ast.operator,
) -> ast.Return:
  args: list[ast.expr] = []
  for fname in fields:
    args.append(
      ast.BinOp(
        left=ast.Attribute(
          value=ast.Name(id="self", ctx=ast.Load()),
          attr=fname,
          ctx=ast.Load(),
        ),
        op=op,
        right=ast.Attribute(
          value=ast.Name(id="other", ctx=ast.Load()),
          attr=fname,
          ctx=ast.Load(),
        ),
      )
    )
  return ast.Return(
    value=ast.Call(
      func=ast.Name(id=host_name, ctx=ast.Load()),
      args=args,
      keywords=[],
    )
  )


def _expand_fieldwise_loop_method(
  method: ast.FunctionDef,
  host: ClassInfo,
  classes: dict[str, ClassInfo],
) -> ast.FunctionDef | None:
  for_idx: int | None = None
  for i, stmt in enumerate(method.body):
    if isinstance(stmt, ast.For):
      for_idx = i
      break
  if for_idx is None:
    return None
  for_node = method.body[for_idx]
  ann = _iter_fields_subscript_annotation(for_node.iter)
  if ann is None or len(for_node.body) != 1:
    return None
  parsed = _setattr_field_binop(for_node.body[0])
  if parsed is None:
    return None
  _field, op, _result = parsed
  fields = annotated_fields(host, ann, classes)
  if not fields:
    return None
  prefix: list[ast.stmt] = []
  for stmt in method.body[:for_idx]:
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "result":
      continue
    prefix.append(stmt)
  new_body = prefix + [_build_fieldwise_ctor_return(host.cpp_name(), fields, op)]
  out = copy.deepcopy(method)
  out.body = new_body
  return out


def _mixin_base_type_arg_names(slice_node: ast.expr) -> list[str]:
  if isinstance(slice_node, ast.Name):
    return [slice_node.id]
  if isinstance(slice_node, ast.Tuple):
    out: list[str] = []
    for elt in slice_node.elts:
      if isinstance(elt, ast.Name):
        out.append(elt.id)
      else:
        out.append(ast.unparse(elt))
    return out
  return []


def _mixin_type_subst_map_for_host(
  host: ClassInfo,
  mixin: ClassInfo,
) -> dict[str, str] | None:
  """``Host(TransformMixin[Vector2, Rotator, Matrix3])`` → ``Vec``/``Rot``/``Mat`` 替换表。"""
  if not mixin.type_params:
    return None
  mixin_name = mixin.name
  for base in host.node.bases:
    if (
      isinstance(base, ast.Subscript)
      and isinstance(base.value, ast.Name)
      and base.value.id == mixin_name
    ):
      args = _mixin_base_type_arg_names(base.slice)
      if len(args) != len(mixin.type_params):
        return None
      return dict(zip(mixin.type_params, args))
  return None


def _mixin_elem_type_for_host(host: ClassInfo, mixin: ClassInfo) -> str | None:
  """``Host(StringMixin[char])`` → ``char``（供混入方法内 ``T`` 替换）。"""
  subst = _mixin_type_subst_map_for_host(host, mixin)
  if subst is not None and len(subst) == 1:
    return next(iter(subst.values()))
  mixin_name = mixin.name
  for base in host.node.bases:
    if (
      isinstance(base, ast.Subscript)
      and isinstance(base.value, ast.Name)
      and base.value.id == mixin_name
      and isinstance(base.slice, ast.Name)
    ):
      return base.slice.id
  return None


class _MixinTypeParamSubstituter(ast.NodeTransformer):
  """混入并入宿主时把形参名（``T`` / ``Vec`` / ``Rot`` / …）换成具体类型名。"""

  def __init__(self, subst: str | dict[str, str]):
    if isinstance(subst, str):
      self._subst: dict[str, str] = {"T": subst}
    else:
      self._subst = subst

  def visit_Name(self, node: ast.Name) -> ast.expr:
    repl = self._subst.get(node.id)
    if repl is not None:
      return ast.Name(id=repl, ctx=node.ctx)
    return self.generic_visit(node)


class _MixinInliner(ast.NodeTransformer):
  def __init__(self, host: ClassInfo):
    self._host = host
    self._host_name = host.cpp_name()

  def visit_Name(self, node: ast.Name) -> ast.expr:
    if node.id == "Self":
      return ast.Name(id=self._host_name, ctx=node.ctx)
    return node

  def visit_arg(self, node: ast.arg) -> ast.arg:
    return node

  def _preserve_bare_self_return_ann(self, ann: ast.expr | None) -> ast.expr | None:
    """``-> Self`` 保留；``GeneratorType[Self]`` / ``list[Self]`` 等 subscript 内 ``Self`` 仍内联为宿主名。"""
    if ann is None:
      return None
    if isinstance(ann, ast.Name) and ann.id == "Self":
      return ann
    return self.generic_visit(copy.deepcopy(ann))

  def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
    saved_returns = self._preserve_bare_self_return_ann(node.returns)
    node = copy.deepcopy(node)
    node.returns = None
    new_node = self.generic_visit(node)
    new_node.returns = saved_returns
    return new_node

  def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
    saved_returns = self._preserve_bare_self_return_ann(node.returns)
    node = copy.deepcopy(node)
    node.returns = None
    new_node = self.generic_visit(node)
    new_node.returns = saved_returns
    return new_node

  def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
    if isinstance(node.value, ast.Name) and node.value.id == "Self" and node.attr == "__name__":
      return ast.Constant(value=self._host.name)
    return self.generic_visit(node)

  def visit_Match(self, node: ast.Match) -> ast.AST:
    return node

  def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.AST:
    return node


def _mixin_match_supported(node: ast.Match) -> bool:
  """混入内联后宿主可生成 ``switch`` 的 ``match``（如 ``match cn: case 0:``）。"""
  if isinstance(node.subject, ast.Name):
    return is_simple_match(node, cpp_ident("int"))
  return False


def _mixin_method_has_unsupported_after_expand(method: ast.FunctionDef) -> bool:
  for node in ast.walk(method):
    if isinstance(node, ast.Match):
      if _mixin_match_supported(node):
        continue
      return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
      if isinstance(node.func.value, ast.Name) and node.func.value.id == "Self":
        if node.func.attr in (
          "iter_fields",
          "iterFields",
          "enum_fields",
          "enumFields",
          "get_field_annotation",
          "getFieldAnnotation",
          "get_field_annotations",
          "getFieldAnnotations",
          "iter_methods",
          "iterMethods",
          "get_method_annotation",
          "getMethodAnnotation",
          "iter_method_params",
          "iterMethodParams",
          "get_method_param_type",
          "getMethodParamType",
          "get_method_return_type",
          "getMethodReturnType",
          "get_field_type",
          "getFieldType",
          "get_field_default",
          "getFieldDefault",
        ):
          return True
      recv = None
      if isinstance(node.func, ast.Attribute) and node.func.attr in (
        "iter_fields",
        "iterFields",
        "enum_fields",
        "enumFields",
      ):
        if isinstance(node.func.value, ast.Name):
          recv = node.func.value.id
      if recv is not None and recv != "Self":
        return True
  if method_has_unexpanded_varstack(method):
    return True
  return False


def _mixin_preserve_decorators(method: ast.FunctionDef) -> list[ast.expr]:
  """混入内联后保留 ``@immutable`` / ``@override`` / ``@staticmethod`` / ``@property`` 等。"""
  kept: list[ast.expr] = []
  for dec in method.decorator_list:
    if isinstance(dec, ast.Name) and dec.id in (
      "immutable",
      "override",
      "staticmethod",
      "property",
    ):
      kept.append(copy.deepcopy(dec))
    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id in (
      "immutable",
      "property",
    ):
      kept.append(copy.deepcopy(dec))
    elif isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Name):
      if dec.value.id == "property" and dec.attr in ("setter", "postsetter"):
        kept.append(copy.deepcopy(dec))
      if dec.value.id == "staticproperty" and dec.attr in ("setter", "postsetter"):
        kept.append(copy.deepcopy(dec))
  return kept


def _drop_property_names_from_fields(host: ClassInfo) -> None:
  """``self.mag = …`` 等 setter 体勿把 property 名误收进 ``fields``。"""
  for name in list(host.properties):
    if name in host.fields:
      host.fields.remove(name)
  for name in list(host.static_properties):
    if name in host.fields:
      host.fields.remove(name)


def _mixin_type_hosts_for_host(
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
) -> dict[str, ClassInfo]:
  subst_map = _mixin_type_subst_map_for_host(host, mixin)
  if subst_map is None:
    return {}
  out: dict[str, ClassInfo] = {}
  for tp, concrete in subst_map.items():
    ci = classes.get(concrete)
    if ci is not None:
      out[tp] = ci
  return out


def _clone_mixin_method(
  method: ast.FunctionDef,
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
) -> ast.FunctionDef | None:
  cloned = copy.deepcopy(method)
  cloned.decorator_list = _mixin_preserve_decorators(method)
  type_hosts = _mixin_type_hosts_for_host(host, mixin, classes)
  expanded = expand_str_annotation_match(cloned, host)
  if expanded is not None:
    cloned = expanded
  else:
    expanded = expand_iter_fields_meta(cloned, host, all_classes=classes)
    if expanded is not None:
      cloned = expanded
  expanded = expand_iter_fields_loops(cloned, host, type_hosts=type_hosts, all_classes=classes)
  if expanded is not None:
    cloned = expanded
  if method_has_fixed_vararg(cloned):
    expanded = expand_fixed_vararg(cloned, host)
    if expanded is None:
      return None
    cloned = expanded
  cloned = expand_inline_range(cloned, host)
  if method_uses_varstack(cloned):
    expanded = expand_varstack(cloned, host)
    if expanded is None:
      return None
    cloned = expanded
  expanded = expand_mixin_method_meta_closures(cloned, host, classes)
  cloned = expanded
  expanded = _expand_fieldwise_loop_method(cloned, host, classes)
  if expanded is not None:
    cloned = expanded
  expanded = expand_iter_fields_subscript_loop(cloned, host, classes)
  if expanded is not None:
    cloned = expanded
  if _mixin_method_has_unsupported_after_expand(cloned):
    return None
  fold_static_reflect(cloned, known_fields=frozenset(host.fields))
  subst_map = _mixin_type_subst_map_for_host(host, mixin)
  if subst_map is not None:
    cloned = _MixinTypeParamSubstituter(subst_map).visit(cloned)
  else:
    elem = _mixin_elem_type_for_host(host, mixin)
    if elem is not None:
      cloned = _MixinTypeParamSubstituter(elem).visit(cloned)
  cloned = _MixinInliner(host).visit(cloned)
  ast.fix_missing_locations(cloned)
  return cloned


def _mixin_regular_bases(
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
  *,
  _seen: set[str] | None = None,
) -> list[str]:
  """收集混入类继承链上的普通（非 ``@mixin`` / ``@annotation``）基类名。"""
  if _seen is None:
    _seen = set()
  out: list[str] = []
  for base_name in mixin.bases:
    if base_name in _seen:
      continue
    _seen.add(base_name)
    bi = classes.get(base_name)
    if bi is None:
      out.append(base_name)
      continue
    if bi.is_mixin or bi.is_annotation:
      for carried in _mixin_regular_bases(bi, classes, _seen=_seen):
        if carried not in out:
          out.append(carried)
    else:
      if base_name not in out:
        out.append(base_name)
      for bb in bi.bases:
        bb_info = classes.get(bb)
        if bb_info is not None and (bb_info.is_mixin or bb_info.is_annotation):
          for carried in _mixin_regular_bases(bb_info, classes, _seen=_seen):
            if carried not in out:
              out.append(carried)
        elif bb not in out:
          out.append(bb)
  return out


def propagate_mixin_type_param_constraints(
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
  *,
  _seen: set[str] | None = None,
) -> None:
  """混入形参上的 ``@protocol`` / 装饰器约束 → 宿主对应形参（按 ``Mixin[T, …]`` 实参映射）。"""
  if _seen is None:
    _seen = set()
  if mixin.name in _seen:
    return
  _seen.add(mixin.name)

  for base_name in mixin.bases:
    carrier = classes.get(base_name)
    if carrier is not None and carrier.is_mixin:
      propagate_mixin_type_param_constraints(host, carrier, classes, _seen=_seen)

  subst_map = _mixin_type_subst_map_for_host(host, mixin)
  if subst_map is None:
    return
  host_params = set(host.type_params)
  for mixin_tp, mapped in subst_map.items():
    if mapped not in host_params:
      oneof = mixin.type_param_oneof_constraints.get(mixin_tp, ())
      if oneof:
        merge_concrete_oneof_constraint(host.concrete_oneof_constraints, mapped, oneof)
      continue
    for bound in mixin.type_param_constraints.get(mixin_tp, ()):
      merge_decorator_type_constraint(host.type_param_constraints, mapped, bound)
    oneof = mixin.type_param_oneof_constraints.get(mixin_tp, ())
    if oneof:
      merge_oneof_type_constraint(host.type_param_oneof_constraints, mapped, oneof)
    for dec in mixin.type_param_decorator_constraints.get(mixin_tp, ()):
      merge_decorator_type_constraint(host.type_param_decorator_constraints, mapped, dec)


def propagate_mixin_carrier_bases(
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
) -> None:
  """宿主继承 ``@mixin`` 时，并入该混入所携带的普通基类（如 ``TestCaseMixin(TestCase)``）。"""
  for base_name in _mixin_regular_bases(mixin, classes):
    if base_name not in host.bases:
      host.bases.append(base_name)


def propagate_mixin_static_fields(host: ClassInfo, mixin: ClassInfo) -> None:
  """将混入类体 ``static const`` 声明并入宿主；宿主类体赋值可覆盖初值。"""
  for name, stmt in mixin.static_class_fields.items():
    if name not in host.static_class_fields:
      host.static_class_fields[name] = copy.deepcopy(stmt)
  for name, stmt in getattr(mixin, "thread_local_fields", {}).items():
    if name not in getattr(host, "thread_local_fields", {}):
      host.thread_local_fields[name] = copy.deepcopy(stmt)


def propagate_mixin_instance_fields(host: ClassInfo, mixin: ClassInfo) -> None:
  """将混入类体实例字段（非 ``@const``）并入宿主；宿主已声明的字段不覆盖。"""
  skip = (
    frozenset(mixin.properties)
    | frozenset(mixin.static_properties)
    | mixin.field_properties
  )
  subst_map = _mixin_type_subst_map_for_host(host, mixin)
  substituter = (
    _MixinTypeParamSubstituter(subst_map) if subst_map is not None else None
  )
  for name in mixin.fields:
    if name in skip:
      continue
    if name in host.fields:
      continue
    host.fields.append(name)
    if name in mixin.field_type_nodes:
      node = copy.deepcopy(mixin.field_type_nodes[name])
      host.field_type_nodes[name] = node
      from ..analysis.type_emit import write_field_storage

      write_field_storage(host, name, node)
    ann = field_ann_ast(mixin, name)
    if ann is not None:
      ann = copy.deepcopy(ann)
      if substituter is not None and isinstance(ann, ast.expr):
        ann = substituter.visit(ann)
    if ann is not None:
      write_field_ann_ast(host, name, ann)
    if name in mixin.field_defaults:
      default = copy.deepcopy(mixin.field_defaults[name])
      if substituter is not None and isinstance(default, ast.expr):
        default = substituter.visit(default)
      host.field_defaults[name] = default
    if name in mixin.field_annotations:
      host.field_annotations[name] = mixin.field_annotations[name]
    if name in mixin.field_annotation_markers:
      host.field_annotation_markers[name] = list(mixin.field_annotation_markers[name])
    if name in mixin.field_annotation_kwargs:
      host.field_annotation_kwargs[name] = copy.deepcopy(mixin.field_annotation_kwargs[name])
    if name in mixin.optional_fields:
      host.optional_fields.add(name)
    if name in mixin.field_properties:
      host.field_properties.add(name)


def propagate_mixin_dataclass(host: ClassInfo, mixin: ClassInfo) -> None:
  """混入 ``@dataclass`` 元数据并入宿主（宿主自身无 ``@dataclass`` 时）。"""
  if not mixin.is_dataclass:
    return
  from .dataclass_expand import _parse_dataclass_options

  if _parse_dataclass_options(host.node) is not None:
    return
  host.is_dataclass = True
  host.dataclass_options = mixin.dataclass_options
  subst_map = _mixin_type_subst_map_for_host(host, mixin)
  substituter = (
    _MixinTypeParamSubstituter(subst_map) if subst_map is not None else None
  )
  if host.dataclass_field_specs is None:
    host.dataclass_field_specs = []
  existing = {s.name for s in host.dataclass_field_specs}
  for spec in mixin.dataclass_field_specs:
    if spec.name in existing:
      continue
    new_spec = copy.deepcopy(spec)
    if substituter is not None:
      new_spec.annotation = substituter.visit(new_spec.annotation)
      if new_spec.default is not None:
        new_spec.default = substituter.visit(new_spec.default)
      if new_spec.body_init is not None:
        new_spec.body_init = substituter.visit(new_spec.body_init)
    host.dataclass_field_specs.append(new_spec)
  host.optional_fields |= mixin.optional_fields


def propagate_mixin_properties(
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
  *,
  _seen: set[str] | None = None,
) -> None:
  """``@property`` / ``@staticproperty`` 定义自混入并入宿主（先于实例字段与方法内联）。"""
  from ..analysis.ir import PropertyDef

  if _seen is None:
    _seen = set()
  if mixin.name in _seen:
    return
  _seen.add(mixin.name)

  for base_name in mixin.bases:
    carrier = classes.get(base_name)
    if carrier is not None and carrier.is_mixin:
      propagate_mixin_properties(host, carrier, classes, _seen=_seen)

  for pname, prop in mixin.properties.items():
    if pname in host.properties:
      continue
    host_prop = PropertyDef(name=pname)
    if prop.getter is not None:
      cloned = _clone_mixin_method(prop.getter, host, mixin, classes)
      if cloned is not None:
        host_prop.getter = cloned
    if prop.setter is not None:
      cloned = _clone_mixin_method(prop.setter, host, mixin, classes)
      if cloned is not None:
        host_prop.setter = cloned
    if prop.postsetter is not None:
      cloned = _clone_mixin_method(prop.postsetter, host, mixin, classes)
      if cloned is not None:
        host_prop.postsetter = cloned
    if host_prop.getter or host_prop.setter or host_prop.postsetter:
      host.properties[pname] = host_prop

  for spname, prop in mixin.static_properties.items():
    if spname in host.static_properties:
      continue
    host_prop = PropertyDef(name=spname)
    if prop.getter is not None:
      cloned = _clone_mixin_method(prop.getter, host, mixin, classes)
      if cloned is not None:
        host_prop.getter = ClassInfo._normalize_static_property_method(cloned)
    if prop.setter is not None:
      cloned = _clone_mixin_method(prop.setter, host, mixin, classes)
      if cloned is not None:
        host_prop.setter = ClassInfo._normalize_static_property_method(cloned)
    if prop.postsetter is not None:
      cloned = _clone_mixin_method(prop.postsetter, host, mixin, classes)
      if cloned is not None:
        host_prop.postsetter = ClassInfo._normalize_static_property_method(cloned)
    if host_prop.getter or host_prop.setter or host_prop.postsetter:
      host.static_properties[spname] = host_prop


from ..constant.mixin import MIXIN_METHODS_NOT_INLINED


def _host_has_method_name(host: ClassInfo, name: str) -> bool:
  if name in host.methods or name in host.method_overloads:
    return True
  return any(
    isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == name
    for stmt in host.node.body
  )


def _apply_mixin_async_method_defs(
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
  *,
  _seen: set[str],
) -> None:
  """将混入 ``async def`` 并入宿主类体，供 ``expand_generators`` 展开为 ``*_coroutine``。"""
  if mixin.name in _seen:
    return
  _seen.add(mixin.name)

  for base_name in mixin.bases:
    carrier = classes.get(base_name)
    if carrier is not None and carrier.is_mixin:
      _apply_mixin_async_method_defs(host, carrier, classes, _seen=_seen)

  inliner = _MixinInliner(host)
  for stmt in mixin.node.body:
    if not isinstance(stmt, ast.AsyncFunctionDef):
      continue
    name = stmt.name
    if name in MIXIN_METHODS_NOT_INLINED:
      continue
    if _host_has_method_name(host, name):
      continue
    cloned = inliner.visit(copy.deepcopy(stmt))
    if isinstance(cloned.returns, ast.Name) and cloned.returns.id == "Self":
      cloned.returns = ast.Name(id=host.cpp_name(), ctx=ast.Load())
    ast.fix_missing_locations(cloned)
    host.node.body.append(cloned)


def _apply_mixin_method_defs(
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
  *,
  _seen: set[str],
) -> None:
  """将混入（含其 ``@mixin`` 基类）的方法并入宿主；``@overload`` 组写入 ``method_overloads``。"""
  if mixin.name in _seen:
    return
  _seen.add(mixin.name)

  for base_name in mixin.bases:
    carrier = classes.get(base_name)
    if carrier is not None and carrier.is_mixin:
      _apply_mixin_method_defs(host, carrier, classes, _seen=_seen)

  for name, overloads in mixin.method_overloads.items():
    if name in MIXIN_METHODS_NOT_INLINED:
      continue
    if name in host.method_overloads or name in host.methods:
      continue
    cloned_overloads: list[ast.FunctionDef] = []
    for method in overloads:
      cloned = _clone_mixin_method(method, host, mixin, classes)
      if cloned is not None:
        cloned_overloads.append(cloned)
    if not cloned_overloads:
      continue
    host.method_overloads[name] = cloned_overloads
    for cloned in cloned_overloads:
      host._collect_fields(cloned)
      if name == "__copy__":
        host.has_copy = True
      elif name == "__move__":
        host.has_move = True

  for name, method in mixin.methods.items():
    if name in MIXIN_METHODS_NOT_INLINED:
      continue
    if name in host.methods or name in host.method_overloads:
      continue
    cloned = _clone_mixin_method(method, host, mixin, classes)
    if cloned is None:
      continue
    host.methods[name] = cloned
    host._collect_fields(cloned)
    if name == "__copy__":
      host.has_copy = True
    elif name == "__move__":
      host.has_move = True

  _drop_property_names_from_fields(host)
  _apply_mixin_async_method_defs(host, mixin, classes, _seen=set())


def _apply_mixin_init_def(
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
  *,
  _seen: set[str],
) -> None:
  """宿主无手写 ``__init__`` 时，并入混入类（含其 ``@mixin`` 基类）的 ``__init__``。"""
  if mixin.name in _seen:
    return
  _seen.add(mixin.name)

  for base_name in mixin.bases:
    carrier = classes.get(base_name)
    if carrier is not None and carrier.is_mixin:
      _apply_mixin_init_def(host, carrier, classes, _seen=_seen)

  if host.inits or not mixin.inits:
    return
  init = mixin.inits[0]
  cloned = copy.deepcopy(init)
  _MixinInliner(host).visit(cloned)
  ast.fix_missing_locations(cloned)
  host.inits.append(cloned)
  host._collect_fields(cloned)


def propagate_mixin_init(
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo],
) -> None:
  _apply_mixin_init_def(host, mixin, classes, _seen=set())


def apply_mixin_methods(
  host: ClassInfo,
  mixin: ClassInfo,
  classes: dict[str, ClassInfo] | None = None,
) -> None:
  _apply_mixin_method_defs(host, mixin, classes or {}, _seen=set())


def expand_static_reflect(tr: Translator) -> None:
  """宿主类与模块函数内折叠 ``getattr``/``setattr``。"""
  skip = getattr(tr, "skip_cached_analysis_module", None)
  for info in tr.classes.values():
    if skip is not None and skip(info.module_path):
      continue
    if info.is_mixin or info.is_annotation:
      continue
    fields = frozenset(info.fields)
    for method in list(info.iter_methods()) + list(info.inits):
      fold_static_reflect(method, known_fields=fields)
  for _mp, func in tr.module_functions:
    if skip is not None and skip(_mp):
      continue
    fold_static_reflect(func, known_fields=None)


def _expand_reflect_loops_on_class(host: ClassInfo, classes: dict[str, ClassInfo]) -> None:
  """宿主自有方法中的 ``Self.iter_fields[Ann]`` 循环（混入已内联的方法亦再扫一遍无害）。"""
  known = frozenset(host.fields)

  def _fix(method: ast.FunctionDef) -> ast.FunctionDef:
    expanded = _expand_fieldwise_loop_method(method, host, classes)
    if expanded is not None:
      method = expanded
    expanded = expand_iter_fields_subscript_loop(method, host, classes)
    if expanded is not None:
      method = expanded
    fold_static_reflect(method, known_fields=known)
    return method

  for name in list(host.methods):
    host.methods[name] = _fix(host.methods[name])
  for name, overloads in list(host.method_overloads.items()):
    host.method_overloads[name] = [_fix(m) for m in overloads]


def expand_mixins(tr: Translator) -> None:
  from .annotation_options import check_annotation_repeatable, parse_annotation_options

  for info in tr.classes.values():
    info.is_annotation = is_annotation_class(info)
    info.is_mixin = is_mixin_class(info)
    if info.is_annotation:
      info.annotation_options = parse_annotation_options(info.node)

  for info in tr.classes.values():
    if not info.is_annotation:
      extract_field_annotations(info)

  for host in tr.classes.values():
    if host.is_annotation or host.is_mixin:
      continue
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(host.module_path):
      continue
    for base_name in host.bases:
      mixin = tr.classes.get(base_name)
      if mixin is None or not mixin.is_mixin:
        continue
      propagate_mixin_carrier_bases(host, mixin, tr.classes)
      propagate_mixin_type_param_constraints(host, mixin, tr.classes)
      propagate_mixin_static_fields(host, mixin)
      propagate_mixin_properties(host, mixin, tr.classes)
      propagate_mixin_instance_fields(host, mixin)
      propagate_mixin_dataclass(host, mixin)
      propagate_mixin_init(host, mixin, tr.classes)
      apply_mixin_methods(host, mixin, tr.classes)
    _expand_reflect_loops_on_class(host, tr.classes)

  check_annotation_repeatable(tr)
