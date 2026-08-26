"""``**kwargs: Options``：关键字映射到选项类 / 实例字段；``assign`` 为翻译期专用。

- ``def f(**kwargs: Opt)`` → ``def f(kwargs: Opt)``；调用处构造 ``Opt`` 再传入。
- ``Cls(a=1)`` 且 ``__init__`` **无** ``**kwargs`` → ``Cls()`` + ``.a = 1``（字段 / 可写 ``@property``）。
- ``Cls(a=1)`` 且 ``__init__(self, **kwargs: Opt)`` → 构造 ``Opt`` 再 ``Cls(opt)``（可带位置参数）。
- ``obj.assign(w=1)`` / ``self.assign(**opt)``：**不**生成 C++ ``assign`` 成员；调用处脱糖为字段/``set_*`` 赋值（**不支持** ``assign(opt)`` 位置传参）。
- ``inner(**kwargs)`` 转发：形参类型与目标 ``**kwargs: Opt`` 须相同 → ``inner(kwargs)``。
- ``new(w=1)`` / ``Self(w=1)``（带类型注解）：同 ``Cls(w=1)``；类内 ``new`` → ``Self()`` + 字段赋值。
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  import ast

  from ..analysis.ir import ClassInfo
  from ..translator import Translator
else:
  import ast

from ..analysis.patterns import temp_name

_ASSIGN_NAME = "assign"
# 仅翻译期识别；不注入类体、不生成 C++ 声明/定义（与容器迭代器 ``.copy_from`` 无关）
TRANSLATOR_ONLY_METHODS = frozenset({_ASSIGN_NAME, "select", "build"})

VARSTACK_TRANSLATOR_ONLY_METHODS = frozenset({"push", "pop", "top"})


def is_translator_only_method(name: str, method: ast.FunctionDef | None = None) -> bool:
  """``assign`` 调用脱糖为字段赋值；带真实方法体的 ``assign``（如 ``ListIterator``）仍生成 C++。"""
  if name not in TRANSLATOR_ONLY_METHODS:
    return False
  if method is None:
    return True
  if not method.body:
    return True
  if len(method.body) == 1:
    stmt = method.body[0]
    if isinstance(stmt, ast.Pass):
      return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
      if stmt.value.value is Ellipsis:
        return True
  return False


def is_varstack_translator_only_method(method: ast.FunctionDef) -> bool:
  """``VarStack.push`` / ``pop`` / ``top``：Python 桩，译器 ``expand_varstack`` 展开，无 C++ 成员。"""
  if method.name not in VARSTACK_TRANSLATOR_ONLY_METHODS:
    return False
  body = method.body
  if (
    body
    and isinstance(body[0], ast.Expr)
    and isinstance(body[0].value, ast.Constant)
    and isinstance(body[0].value.value, str)
  ):
    body = body[1:]
  if not body:
    return True
  if len(body) == 1 and isinstance(body[0], ast.Pass):
    return True
  return False


@dataclass(frozen=True)
class KwargsOptionsSig:
  options_class: str
  kw_param: str


def _annotation_class(ann: ast.expr | None) -> str | None:
  if isinstance(ann, ast.Name):
    return ann.id
  return None


def _kwargs_options_sig(func: ast.FunctionDef | ast.AsyncFunctionDef) -> KwargsOptionsSig | None:
  kw = func.args.kwarg
  if kw is None:
    return None
  cls = _annotation_class(kw.annotation)
  if cls is None:
    return None
  return KwargsOptionsSig(options_class=cls, kw_param=kw.arg)


def _expand_function_kwargs(func: ast.FunctionDef | ast.AsyncFunctionDef) -> KwargsOptionsSig | None:
  sig = _kwargs_options_sig(func)
  if sig is None:
    return None
  kw = func.args.kwarg
  assert kw is not None
  func.args.args.append(
    ast.arg(
      arg=kw.arg,
      annotation=ast.Name(id=sig.options_class, ctx=ast.Load()),
    )
  )
  func.args.defaults.append(
    ast.Call(func=ast.Name(id="new", ctx=ast.Load()), args=[])
  )
  func.args.kwarg = None
  ast.fix_missing_locations(func)
  return sig


def _skip_class(info: ClassInfo) -> bool:
  return (
    info.is_descriptor
    or info.is_mixin
    or info.is_annotation
    or info.is_protocol
  )


def _writable_member_names(info: ClassInfo) -> frozenset[str]:
  """``assign`` / ``Cls(kw=…)`` / ``new(kw=…)`` 可写成员：存储字段 + 带 setter 的 ``@property``。

  ``@optional`` 不进 ``__init__`` 形参，但仍可用关键字赋值（容器默认须 ``@optional``，见 **S0401**）。
  ``T @final`` 仅能在 ``__init__`` 中初始化，不可 ``assign`` / 关键字构造。
  """
  names = {n for n in info.fields if n not in info.final_fields}
  for pname, prop in info.properties.items():
    if prop.setter is not None or prop.postsetter is not None:
      names.add(pname)
  return frozenset(names)


def _matchable_member_names(info: ClassInfo) -> frozenset[str]:
  """``case new(kw=…)`` 可读槽位：存储字段 + 只读/可写 ``@property``（排除 ``__*``、栈数组）。"""
  names: set[str] = set()
  for n in info.fields:
    if n.startswith("__"):
      continue
    if _field_is_stack_array(info, n):
      continue
    names.add(n)
  for pname, prop in info.properties.items():
    if prop.getter is not None:
      names.add(pname)
  return frozenset(names)


def _validate_match_field_names(
  owner: str,
  field_names: list[str],
  allowed: frozenset[str],
  *,
  tr: Translator | None = None,
  at: ast.AST | None = None,
) -> None:
  for name in field_names:
    if name not in allowed:
      msg = f"{owner} 无字段/属性 {name!r}；case new 仅可匹配已声明可读成员"
      if tr is not None:
        from ..translation_error import raise_translation_error

        raise_translation_error(tr, at, msg)
      raise NotImplementedError(msg)


def _class_fields(
  tr: Translator,
  class_name: str,
  *,
  for_assign: bool = False,
) -> frozenset[str] | None:
  info = tr.classes.get(class_name)
  if info is None:
    return None
  if for_assign:
    names = _writable_member_names(info)
  else:
    names = set(info.fields)
    for pname, prop in info.properties.items():
      if prop.setter is not None or prop.postsetter is not None:
        names.add(pname)
  out = {
    n for n in names
    if not (n.startswith("__") or _field_is_stack_array(info, n))
  }
  if not out:
    if for_assign and info.final_fields:
      return frozenset()
    return None
  return frozenset(out)


def _field_is_stack_array(info: ClassInfo, fname: str) -> bool:
  """``kwargs`` 注入 ``assign`` 时字段类型可能尚未解析，须同时看 ``__ann__``。"""
  from ..analysis.type_pred import is_stack_array_type
  from ..analysis.ir import parse_slice_fixed_size

  from ..analysis.type_emit import field_ann_ast, field_storage_cpp

  ft = field_storage_cpp(info, fname)
  if is_stack_array_type(ft):
    return True
  ann = field_ann_ast(info, fname)
  if isinstance(ann, ast.Subscript):
    return parse_slice_fixed_size(ann.slice) is not None
  return False


def _init_kwargs_sig(info: ClassInfo) -> KwargsOptionsSig | None:
  for init in info.inits:
    sig = _kwargs_options_sig(init)
    if sig is not None:
      return sig
  return None


def _fresh_opts_var() -> str:
  return temp_name("opts")


def _param_options_sig(
  method: ast.FunctionDef | None, param_name: str,
) -> KwargsOptionsSig | None:
  if method is None:
    return None
  kw = method.args.kwarg
  if kw is not None and kw.arg == param_name:
    cls = _annotation_class(kw.annotation)
    if cls is not None:
      return KwargsOptionsSig(options_class=cls, kw_param=param_name)
  for arg in method.args.args:
    if arg.arg != param_name:
      continue
    cls = _annotation_class(arg.annotation)
    if cls is None:
      return None
    return KwargsOptionsSig(options_class=cls, kw_param=param_name)
  return None


def _validate_keywords(
  owner: str,
  keywords: list[ast.keyword],
  fields: frozenset[str],
  *,
  tr: Translator | None = None,
  at: ast.AST | None = None,
) -> None:
  for kw in keywords:
    if kw.arg is None:
      continue
    if kw.arg not in fields:
      msg = f"{owner} 无字段/属性 {kw.arg!r}；关键字仅可映射已声明成员"
      if tr is not None:
        from ..translation_error import raise_translation_error

        raise_translation_error(tr, at or kw, msg)
      raise NotImplementedError(msg)


def _assign_member(target: ast.expr, field: str, value: ast.expr) -> ast.Assign:
  return ast.Assign(
    targets=[
      ast.Attribute(
        value=copy.deepcopy(target),
        attr=field,
        ctx=ast.Store(),
      )
    ],
    value=copy.deepcopy(value),
  )


def _dataclass_default(info: ClassInfo, field: str) -> ast.expr | None:
  default = info.field_defaults.get(field)
  if default is not None:
    return default
  for spec in info.dataclass_field_specs or ():
    if spec.name == field:
      return spec.default
  return None


@dataclass(frozen=True)
class _CachedCtorClassInfo:
  source: ClassInfo
  fields: list[str]
  inits: list[ast.FunctionDef]
  final_fields: set[str]
  field_defaults: dict[str, ast.expr]
  dataclass_options: object | None
  dataclass_field_specs: list | None

  def __getattr__(self, name: str):
    return getattr(self.source, name)


def _ctor_class_info(tr: Translator, class_name: str) -> ClassInfo | _CachedCtorClassInfo | None:
  info = (
    tr._class_info_for_ref(class_name)
    or tr._lookup_class_by_cpp_or_py_name(class_name)
    or tr.classes.get(class_name)
  )
  if info is None:
    return None
  payloads = getattr(tr, "_cached_class_payloads", {})
  module_path = info.module_path.replace("\\", "/")
  payload = payloads.get((module_path, info.class_registry_key()))
  if payload is None:
    payload = payloads.get((module_path, info.name))
  if payload is None:
    return info
  return _CachedCtorClassInfo(
    source=info,
    fields=list(payload.get("fields", info.fields)),
    inits=info.inits,
    final_fields=set(payload.get("final_fields", info.final_fields)),
    field_defaults=dict(payload.get("field_defaults", info.field_defaults)),
    dataclass_options=payload.get("dataclass_options", info.dataclass_options),
    dataclass_field_specs=payload.get(
      "dataclass_field_specs", info.dataclass_field_specs,
    ),
  )


def _build_options_from_keywords(
  class_name: str,
  keywords: list[ast.keyword],
  fields: frozenset[str],
  *,
  tr: Translator | None = None,
  at: ast.AST | None = None,
) -> tuple[list[ast.stmt], ast.Name]:
  _validate_keywords(
    class_name, keywords, fields,
    tr=tr, at=at or (keywords[0] if keywords else None),
  )
  var = _fresh_opts_var()
  info = _ctor_class_info(tr, class_name) if tr is not None else None
  dataclass_opts = getattr(info, "dataclass_options", None) if info is not None else None
  is_frozen_dataclass = bool(getattr(dataclass_opts, "frozen", False))
  if info is not None and (info.final_fields or is_frozen_dataclass):
    values = {kw.arg: copy.deepcopy(kw.value) for kw in keywords if kw.arg is not None}
    args: list[ast.expr] = []
    for field in info.fields:
      value = values.get(field)
      if value is None:
        default = _dataclass_default(info, field)
        if default is None:
          break
        value = copy.deepcopy(default)
      args.append(value)
    else:
      stmt = ast.Assign(
        targets=[ast.Name(id=var, ctx=ast.Store())],
        value=ast.Call(func=ast.Name(id=class_name, ctx=ast.Load()), args=args),
      )
      ast.fix_missing_locations(stmt)
      return [stmt], ast.Name(id=var, ctx=ast.Load())
  stmts: list[ast.stmt] = [
    ast.Assign(
      targets=[ast.Name(id=var, ctx=ast.Store())],
      value=ast.Call(func=ast.Name(id=class_name, ctx=ast.Load()), args=[]),
    ),
  ]
  for kw in keywords:
    stmts.append(_assign_member(ast.Name(id=var, ctx=ast.Load()), kw.arg, kw.value))
  for s in stmts:
    ast.fix_missing_locations(s)
  return stmts, ast.Name(id=var, ctx=ast.Load())


def _ann_ctor_func(ann: ast.expr | None) -> ast.expr | None:
  """注解类型对应的显式构造 ``Callee``（保留 ``T[Args]`` 泛型实参）。"""
  match ann:
    case ast.Name(id=name):
      return ast.Name(id=name, ctx=ast.Load())
    case ast.Subscript():
      return copy.deepcopy(ann)
    case _:
      return None


def _ann_type_root_name(ann: ast.expr | None) -> str | None:
  match ann:
    case ast.Name(id=name):
      return name
    case ast.Subscript(value=ast.Name(id=name)):
      return name
    case _:
      return None


def _placeholder_expr_for_annotation(ann: ast.expr | None) -> ast.expr:
  """无 ``__init__`` 形参默认时，用于 ``Cls(…)`` 占位的字面量。"""
  match ann:
    case ast.Name(id="int"):
      return ast.Constant(value=0)
    case ast.Name(id="float"):
      return ast.Constant(value=0.0)
    case ast.Name(id="bool"):
      return ast.Constant(value=False)
    case ast.Name(id="str"):
      return ast.Constant(value="")
    case ast.Name(id="long"):
      return ast.Call(
        func=ast.Name(id="long", ctx=ast.Load()),
        args=[ast.Constant(value="")],
        keywords=[],
      )
    case _:
      ctor = _ann_ctor_func(ann)
      if ctor is not None:
        return ast.Call(func=ctor, args=[], keywords=[])
      return ast.Constant(value=0)


def _sanitize_ctor_arg_expr(expr: ast.expr, ann: ast.expr | None) -> ast.expr:
  """``Cls(…)`` 实参位勿嵌套 ``new()``（codegen 无类型上下文）；改为显式 ``Ann()``。"""
  if not (
    isinstance(expr, ast.Call)
    and isinstance(expr.func, ast.Name)
    and expr.func.id == "new"
  ):
    return copy.deepcopy(expr)
  ctor = _ann_ctor_func(ann)
  if ctor is None:
    return _placeholder_expr_for_annotation(ann)
  return ast.Call(
    func=ctor,
    args=[copy.deepcopy(a) for a in expr.args],
    keywords=[copy.deepcopy(kw) for kw in expr.keywords],
  )


def new_ctor_arg_exprs_from_init(call: ast.Call, init: ast.FunctionDef) -> list[ast.expr]:
  """将 ``new(pos…, kw=…)`` 对齐目标 ``__init__`` 形参表，合并形参默认。"""
  params = list(init.args.args)
  if params and params[0].arg == "self":
    params = params[1:]
  defaults = list(init.args.defaults)
  n_def = len(defaults)
  n_pad = len(params) - n_def
  resolved: list[ast.expr] = []
  for i, param in enumerate(params):
    if i >= n_pad:
      resolved.append(
        _sanitize_ctor_arg_expr(defaults[i - n_pad], param.annotation)
      )
    else:
      resolved.append(_placeholder_expr_for_annotation(param.annotation))
  for i, arg in enumerate(call.args):
    if i < len(resolved):
      resolved[i] = copy.deepcopy(arg)
  kw_map = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}
  for i, param in enumerate(params):
    if param.arg in kw_map:
      resolved[i] = copy.deepcopy(kw_map[param.arg])
  return resolved


def _default_ctor_args(tr: Translator, class_name: str) -> list[ast.expr]:
  """``new(kw=…)`` 脱糖为 ``Cls(占位实参…)`` + 字段赋值；占位与 ``__init__`` 形参默认对齐。"""
  info = tr.classes.get(class_name)
  if info is None:
    return []
  if info.inits:
    init = info.inits[0]
    raw = init.args.args
    params = raw[1:] if raw and raw[0].arg == "self" else list(raw)
    defaults = list(init.args.defaults)
    n_def = len(defaults)
    n_pad = len(params) - n_def
    out: list[ast.expr] = []
    for i, param in enumerate(params):
      if i >= n_pad:
        out.append(_sanitize_ctor_arg_expr(defaults[i - n_pad], param.annotation))
      else:
        out.append(_placeholder_expr_for_annotation(param.annotation))
    return out
  if info.is_dataclass:
    from .dataclass_expand import _collect_dataclass_fields

    specs = _collect_dataclass_fields(info.node)
    out = []
    for spec in specs:
      if spec.optional or spec.body_init is not None:
        continue
      out.append(_placeholder_expr_for_annotation(spec.annotation))
    return out
  return []


def _bind_opts_var(
  var: str,
  value: ast.expr,
  *,
  annotation: ast.expr | None = None,
) -> ast.stmt:
  target = ast.Name(id=var, ctx=ast.Store())
  if annotation is not None:
    return ast.AnnAssign(
      target=target,
      annotation=copy.deepcopy(annotation),
      value=value,
      simple=0,
    )
  return ast.Assign(targets=[target], value=value)


def _build_instance_ctor_field_keywords(
  tr: Translator,
  class_name: str,
  positional: list[ast.expr],
  keywords: list[ast.keyword],
  fields: frozenset[str],
  *,
  use_self: bool = False,
  at: ast.AST | None = None,
  var_annotation: ast.expr | None = None,
) -> tuple[list[ast.stmt], ast.Name]:
  """``Cls(…)`` / ``Self(…)`` 后对实例字段（或 property）赋值（非空构造实参见 ``_default_ctor_args``）。

  关键字若均可映射到 ``__init__`` 形参（含 ``@dataclass(frozen=True)`` 的 const 字段），
  则并入构造实参，避免占位 ``0`` 对 ``str`` 非法，也避免对 const 事后赋值。
  """
  _validate_keywords(
    class_name, keywords, fields,
    tr=tr, at=at or (keywords[0] if keywords else None),
  )
  ctor = ast.Name(id="Self" if use_self else class_name, ctx=ast.Load())
  var = _fresh_opts_var()
  info = _ctor_class_info(tr, class_name)
  kw_names = {kw.arg for kw in keywords if kw.arg is not None}
  final = frozenset(info.final_fields) if info is not None else frozenset()
  dataclass_opts = getattr(info, "dataclass_options", None) if info is not None else None
  is_frozen_dataclass = bool(getattr(dataclass_opts, "frozen", False))
  if info is not None and (final or is_frozen_dataclass) and keywords:
    values: dict[str, ast.expr] = {}
    for field, value in zip(info.fields, positional):
      values[field] = copy.deepcopy(value)
    for kw in keywords:
      if kw.arg is not None:
        values[kw.arg] = copy.deepcopy(kw.value)
    args: list[ast.expr] = []
    for field in info.fields:
      value = values.get(field)
      if value is None:
        default = _dataclass_default(info, field)
        if default is None:
          break
        value = copy.deepcopy(default)
      args.append(value)
    else:
      stmt = _bind_opts_var(
        var,
        ast.Call(func=ctor, args=args, keywords=[]),
        annotation=var_annotation,
      )
      ast.fix_missing_locations(stmt)
      return [stmt], ast.Name(id=var, ctx=ast.Load())
  init = (
    info.inits[0]
    if info is not None and info.inits
    else info.methods.get("__init__") if info is not None else None
  )
  init_params: set[str] = set()
  if init is not None:
    raw = init.args.args
    params = raw[1:] if raw and raw[0].arg == "self" else list(raw)
    init_params = {p.arg for p in params}
  if init is not None and keywords:
    init_kws = [kw for kw in keywords if kw.arg in init_params]
    post_kws = [kw for kw in keywords if kw.arg not in init_params]
    if init_kws and all(kw.arg in fields for kw in post_kws):
      fake = ast.Call(
        func=ctor,
        args=[copy.deepcopy(a) for a in positional],
        keywords=[copy.deepcopy(kw) for kw in init_kws],
      )
      ctor_args = new_ctor_arg_exprs_from_init(fake, init)
      stmts: list[ast.stmt] = [
        _bind_opts_var(
          var,
          ast.Call(func=ctor, args=ctor_args, keywords=[]),
          annotation=var_annotation,
        ),
      ]
      target = ast.Name(id=var, ctx=ast.Load())
      for kw in post_kws:
        if kw.arg in final:
          from ..translation_error import raise_translation_error

          raise_translation_error(
            tr,
            at or kw,
            f"{class_name}.{kw.arg}: frozen/final 字段不可在构造后赋值；"
            "请将该关键字并入构造或勿与可写字段混用同一 Cls(kw=…) 调用",
          )
        stmts.append(_assign_member(target, kw.arg, kw.value))
      for s in stmts:
        ast.fix_missing_locations(s)
      return stmts, ast.Name(id=var, ctx=ast.Load())
  if init is not None and kw_names and kw_names <= init_params:
    fake = ast.Call(
      func=ctor,
      args=[copy.deepcopy(a) for a in positional],
      keywords=[copy.deepcopy(kw) for kw in keywords],
    )
    ctor_args = new_ctor_arg_exprs_from_init(fake, init)
    stmts: list[ast.stmt] = [
      _bind_opts_var(
        var,
        ast.Call(func=ctor, args=ctor_args, keywords=[]),
        annotation=var_annotation,
      ),
    ]
    for s in stmts:
      ast.fix_missing_locations(s)
    return stmts, ast.Name(id=var, ctx=ast.Load())
  ctor_args = [copy.deepcopy(a) for a in positional]
  if not ctor_args:
    ctor_args = _default_ctor_args(tr, class_name)
  if var_annotation is None and info is not None and info.is_dataclass and not ctor_args:
    var_annotation = ast.Name(id="Self" if use_self else class_name)
  if var_annotation is not None:
    init_value: ast.expr = ast.Call(
      func=ast.Name(id="new", ctx=ast.Load()),
      args=[],
      keywords=[],
    )
  else:
    init_value = ast.Call(
      func=ctor,
      args=ctor_args,
    )
  stmts = [
    _bind_opts_var(
      var,
      init_value,
      annotation=var_annotation,
    ),
  ]
  target = ast.Name(id=var, ctx=ast.Load())
  for kw in keywords:
    if kw.arg in final:
      from ..translation_error import raise_translation_error

      raise_translation_error(
        tr,
        at or kw,
        f"{class_name}.{kw.arg}: frozen/final 字段不可在构造后赋值；"
        "请将该关键字并入构造或勿与可写字段混用同一 Cls(kw=…) 调用",
      )
    stmts.append(_assign_member(target, kw.arg, kw.value))
  for s in stmts:
    ast.fix_missing_locations(s)
  return stmts, ast.Name(id=var, ctx=ast.Load())


class _CallExpander:
  def __init__(
    self,
    tr: Translator,
    *,
    func_sigs: dict[tuple[str, ...], KwargsOptionsSig],
    init_sigs: dict[tuple[str, ...], KwargsOptionsSig | None],
    module_path: str,
    class_name: str | None = None,
    method: ast.FunctionDef | None = None,
  ) -> None:
    self._tr = tr
    self._func_sigs = func_sigs
    self._init_sigs = init_sigs
    self._module_path = module_path
    self._class_name = class_name
    self._method = method

  def _ann_type_name(self, ann: ast.expr | None) -> str | None:
    return _ann_type_root_name(ann)

  def _local_var_class(self, name: str) -> str | None:
    if self._method is None:
      return None
    for arg in self._method.args.args:
      if arg.arg == name:
        return self._ann_type_name(arg.annotation)
    for stmt in self._method.body:
      if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        if stmt.target.id == name:
          return self._ann_type_name(stmt.annotation)
    return None

  def _resolve_class_name(self, name: str | None) -> str | None:
    if name == "Self" and self._class_name:
      return self._class_name
    return name

  def _method_return_class(self) -> str | None:
    if self._method is None or self._method.returns is None:
      return None
    return self._resolve_class_name(self._ann_type_name(self._method.returns))

  def _call_param_class_name(self, call: ast.Call, arg_index: int) -> str | None:
    """``obj.method(..., bundle, ...)`` 第 ``arg_index`` 个位置参数的类型名。"""
    match call.func:
      case ast.Attribute(attr=meth, value=recv):
        cls = self._receiver_class_name(recv)
      case _:
        return None
    if cls is None:
      return None
    info = self._tr.classes.get(cls)
    if info is None:
      return None
    fn_def = info.methods.get(meth)
    if fn_def is None:
      return None
    raw = fn_def.args.args
    params = raw[1:] if raw and raw[0].arg == "self" else list(raw)
    if arg_index >= len(params):
      return None
    return self._ann_type_name(params[arg_index].annotation)

  def _try_rewrite_new_from_callee_param(
    self, call: ast.Call, arg_index: int, arg: ast.expr,
  ) -> tuple[list[ast.stmt], ast.expr]:
    if not (
      isinstance(arg, ast.Call)
      and isinstance(arg.func, ast.Name)
      and arg.func.id == "new"
      and arg.keywords
    ):
      return [], arg
    cls = self._call_param_class_name(call, arg_index)
    if cls is None:
      return [], arg
    got = self._try_rewrite_typed_ctor(arg, cls)
    if got is None:
      return [], arg
    pre, var = got
    return pre, var

  def _try_rewrite_typed_ctor(
    self, node: ast.Call, cls: str,
    *,
    var_annotation: ast.expr | None = None,
  ) -> tuple[list[ast.stmt], ast.Name] | None:
    if not node.keywords:
      return None
    cls = self._resolve_class_name(cls) or cls
    fields = _class_fields(self._tr, cls, for_assign=False)
    if fields is None:
      return None
    use_self = False
    match node.func:
      case ast.Name(id="Self"):
        if self._class_name != cls:
          raise NotImplementedError(
            "Self(kw=…) 仅用于当前类，且类型注解须与类名一致"
          )
        use_self = True
      case ast.Name(id="new"):
        use_self = self._class_name == cls
      case _:
        return None
    return _build_instance_ctor_field_keywords(
      self._tr,
      cls,
      list(node.args),
      node.keywords,
      fields,
      use_self=use_self,
      at=node,
      var_annotation=var_annotation,
    )

  def _try_rewrite_kwargs_forward(
    self, node: ast.Call,
  ) -> tuple[list[ast.stmt], ast.Call] | None:
    if not node.keywords:
      return None
    unpack = [kw for kw in node.keywords if kw.arg is None]
    if not unpack:
      return None
    if len(unpack) != 1 or len(node.keywords) != 1:
      raise NotImplementedError(
        "仅支持单个 **name 转发，且不能与显式关键字混用"
      )
    if not isinstance(unpack[0].value, ast.Name):
      raise NotImplementedError("**kwargs 转发仅支持 **变量名")
    src_name = unpack[0].value.id
    src_sig = _param_options_sig(self._method, src_name)
    if src_sig is None:
      raise NotImplementedError(
        f"{src_name!r} 不是 Options 形参，不能用于 ** 转发"
      )
    callee_sig = self._lookup_func_sig(node.func)
    if callee_sig is None:
      match node.func:
        case ast.Name(id=class_name):
          init_sig = self._init_sigs.get((self._module_path, class_name))
          if init_sig is None:
            return None
          callee_sig = init_sig
        case _:
          return None
    if src_sig.options_class != callee_sig.options_class:
      raise NotImplementedError(
        f"**kwargs 转发类型须一致：{src_sig.options_class} → "
        f"{callee_sig.options_class}"
      )
    new_call = ast.Call(
      func=copy.deepcopy(node.func),
      args=[copy.deepcopy(a) for a in node.args]
      + [ast.Name(id=src_name, ctx=ast.Load())],
      keywords=[],
    )
    ast.copy_location(new_call, node)
    return [], new_call

  def _receiver_class_name(self, recv: ast.expr) -> str | None:
    match recv:
      case ast.Name(id="self") if self._class_name:
        return self._class_name
      case ast.Name(id=name):
        return self._local_var_class(name)
      case _:
        return None

  def _receiver_fields(self, recv: ast.expr) -> frozenset[str] | None:
    cls = self._receiver_class_name(recv)
    if cls is None:
      return None
    return _class_fields(self._tr, cls, for_assign=True)

  def _assign_from_options_var(
    self, recv: ast.expr, src_name: str, opt_class: str, recv_fields: frozenset[str],
  ) -> list[ast.stmt] | None:
    opt_fields = _class_fields(self._tr, opt_class, for_assign=True)
    if opt_fields is None:
      return None
    common = sorted(recv_fields & opt_fields)
    if not common:
      raise NotImplementedError(
        f"{opt_class} 与接收方无共有字段，不能用 assign(**{src_name})"
      )
    src = ast.Name(id=src_name, ctx=ast.Load())
    stmts = [
      _assign_member(
        recv,
        fname,
        ast.Attribute(value=copy.deepcopy(src), attr=fname, ctx=ast.Load()),
      )
      for fname in common
    ]
    for s in stmts:
      ast.fix_missing_locations(s)
    return stmts

  def _try_rewrite_receiver_assign(self, node: ast.Call) -> list[ast.stmt] | None:
    if not (
      isinstance(node.func, ast.Attribute)
      and node.func.attr == _ASSIGN_NAME
    ):
      return None
    recv = node.func.value
    if node.args:
      raise NotImplementedError(
        "assign 不支持位置参数；请用 obj.assign(x=…) 或 obj.assign(**opt)"
      )
    fields = self._receiver_fields(recv)
    if fields is None:
      return None
    # ``self.assign(**opts)``：从 Options 形参解包到实例字段
    if len(node.keywords) == 1:
      kw = node.keywords[0]
      if kw.arg is None and isinstance(kw.value, ast.Name):
        src_name = kw.value.id
        src_sig = _param_options_sig(self._method, src_name)
        if src_sig is not None:
          return self._assign_from_options_var(
            recv, src_name, src_sig.options_class, fields,
          )
    if not node.keywords:
      return None
    if any(kw.arg is None for kw in node.keywords):
      return None
    _validate_keywords(
      "assign", node.keywords, fields, tr=self._tr, at=node,
    )
    stmts = [
      _assign_member(recv, kw.arg, kw.value) for kw in node.keywords
    ]
    for s in stmts:
      ast.fix_missing_locations(s)
    return stmts

  def _lookup_func_sig(self, func: ast.expr) -> KwargsOptionsSig | None:
    match func:
      case ast.Name(id=name):
        return self._func_sigs.get((self._module_path, name))
      case ast.Attribute(value=ast.Name(id="self"), attr=meth):
        if self._class_name is None:
          return None
        return self._func_sigs.get((self._module_path, self._class_name, meth))
      case _:
        return None

  def _rewrite_class_ctor(
    self, node: ast.Call, class_name: str,
  ) -> tuple[list[ast.stmt], ast.expr] | None:
    if not node.keywords:
      return None
    fields = _class_fields(self._tr, class_name, for_assign=False)
    if fields is None:
      return None
    init_sig = self._init_sigs.get((self._module_path, class_name))
    if init_sig is not None:
      pre, var = _build_options_from_keywords(
        init_sig.options_class,
        node.keywords,
        _class_fields(self._tr, init_sig.options_class, for_assign=False) or fields,
        tr=self._tr,
        at=node,
      )
      args = [copy.deepcopy(a) for a in node.args]
      args.append(var)
      call = ast.Call(
        func=ast.Name(id=class_name, ctx=ast.Load()),
        args=args,
        keywords=[],
      )
      ast.copy_location(call, node)
      return pre, call
    pre, inst = _build_instance_ctor_field_keywords(
      self._tr,
      class_name,
      list(node.args),
      node.keywords,
      fields,
      at=node,
    )
    return pre, inst

  def _try_rewrite_call(
    self, node: ast.Call,
  ) -> tuple[list[ast.stmt], ast.expr] | None:
    fwd = self._try_rewrite_kwargs_forward(node)
    if fwd is not None:
      return fwd
    if not node.keywords:
      return None
    match node.func:
      case ast.Name(id=class_name) if class_name in self._tr.classes:
        return self._rewrite_class_ctor(node, class_name)
      case _:
        sig = self._lookup_func_sig(node.func)
        if sig is None:
          return None
        opt_fields = _class_fields(self._tr, sig.options_class, for_assign=True)
        if opt_fields is None:
          raise NotImplementedError(
            f"未找到 **kwargs 注解类 {sig.options_class!r}"
          )
        pre, var = _build_options_from_keywords(
          sig.options_class, node.keywords, opt_fields,
          tr=self._tr, at=node,
        )
        new_args = [copy.deepcopy(a) for a in node.args] + [var]
        new_call = ast.Call(
          func=copy.deepcopy(node.func),
          args=new_args,
          keywords=[],
        )
        ast.copy_location(new_call, node)
        return pre, new_call

  def _flatten_call(self, call: ast.Call) -> tuple[list[ast.stmt], ast.expr | None, bool]:
    assign_stmts = self._try_rewrite_receiver_assign(call)
    if assign_stmts is not None:
      return assign_stmts, None, True
    pre: list[ast.stmt] = []
    new_args: list[ast.expr] = []
    changed = False
    for arg in call.args:
      apre, new_arg, arg_changed = self._flatten_expr(arg)
      pre.extend(apre)
      new_args.append(new_arg)
      changed = changed or arg_changed
    resolved_args: list[ast.expr] = []
    for i, arg in enumerate(new_args):
      apre, arg_expr = self._try_rewrite_new_from_callee_param(call, i, arg)
      pre.extend(apre)
      resolved_args.append(arg_expr)
      changed = changed or bool(apre)
    new_args = resolved_args
    flat = ast.Call(
      func=call.func,
      args=new_args,
      keywords=list(call.keywords),
    )
    ast.copy_location(flat, call)
    got = self._try_rewrite_call(flat)
    if got is None:
      return pre, flat, changed
    kw_pre, new_expr = got
    return pre + kw_pre, new_expr, True

  def _flatten_expr(self, expr: ast.expr) -> tuple[list[ast.stmt], ast.expr | None, bool]:
    match expr:
      case ast.Call() as call:
        return self._flatten_call(call)
      case ast.Await(value=value):
        pre, new_val, changed = self._flatten_expr(value)
        if not pre and not changed:
          return [], expr, False
        out = ast.Await(value=new_val)
        ast.copy_location(out, expr)
        return pre, out, True
      case ast.YieldFrom(value=value):
        pre, new_val, changed = self._flatten_expr(value)
        if not pre and not changed:
          return [], expr, False
        out = ast.YieldFrom(value=new_val)
        ast.copy_location(out, expr)
        return pre, out, True
      case _:
        return [], expr, False

  def _flatten_stmt(self, stmt: ast.stmt) -> list[ast.stmt]:
    match stmt:
      case ast.Assign(targets, value):
        pre, new_val, changed = self._flatten_expr(value)
        if not pre and not changed:
          return [stmt]
        return pre + [ast.Assign(targets=targets, value=new_val)]
      case ast.AnnAssign(target, annotation, value, simple):
        if value is None:
          return [stmt]
        cls = self._resolve_class_name(self._ann_type_name(annotation))
        if cls is not None and isinstance(value, ast.Call):
          got = self._try_rewrite_typed_ctor(
            value, cls, var_annotation=annotation,
          )
          if got is not None:
            pre, new_val = got
            return pre + [
              ast.AnnAssign(
                target=target,
                annotation=annotation,
                value=new_val,
                simple=simple,
              )
            ]
        pre, new_val, changed = self._flatten_expr(value)
        if not pre and not changed:
          return [stmt]
        return pre + [
          ast.AnnAssign(
            target=target,
            annotation=annotation,
            value=new_val,
            simple=simple,
          )
        ]
      case ast.Return(value=value) if value is not None:
        cls = self._method_return_class()
        ret_ann = self._method.returns if self._method is not None else None
        if cls is not None and isinstance(value, ast.Call):
          got = self._try_rewrite_typed_ctor(
            value, cls, var_annotation=ret_ann,
          )
          if got is not None:
            pre, new_val = got
            return pre + [ast.Return(value=new_val)]
        pre, new_val, changed = self._flatten_expr(value)
        if not pre and not changed:
          return [stmt]
        return pre + [ast.Return(value=new_val)]
      case ast.Expr(value=value):
        pre, new_val, changed = self._flatten_expr(value)
        if new_val is None:
          return pre
        if not pre and not changed:
          return [stmt]
        return pre + [ast.Expr(value=new_val)]
      case ast.If(test=test, body=body, orelse=orelse):
        tpre, new_test, _ = self._flatten_expr(test)
        out = tpre
        out.append(
          ast.If(
            test=new_test,
            body=self._flatten_body(body),
            orelse=self._flatten_body(orelse),
          )
        )
        return out
      case ast.While(test=test, body=body, orelse=orelse):
        tpre, new_test, _ = self._flatten_expr(test)
        out = tpre
        out.append(
          ast.While(
            test=new_test,
            body=self._flatten_body(body),
            orelse=self._flatten_body(orelse),
          )
        )
        return out
      case ast.For(target=target, iter=iter_, body=body, orelse=orelse):
        ipre, new_iter, _ = self._flatten_expr(iter_)
        out = ipre
        out.append(
          ast.For(
            target=target,
            iter=new_iter,
            body=self._flatten_body(body),
            orelse=self._flatten_body(orelse),
          )
        )
        return out
      case ast.FunctionDef() as fn:
        child = _CallExpander(
          self._tr,
          func_sigs=self._func_sigs,
          init_sigs=self._init_sigs,
          module_path=self._module_path,
          class_name=self._class_name,
          method=fn,
        )
        new_body = child._flatten_body(fn.body)
        if new_body is fn.body:
          return [stmt]
        fn = copy.deepcopy(fn)
        fn.body = new_body
        ast.fix_missing_locations(fn)
        return [fn]
      case ast.AsyncFunctionDef() as fn:
        child = _CallExpander(
          self._tr,
          func_sigs=self._func_sigs,
          init_sigs=self._init_sigs,
          module_path=self._module_path,
          class_name=self._class_name,
          method=fn,
        )
        new_body = child._flatten_body(fn.body)
        if new_body is fn.body:
          return [stmt]
        fn = copy.deepcopy(fn)
        fn.body = new_body
        ast.fix_missing_locations(fn)
        return [fn]
      case ast.ClassDef() as cls:
        child = _CallExpander(
          self._tr,
          func_sigs=self._func_sigs,
          init_sigs=self._init_sigs,
          module_path=self._module_path,
          class_name=cls.name,
        )
        new_body = child._flatten_body(cls.body)
        if new_body is cls.body:
          return [stmt]
        cls = copy.deepcopy(cls)
        cls.body = new_body
        ast.fix_missing_locations(cls)
        return [cls]
      case _:
        return [stmt]

  def _flatten_body(self, body: list[ast.stmt]) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for stmt in body:
      out.extend(self._flatten_stmt(stmt))
    return out


def _collect_func_sigs(tr: Translator) -> dict[tuple[str, ...], KwargsOptionsSig]:
  sigs: dict[tuple[str, ...], KwargsOptionsSig] = {}
  for module_path, func in tr.module_functions:
    sig = _kwargs_options_sig(func)
    if sig is not None:
      sigs[(module_path, func.name)] = sig
  for info in tr.classes.values():
    for method in info.methods.values():
      sig = _kwargs_options_sig(method)
      if sig is not None:
        sigs[(info.module_path, info.name, method.name)] = sig
    for init in info.inits:
      sig = _kwargs_options_sig(init)
      if sig is not None:
        sigs[(info.module_path, info.name, init.name)] = sig
  for module_path, tree in tr.module_asts.items():
    for stmt in tree.body:
      if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        sig = _kwargs_options_sig(stmt)
        if sig is not None:
          sigs[(module_path, stmt.name)] = sig
      elif isinstance(stmt, ast.ClassDef):
        for inner in stmt.body:
          if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = _kwargs_options_sig(inner)
            if sig is not None:
              sigs[(module_path, stmt.name, inner.name)] = sig
  return sigs


def _collect_init_sigs(tr: Translator) -> dict[tuple[str, ...], KwargsOptionsSig | None]:
  out: dict[tuple[str, ...], KwargsOptionsSig | None] = {}
  for info in tr.classes.values():
    if _skip_class(info):
      continue
    out[(info.module_path, info.name)] = _init_kwargs_sig(info)
  return out


def _expand_defs(tr: Translator, sigs: dict[tuple[str, ...], KwargsOptionsSig]) -> None:
  for module_path, func in tr.module_functions:
    key = (module_path, func.name)
    if key in sigs:
      _expand_function_kwargs(func)
  for info in tr.classes.values():
    for method in list(info.methods.values()):
      key = (info.module_path, info.name, method.name)
      if key in sigs:
        _expand_function_kwargs(method)
    for init in info.inits:
      key = (info.module_path, info.name, init.name)
      if key in sigs:
        _expand_function_kwargs(init)
  for module_path, tree in tr.module_asts.items():
    for stmt in tree.body:
      if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        key = (module_path, stmt.name)
        if key in sigs:
          _expand_function_kwargs(stmt)
      elif isinstance(stmt, ast.ClassDef):
        for inner in stmt.body:
          if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            key = (module_path, stmt.name, inner.name)
            if key in sigs:
              _expand_function_kwargs(inner)


def _expand_all_call_sites(
  tr: Translator,
  func_sigs: dict[tuple[str, ...], KwargsOptionsSig],
  init_sigs: dict[tuple[str, ...], KwargsOptionsSig | None],
) -> None:
  for module_path, tree in tr.module_asts.items():
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(module_path):
      continue
    exp = _CallExpander(
      tr, func_sigs=func_sigs, init_sigs=init_sigs, module_path=module_path,
    )
    tree.body = exp._flatten_body(tree.body)
    ast.fix_missing_locations(tree)
  for module_path, func in tr.module_functions:
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(module_path):
      continue
    exp = _CallExpander(
      tr,
      func_sigs=func_sigs,
      init_sigs=init_sigs,
      module_path=module_path,
      method=func,
    )
    func.body = exp._flatten_body(func.body)
    ast.fix_missing_locations(func)
  for info in tr.classes.values():
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(info.module_path):
      continue
    exp = _CallExpander(
      tr,
      func_sigs=func_sigs,
      init_sigs=init_sigs,
      module_path=info.module_path,
      class_name=info.name,
    )
    for method in info.methods.values():
      mexp = _CallExpander(
        tr,
        func_sigs=func_sigs,
        init_sigs=init_sigs,
        module_path=info.module_path,
        class_name=info.name,
        method=method,
      )
      method.body = mexp._flatten_body(method.body)
      ast.fix_missing_locations(method)
    for init in info.inits:
      iexp = _CallExpander(
        tr,
        func_sigs=func_sigs,
        init_sigs=init_sigs,
        module_path=info.module_path,
        class_name=info.name,
        method=init,
      )
      init.body = iexp._flatten_body(init.body)
      ast.fix_missing_locations(init)


def expand_kwargs_options(tr: Translator) -> None:
  func_sigs = _collect_func_sigs(tr)
  init_sigs = _collect_init_sigs(tr)
  _expand_defs(tr, func_sigs)
  _expand_all_call_sites(tr, func_sigs, init_sigs)
