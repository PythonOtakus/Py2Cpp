"""``@dataclass``：从类体字段生成 ``__init__`` / ``__eq__`` / ``__repr__`` / ``__cmp__``（对齐 CPython 3.13 常用选项）。

字段默认值直接写在类体（``y: int = 0``、``items: list[int] @optional = []``）；容器 / ``char[:]``
默认不能进 ``__init__`` 形参（C++ 容器按引用传参，**S26** 强制 ``@optional``）。``T @optional`` 不参与
``__init__`` / ``assign`` 形参；``order=True`` 时亦不参与 ``__cmp__`` 字典序比较。类内
``__post_init__`` 在自动生成 ``__init__`` 末尾调用（对齐 CPython）。
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import (
  ClassInfo,
  has_named_decorator,
  is_const_type_annotation,
  is_optional_type_annotation,
  is_native_function_body,
  is_postsetter_type_annotation,
  is_property_type_annotation,
  strip_type_annotation_markers,
)
from ..analysis.type_emit import write_field_ann_ast, write_field_storage
from ..constant.stdlib_discovery import is_stdlib_codegen_module

if TYPE_CHECKING:
  from ..translator import Translator

DATACLASS_DECORATOR = "dataclass"
_IMMUTABLE_DEC = ast.Name(id="immutable", ctx=ast.Load())


@dataclass(frozen=True)
class DataclassOptions:
  init: bool = True
  repr: bool = True
  eq: bool = True
  order: bool = False
  frozen: bool = False
  kw_only: bool = False
  slots: bool = False


@dataclass
class DataclassFieldSpec:
  name: str
  annotation: ast.expr
  default: ast.expr | None = None
  body_init: ast.expr | None = None
  optional: bool = False


def _is_dataclass_decorator(dec: ast.expr) -> bool:
  if isinstance(dec, ast.Name) and dec.id == DATACLASS_DECORATOR:
    return True
  return (
    isinstance(dec, ast.Call)
    and isinstance(dec.func, ast.Name)
    and dec.func.id == DATACLASS_DECORATOR
  )


def _parse_dataclass_options(node: ast.ClassDef) -> DataclassOptions | None:
  overrides: dict[str, bool] = {}
  found = False
  for dec in node.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == DATACLASS_DECORATOR:
      found = True
      continue
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Name):
      continue
    if dec.func.id != DATACLASS_DECORATOR:
      continue
    found = True
    for kw in dec.keywords:
      if kw.arg is None:
        raise NotImplementedError("@dataclass 不支持 **kwargs 解包")
      val = kw.value
      if not isinstance(val, ast.Constant) or not isinstance(val.value, bool):
        raise NotImplementedError(f"@dataclass({kw.arg}=…) 须为 bool 常量")
      overrides[kw.arg] = val.value
  if not found:
    return None
  # order=True 且未写 eq 时默认 eq=False（仅生成 __cmp__；需 __eq__ 时显式 eq=True）
  kwargs = dict(overrides)
  if kwargs.get("order") and "eq" not in overrides:
    kwargs["eq"] = False
  return DataclassOptions(**kwargs)


def _is_classvar_annotation(ann: ast.expr | None) -> bool:
  if ann is None:
    return False
  match ann:
    case ast.Name(id="ClassVar"):
      return True
    case ast.Subscript(value=ast.Name(id="ClassVar")):
      return True
    case ast.Attribute(value=ast.Name(id="typing"), attr="ClassVar"):
      return True
    case ast.Subscript(value=ast.Attribute(value=ast.Name(id="typing"), attr="ClassVar")):
      return True
  return False


_DATACLASS_CONTAINER_ANN_NAMES = frozenset({
  "list",
  "dict",
  "set",
  "deque",
  "frozenset",
  "frozenlist",
  "frozendict",
})


def _is_new_call(value: ast.expr) -> bool:
  return (
    isinstance(value, ast.Call)
    and isinstance(value.func, ast.Name)
    and value.func.id == "new"
  )


def _annotation_is_mutable_container(ann: ast.expr) -> bool:
  """``list[int]`` / ``char[:]`` 等须在构造体内初始化，避免共享默认。"""
  if _heap_buffer_kind(ann) is not None:
    return True
  if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
    return ann.value.id in _DATACLASS_CONTAINER_ANN_NAMES
  return False


def _new_as_init_param(value: ast.expr, annotation: ast.expr) -> bool:
  """``new(...)`` 且非容器注解 → 构造形参默认（``UIStyle = new()`` / ``new(font_size=11)`` 等）。"""
  if not _is_new_call(value):
    return False
  return not _annotation_is_mutable_container(annotation)


def _needs_body_init(
  value: ast.expr,
  annotation: ast.expr | None = None,
) -> bool:
  """``[]`` / ``{}`` / ``new.xxx`` / 非 ``new`` 的 ``Call`` 等在 ``__init__`` 体内赋值。"""
  if isinstance(value, (ast.List, ast.Dict, ast.Set)):
    return True
  if (
    isinstance(value, ast.Attribute)
    and isinstance(value.value, ast.Name)
    and value.value.id == "new"
  ):
    return True
  if not isinstance(value, ast.Call):
    return False
  if annotation is None:
    return True
  return not _new_as_init_param(value, annotation)


def _heap_buffer_kind(ann: ast.expr) -> str | None:
  """``char[:]`` / ``byte[:]`` → ``'char'`` / ``'byte'``。"""
  if not isinstance(ann, ast.Subscript) or not isinstance(ann.value, ast.Name):
    return None
  if ann.value.id not in ("char", "byte"):
    return None
  if isinstance(ann.slice, ast.Slice):
    return ann.value.id
  return None


def _is_empty_heap_buffer_default(value: ast.expr, ann: ast.expr) -> bool:
  """空 ``char[:] = ""`` / ``byte[:] = b""`` 在构造体内初始化（避免引用形参默认）。"""
  kind = _heap_buffer_kind(ann)
  if kind is None or not isinstance(value, ast.Constant):
    return False
  if kind == "char":
    return value.value == ""
  return value.value == b""


def _parse_class_default(
  value: ast.expr | None, *, optional: bool, name: str, annotation: ast.expr | None = None,
) -> tuple[ast.expr | None, ast.expr | None]:
  """返回 ``(init_param_default, body_init_expr)``。"""
  if value is None:
    if optional:
      raise NotImplementedError(f"{name}: @optional 字段须写类体默认值")
    return None, None
  if annotation is not None and _is_empty_heap_buffer_default(value, annotation):
    return None, value
  if _needs_body_init(value, annotation):
    return None, value
  return value, None


def _collect_dataclass_fields(
  node: ast.ClassDef,
  *,
  allow_empty: bool = False,
) -> list[DataclassFieldSpec]:
  specs: list[DataclassFieldSpec] = []
  for stmt in node.body:
    if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
      continue
    if _is_classvar_annotation(stmt.annotation):
      continue
    if is_const_type_annotation(stmt.annotation):
      continue
    if is_property_type_annotation(stmt.annotation):
      continue
    if is_postsetter_type_annotation(stmt.annotation):
      continue
    name = stmt.target.id
    optional = is_optional_type_annotation(stmt.annotation)
    base_ann = strip_type_annotation_markers(stmt.annotation)
    if base_ann is None:
      raise NotImplementedError(f"{name}: 缺少类型注解")
    param_def, body_init = _parse_class_default(
      stmt.value, optional=optional, name=name, annotation=base_ann,
    )
    specs.append(
      DataclassFieldSpec(
        name=name,
        annotation=copy.deepcopy(base_ann),
        default=copy.deepcopy(param_def) if param_def is not None else None,
        body_init=copy.deepcopy(body_init) if body_init is not None else None,
        optional=optional,
      )
    )
  if not specs and not allow_empty:
    raise NotImplementedError("@dataclass 类须至少有一个实例字段（带类型注解）")
  return specs


def _strip_dataclass_decorators(node: ast.ClassDef) -> None:
  node.decorator_list = [
    dec for dec in node.decorator_list if not _is_dataclass_decorator(dec)
  ]


def _rewrite_class_field_decls(
  node: ast.ClassDef, specs: list[DataclassFieldSpec], info: ClassInfo,
) -> None:
  """类体只保留 ``name: T``（无类级初值）；默认值由生成的 ``__init__`` 承载。"""
  spec_names = {s.name for s in specs}
  new_body: list[ast.stmt] = []
  for stmt in node.body:
    if (
      isinstance(stmt, ast.AnnAssign)
      and isinstance(stmt.target, ast.Name)
      and stmt.target.id in spec_names
    ):
      name = stmt.target.id
      spec = next(s for s in specs if s.name == name)
      info.static_class_fields.pop(name, None)
      if name not in info.fields:
        info.fields.append(name)
      write_field_storage(info, name, None)
      write_field_ann_ast(info, name, copy.deepcopy(spec.annotation))
      info.field_defaults.pop(name, None)
      new_body.append(
        ast.AnnAssign(
          target=ast.Name(id=name, ctx=ast.Store()),
          annotation=copy.deepcopy(spec.annotation),
          value=None,
          simple=1,
        )
      )
      ast.fix_missing_locations(new_body[-1])
      continue
    new_body.append(stmt)
  node.body = new_body
  ast.fix_missing_locations(node)


def _assign_params(
  specs: list[DataclassFieldSpec],
) -> tuple[list[ast.arg], list[ast.expr]]:
  """无默认 / 仅形参默认的字段；``@optional`` 与体内初始化字段不进形参表。"""
  args: list[ast.arg] = [ast.arg(arg="self")]
  defaults: list[ast.expr] = []
  for spec in specs:
    if spec.optional or spec.body_init is not None:
      continue
    args.append(
      ast.arg(arg=spec.name, annotation=copy.deepcopy(spec.annotation)),
    )
    if spec.default is not None:
      defaults.append(copy.deepcopy(spec.default))
  n_def = len(defaults)
  if n_def:
    args = args[:-n_def] + args[-n_def:]
  return args, defaults


def _body_init_rhs(spec: DataclassFieldSpec) -> ast.expr:
  if spec.body_init is None:
    raise ValueError("body_init required")
  match spec.body_init:
    case ast.List() | ast.Dict() | ast.Set():
      # 空容器字面量：``self.f = []`` 由 emit 按字段注解生成 ``PyList<…>()``（含 ``list[T,N]``）
      return copy.deepcopy(spec.body_init)
    case ast.Call():
      return copy.deepcopy(spec.body_init)
  return copy.deepcopy(spec.body_init)


def _make_init_assign(spec: DataclassFieldSpec, *, from_param: bool) -> ast.stmt:
  target = ast.Attribute(
    value=ast.Name(id="self", ctx=ast.Load()),
    attr=spec.name,
    ctx=ast.Store(),
  )
  if from_param:
    value: ast.expr = ast.Name(id=spec.name, ctx=ast.Load())
  elif spec.body_init is not None:
    value = _body_init_rhs(spec)
  elif spec.default is not None:
    value = copy.deepcopy(spec.default)
  else:
    raise ValueError(f"{spec.name}: 缺少初始化表达式")
  stmt = ast.Assign(targets=[target], value=value)
  ast.fix_missing_locations(stmt)
  return stmt


def _post_init_call_stmt() -> ast.Expr:
  """生成 ``self.__post_init__()``（在字段赋值之后调用，对齐 CPython dataclasses）。"""
  stmt = ast.Expr(
    value=ast.Call(
      func=ast.Attribute(
        value=ast.Name(id="self", ctx=ast.Load()),
        attr="__post_init__",
        ctx=ast.Load(),
      ),
      args=[],
    ),
  )
  ast.fix_missing_locations(stmt)
  return stmt


def _generate_init(
  specs: list[DataclassFieldSpec],
  class_name: str,
  *,
  call_post_init: bool = False,
) -> ast.FunctionDef:
  args, defaults = _assign_params(specs)
  body: list[ast.stmt] = []
  for spec in specs:
    if spec.optional or spec.body_init is not None:
      body.append(_make_init_assign(spec, from_param=False))
  for spec in specs:
    if spec.optional or spec.body_init is not None:
      continue
    body.append(_make_init_assign(spec, from_param=True))
  if call_post_init:
    body.append(_post_init_call_stmt())
  fn = ast.FunctionDef(
    name="__init__",
    args=ast.arguments(
      posonlyargs=[],
      args=args,
      kwonlyargs=[],
      kw_defaults=[],
      defaults=defaults,
      kwarg=None,
    ),
    body=body,
    decorator_list=[],
    returns=ast.Constant(value=None),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def _generate_eq(specs: list[DataclassFieldSpec], class_name: str) -> ast.FunctionDef:
  if not specs:
    raise NotImplementedError("@dataclass(eq=True) 但无字段")
  tests: list[ast.expr] = []
  for spec in specs:
    tests.append(
      ast.Compare(
        left=ast.Attribute(
          value=ast.Name(id="self", ctx=ast.Load()),
          attr=spec.name,
          ctx=ast.Load(),
        ),
        ops=[ast.Eq()],
        comparators=[
          ast.Attribute(
            value=ast.Name(id="other", ctx=ast.Load()),
            attr=spec.name,
            ctx=ast.Load(),
          )
        ],
      )
    )
  test_expr = tests[0]
  for extra in tests[1:]:
    test_expr = ast.BoolOp(op=ast.And(), values=[test_expr, extra])
  fn = ast.FunctionDef(
    name="__eq__",
    args=ast.arguments(
      posonlyargs=[],
      args=[
        ast.arg(arg="self"),
        ast.arg(arg="other", annotation=ast.Name(id="Self", ctx=ast.Load())),
      ],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=[ast.Return(value=test_expr)],
    decorator_list=[copy.deepcopy(_IMMUTABLE_DEC)],
    returns=ast.Name(id="bool", ctx=ast.Load()),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def _self_other_attr(name: str) -> tuple[ast.Attribute, ast.Attribute]:
  self_a = ast.Attribute(
    value=ast.Name(id="self", ctx=ast.Load()),
    attr=name,
    ctx=ast.Load(),
  )
  other_a = ast.Attribute(
    value=ast.Name(id="other", ctx=ast.Load()),
    attr=name,
    ctx=ast.Load(),
  )
  return self_a, other_a


def _field_lex_cmp_stmts(spec: DataclassFieldSpec) -> list[ast.stmt]:
  """``if self.f != other.f: return -1 if self.f < other.f else 1``。"""
  self_a, other_a = _self_other_attr(spec.name)
  ne_test = ast.Compare(
    left=copy.deepcopy(self_a),
    ops=[ast.NotEq()],
    comparators=[copy.deepcopy(other_a)],
  )
  lt_test = ast.Compare(
    left=copy.deepcopy(self_a),
    ops=[ast.Lt()],
    comparators=[copy.deepcopy(other_a)],
  )
  inner = ast.If(
    test=lt_test,
    body=[ast.Return(value=ast.Constant(value=-1))],
    orelse=[ast.Return(value=ast.Constant(value=1))],
  )
  ast.fix_missing_locations(inner)
  outer = ast.If(test=ne_test, body=[inner], orelse=[])
  ast.fix_missing_locations(outer)
  return [outer]


def _generate_cmp(specs: list[DataclassFieldSpec], class_name: str) -> ast.FunctionDef:
  order_specs = [s for s in specs if not s.optional]
  if not order_specs:
    raise NotImplementedError("@dataclass(order=True) 须至少有一个非 @optional 比较字段")
  body: list[ast.stmt] = []
  for spec in order_specs:
    body.extend(_field_lex_cmp_stmts(spec))
  body.append(ast.Return(value=ast.Constant(value=0)))
  fn = ast.FunctionDef(
    name="__cmp__",
    args=ast.arguments(
      posonlyargs=[],
      args=[
        ast.arg(arg="self"),
        ast.arg(arg="other", annotation=ast.Name(id="Self", ctx=ast.Load())),
      ],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=body,
    decorator_list=[copy.deepcopy(_IMMUTABLE_DEC)],
    returns=ast.Name(id="int", ctx=ast.Load()),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def _repr_has_varint(specs: list[DataclassFieldSpec]) -> bool:
  return any(
    isinstance(spec.annotation, ast.Name) and spec.annotation.id == "varint"
    for spec in specs
  )


def _repr_field_str_call(spec: DataclassFieldSpec) -> ast.expr:
  return ast.Call(
    func=ast.Name(id="str", ctx=ast.Load()),
    args=[
      ast.Attribute(
        value=ast.Name(id="self", ctx=ast.Load()),
        attr=spec.name,
        ctx=ast.Load(),
      ),
    ],
    keywords=[],
  )


def _repr_concat_expr(specs: list[DataclassFieldSpec], class_name: str) -> ast.expr:
  expr: ast.expr | None = None

  def append(part: ast.expr) -> None:
    nonlocal expr
    if expr is None:
      expr = part
    else:
      expr = ast.BinOp(left=expr, op=ast.Add(), right=part)

  append(ast.Constant(value=f"{class_name}("))
  for i, spec in enumerate(specs):
    if i > 0:
      append(ast.Constant(value=", "))
    append(ast.Constant(value=f"{spec.name}="))
    append(_repr_field_str_call(spec))
  append(ast.Constant(value=")"))
  assert expr is not None
  return expr


def _generate_repr(specs: list[DataclassFieldSpec], class_name: str) -> ast.FunctionDef:
  if _repr_has_varint(specs):
    ret_expr = _repr_concat_expr(specs, class_name)
  else:
    values: list[ast.expr] = [ast.Constant(value=f"{class_name}(")]
    for i, spec in enumerate(specs):
      if i > 0:
        values.append(ast.Constant(value=", "))
      values.append(ast.Constant(value=f"{spec.name}="))
      values.append(
        ast.FormattedValue(
          value=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr=spec.name,
            ctx=ast.Load(),
          ),
          conversion=-1,
        ),
      )
    values.append(ast.Constant(value=")"))
    ret_expr = ast.JoinedStr(values=values)
  fn = ast.FunctionDef(
    name="__repr__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=[ast.Return(value=ret_expr)],
    decorator_list=[copy.deepcopy(_IMMUTABLE_DEC)],
    returns=ast.Name(id="str", ctx=ast.Load()),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def _register_init(info: ClassInfo, init: ast.FunctionDef) -> None:
  info.inits = [init]
  info.methods.pop("__init__", None)
  info._collect_fields_from_init(init)


def _register_method(info: ClassInfo, method: ast.FunctionDef) -> None:
  info.methods[method.name] = method
  info._collect_fields(method)


def _check_native_body(qual: str, body: list[ast.stmt]) -> None:
  if is_native_function_body(body):
    return
  raise NotImplementedError(
    f"{qual}: @native 函数体须为 ...（可有 docstring；勿写 pass/return 占位实现）"
  )


def check_native_function_bodies(tr: Translator) -> None:
  """``@native`` 函数体须为 ``...``（实现由 ``codegen/*_cpp.py`` 注入）。"""
  for module_path, func in tr.module_functions:
    if not has_named_decorator(func, "native"):
      continue
    _check_native_body(f"{module_path}.{func.name}", func.body)

  for info in tr.classes.values():
    if info.is_native:
      if is_stdlib_codegen_module(info.module_path):
        continue
      for init in info.inits:
        qual = f"{info.module_path}.{info.name}.__init__"
        _check_native_body(qual, init.body)
      for method in info.iter_methods():
        qual = f"{info.module_path}.{info.name}.{method.name}"
        _check_native_body(qual, method.body)
      continue
    for method in info.methods.values():
      if not has_named_decorator(method, "native"):
        continue
      qual = f"{info.module_path}.{info.name}.{method.name}"
      _check_native_body(qual, method.body)


def expand_dataclass(tr: Translator) -> None:
  for info in tr.classes.values():
    if info.is_descriptor or info.is_protocol:
      continue
    opts = _parse_dataclass_options(info.node)
    if opts is None:
      continue
    info.is_dataclass = True
    info.dataclass_options = opts
    if opts.kw_only:
      raise NotImplementedError("@dataclass(kw_only=True) 尚未支持")
    if opts.slots:
      raise NotImplementedError("@dataclass(slots=True) 尚未支持")
    if opts.frozen and info.is_copyable:
      raise NotImplementedError(
        f"{info.name}: @copyable 与 @dataclass(frozen=True) 不能同用；"
        "frozen 字段会生成 C++ const 成员，copyable 赋值需要写入字段"
      )
    specs = _collect_dataclass_fields(info.node)
    if opts.frozen:
      for spec in specs:
        info.final_fields.add(spec.name)
    info.dataclass_field_specs = specs
    info.optional_fields = {s.name for s in specs if s.optional}
    _rewrite_class_field_decls(info.node, specs, info)
    _strip_dataclass_decorators(info.node)
    has_post_init = "__post_init__" in info.methods
    if opts.init and not info.inits:
      init = _generate_init(
        specs, info.name, call_post_init=has_post_init,
      )
      _register_init(info, init)
    elif opts.init and info.inits and has_post_init:
      raise NotImplementedError(
        f"{info.name}: 手写 __init__ 时须自行调用 self.__post_init__()，"
        "或由 @dataclass 自动生成 __init__"
      )
    if opts.eq and "__eq__" not in info.methods:
      _register_method(info, _generate_eq(specs, info.name))
    if opts.repr and "__repr__" not in info.methods and not info.repr_aliases_str:
      _register_method(info, _generate_repr(specs, info.name))
    if opts.order and "__cmp__" not in info.methods:
      _register_method(info, _generate_cmp(specs, info.name))
    ast.fix_missing_locations(info.node)
