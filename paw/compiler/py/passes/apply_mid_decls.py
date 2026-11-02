"""从 ``MidModule`` 预填 / 展开声明（expand_* 之前或之中）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from compiler.py.frontend.syntax_nodes import ObjectModel
from compiler.py.mid.nodes import (
  MidClass,
  MidEnum,
  MidFunction,
  MidModule,
  MidModuleConst,
)

if TYPE_CHECKING:
  from src.translator import Translator


def register_module_from_mid(
  tr: Translator, mid: MidModule, module_path: str
) -> int:
  """``NO_MATERIALIZE`` / 空 ``tree`` 时：MidIR → ``ClassInfo`` / 模块函数登记。

  用 ``ast_from_mid`` 单声明直构，不跑 span 物化。返回登记的类数。
  """
  from compiler.py.mid.ast_from_mid import (
    classdef_from_mid_class,
    classdef_from_mid_enum,
    stmt_from_mid_module_const,
    stmts_from_mid_function,
  )
  from src.analysis.ir import ClassInfo

  n = 0
  filename = module_path.replace("\\", "/")
  for item in mid.items:
    if isinstance(item, MidEnum):
      try:
        node = classdef_from_mid_enum(item)
      except (SyntaxError, ValueError, TypeError):
        continue
      info = ClassInfo(node, module_path)
      tr._all_class_infos.append(info)
      tr.classes[info.name] = info
      tr._register_nested_classes(info)
      n += 1
    elif isinstance(item, MidClass):
      try:
        node = classdef_from_mid_class(item, filename)
      except (SyntaxError, ValueError, TypeError):
        continue
      info = ClassInfo(node, module_path)
      tr._all_class_infos.append(info)
      tr.classes[info.name] = info
      tr._register_nested_classes(info)
      n += 1
    elif isinstance(item, MidModuleConst):
      try:
        stmt = stmt_from_mid_module_const(item)
      except (SyntaxError, ValueError, TypeError):
        continue
      if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        tr.module_constants.append((module_path, stmt))
    elif isinstance(item, MidFunction):
      try:
        stmts = stmts_from_mid_function(item, filename)
      except (SyntaxError, ValueError, TypeError):
        continue
      for stmt in stmts:
        if isinstance(stmt, ast.FunctionDef):
          tr.module_functions.append((module_path, stmt))
  return n


def _mid_module_path_norm(path: str) -> str:
  return path.replace("\\", "/").strip("/")


def _classinfo_matches_mid_module(info: object, mid: MidModule) -> bool:
  """避免同名跨模块污染（如测试 ``ContainerType`` vs ``paw.util.protocols.ContainerType``）。"""
  mp = getattr(info, "module_path", None)
  if not mp:
    return True
  return _mid_module_path_norm(str(mp)) == _mid_module_path_norm(mid.path)


def apply_mid_enum_flags(tr: Translator, mid: MidModule) -> int:
  """按 MidEnum 标记 ``ClassInfo.is_enum``；返回命中数。"""
  n = 0
  for item in mid.items:
    if not isinstance(item, MidEnum):
      continue
    info = tr.classes.get(item.name)
    if info is None or not _classinfo_matches_mid_module(info, mid):
      continue
    info.is_enum = True
    if item.flag:
      setattr(info, "enum_flag_from_mid", True)
    if item.is_type_enum:
      setattr(info, "is_enum_mro", True)
    n += 1
  return n


def apply_mid_class_flags(tr: Translator, mid: MidModule) -> int:
  """用 MidClass 对齐 ClassInfo 身份标志（与 materialize 装饰器双源）。"""
  n = 0
  for item in mid.items:
    if not isinstance(item, MidClass):
      continue
    info = tr.classes.get(item.name)
    if info is None or not _classinfo_matches_mid_module(info, mid):
      continue
    if item.is_union:
      info.is_union = True
      if item.bases_source and "base=" in item.bases_source:
        info.is_union_mro = True
    if item.is_variant and not item.is_union:
      # 模块级 ``variant`` 字段模板（非 union 内嵌套）
      info.is_variant_mixin = True
      setattr(info, "variant_from_mid", True)
    if item.is_protocol:
      info.is_protocol = True
    if item.is_mixin:
      info.is_mixin = True
    if item.is_final:
      info.is_final = True
    if item.is_native:
      info.is_native = True
    if item.object_model is ObjectModel.REF_COUNT:
      info.is_refcount = True
    if item.is_record:
      setattr(info, "is_record_from_mid", True)
      setattr(info, "record_frozen_from_mid", bool(item.is_frozen))
      setattr(info, "record_ordered_from_mid", bool(item.is_ordered))
    n += 1
  return n


def _mid_class_for_info(tr: Translator, info: object) -> MidClass | None:
  name = getattr(info, "name", None)
  mp = getattr(info, "module_path", None)
  if not name:
    return None
  mids = getattr(tr, "module_mids", None) or {}
  if mp and mp in mids:
    for item in mids[mp].items:
      if isinstance(item, MidClass) and item.name == name:
        return item
  for mid in mids.values():
    for item in mid.items:
      if isinstance(item, MidClass) and item.name == name:
        return item
  return None


def nested_variant_classdefs_from_mid(tr: Translator, info: object) -> list[ast.ClassDef] | None:
  """``MidClass.opaque_members`` 中嵌套 ``@variant class`` → ClassDef 列表。

  无可用 Mid / 无解析成功变体时返回 ``None``（调用方回退 ``info.node.body``）。
  """
  from src.analysis.ir import has_named_decorator

  item = _mid_class_for_info(tr, info)
  if item is None or not item.is_union or not item.opaque_members:
    return None
  out: list[ast.ClassDef] = []
  for mem in item.opaque_members:
    text = mem.strip()
    if not text:
      continue
    try:
      frag = ast.parse(text + "\n", mode="exec")
    except SyntaxError:
      continue
    for stmt in frag.body:
      if isinstance(stmt, ast.ClassDef) and has_named_decorator(stmt, "variant"):
        out.append(stmt)
  return out if out else None


def record_field_specs_from_mid(tr: Translator, info: object) -> list | None:
  """``MidClass.fields`` → ``DataclassFieldSpec`` 列表；不可用则 ``None``（回退 AST）。

  仅处理已结构化进 ``fields`` 的实例字段；``optional name:`` 前缀等仍在
  ``opaque_members`` 时回退 ``_collect_dataclass_fields``。
  """
  from compiler.py.mid.ast_from_mid import _type_to_legacy_annotation
  from src.analysis.ir import (
    is_const_type_annotation,
    is_optional_type_annotation,
    is_postsetter_type_annotation,
    is_property_type_annotation,
    strip_type_annotation_markers,
  )
  from src.passes.dataclass_expand import (
    DataclassFieldSpec,
    _is_classvar_annotation,
    _parse_class_default,
  )

  if not getattr(info, "is_record_from_mid", False):
    return None
  item = _mid_class_for_info(tr, info)
  if item is None or not item.is_record or not item.fields:
    return None

  specs: list = []
  for name, typ, value in item.fields:
    if not name or not name.isidentifier():
      continue
    legacy = _type_to_legacy_annotation(typ) if typ else None
    if legacy:
      try:
        annotation = ast.parse(legacy, mode="eval").body
      except SyntaxError:
        return None
    else:
      annotation = ast.Name(id="object", ctx=ast.Load())
    if _is_classvar_annotation(annotation):
      continue
    if is_const_type_annotation(annotation):
      continue
    if is_property_type_annotation(annotation):
      continue
    if is_postsetter_type_annotation(annotation):
      continue
    optional = is_optional_type_annotation(annotation)
    base_ann = strip_type_annotation_markers(annotation)
    if base_ann is None:
      raise NotImplementedError(f"{name}: 缺少类型注解")
    val_expr: ast.expr | None = None
    if value is not None and str(value).strip():
      try:
        val_expr = ast.parse(str(value).strip(), mode="eval").body
      except SyntaxError as e:
        raise ValueError(f"{item.name}.{name}: 非法默认值 {value!r}") from e
    param_def, body_init = _parse_class_default(
      val_expr, optional=optional, name=name, annotation=base_ann
    )
    specs.append(
      DataclassFieldSpec(
        name=name,
        annotation=base_ann,
        default=param_def,
        body_init=body_init,
        optional=optional,
      )
    )
  return specs if specs else None


def _parse_mid_enum_base(
  base_source: str | None,
) -> tuple[str | None, str | None]:
  """``(int64)`` / ``(ModeEnum)`` / ``(flag=True, PermFlag)`` → (scalar, parent)。"""
  if not base_source:
    return None, None
  inner = base_source.strip()
  if inner.startswith("(") and inner.endswith(")"):
    inner = inner[1:-1].strip()
  if not inner:
    return None, None
  scalar: str | None = None
  parent: str | None = None
  for part in inner.split(","):
    part = part.strip()
    if not part or "=" in part:
      continue
    if part in ("int", "int64"):
      scalar = part
    elif part.isidentifier():
      parent = part
  return scalar, parent


def _mid_enum_member_specs(
  item: MidEnum,
) -> list[tuple[str, ast.expr | None]]:
  from src.passes.enum_expand import _parse_int_value

  own_specs: list[tuple[str, ast.expr | None]] = []
  for name, val in item.members:
    if val is None or val.strip() in ("...", "Ellipsis"):
      own_specs.append((name, None))
      continue
    try:
      expr = ast.parse(val, mode="eval").body
    except SyntaxError as e:
      raise ValueError(f"{item.name}.{name}: 非法枚举值 {val!r}") from e
    if not (
      isinstance(expr, ast.Constant)
      and isinstance(expr.value, int)
      and not isinstance(expr.value, bool)
    ) and not (
      isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.USub)
    ):
      _parse_int_value(expr, item.name, name)
    own_specs.append((name, expr))
  return own_specs


def expand_enums_from_mid(tr: Translator) -> set[str]:
  """用 MidEnum 成员展开普通 ``@enum``（非 type enum / mro）。

  支持 ``base_source`` 标量底层（int/int64）与单父枚举继承；父未就绪时延后，
  最终未处理者留给 AST ``_parse_enum_layout``。
  返回已处理的类名集合；``expand_enum`` 应跳过这些类。
  """
  from src.passes.enum_expand import (
    _clear_enum_class_body,
    _resolve_enum_members,
    _underlying_cpp_for_scalar,
  )

  pending: list[tuple[MidEnum, object]] = []
  for mid in getattr(tr, "module_mids", {}).values():
    for item in mid.items:
      if not isinstance(item, MidEnum) or item.is_type_enum:
        continue
      info = tr.classes.get(item.name)
      if info is None:
        continue
      if not item.name or item.name == "_" or not item.name.isidentifier():
        continue
      pending.append((item, info))

  done: set[str] = set()
  progress = True
  while progress and pending:
    progress = False
    still: list[tuple[MidEnum, object]] = []
    for item, info in pending:
      scalar, parent_name = _parse_mid_enum_base(item.base_source)
      inherited: list = []
      if parent_name is not None:
        parent = tr.classes.get(parent_name)
        if parent is None or not parent.is_enum or not parent.enum_members:
          still.append((item, info))
          continue
        if scalar is not None:
          raise ValueError(
            f"{item.name}: 仅支持单继承（底层 int/int64 或一个 @enum）"
          )
        info.enum_underlying_cpp = parent.enum_underlying_cpp
        info.enum_parent = parent_name
        inherited = list(parent.enum_members)
        is_flag = bool(item.flag) or bool(parent.enum_is_flag)
      else:
        info.enum_parent = None
        info.enum_underlying_cpp = _underlying_cpp_for_scalar(scalar or "int")
        is_flag = bool(item.flag)

      info.is_enum = True
      info.enum_is_flag = is_flag
      info.enum_members = _resolve_enum_members(
        item.name,
        _mid_enum_member_specs(item),
        inherited,
        is_flag=is_flag,
      )
      _clear_enum_class_body(info)
      done.add(item.name)
      progress = True
    pending = still
  return done
