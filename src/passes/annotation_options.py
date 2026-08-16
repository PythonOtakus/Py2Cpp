"""``@annotation(inheritable=…, repeatable=…)`` 选项与 ``iter_*`` 实体基类 MRO 展开。"""
from __future__ import annotations

import ast
import fnmatch
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, class_base_name, has_named_decorator

if TYPE_CHECKING:
  from ..translator import Translator

ANNOTATION_DECORATOR = "annotation"


@dataclass(frozen=True)
class AnnotationOptions:
  inheritable: bool = False
  repeatable: bool = False


@dataclass(frozen=True)
class IterReflectOptions:
  public_only: bool = False
  mro: bool = False
  glob: str | None = None


def filter_iter_names(names: list[str], glob_pat: str | None) -> list[str]:
  """``glob=`` 粗筛字段/方法名（``fnmatchcase``，对齐 ``str.glob`` / ``fnmatch``）。"""
  if glob_pat is None:
    return names
  return [name for name in names if fnmatch.fnmatchcase(name, glob_pat)]


def _is_annotation_factory_decorator(dec: ast.expr) -> bool:
  if isinstance(dec, ast.Name) and dec.id == ANNOTATION_DECORATOR:
    return True
  return (
    isinstance(dec, ast.Call)
    and isinstance(dec.func, ast.Name)
    and dec.func.id == ANNOTATION_DECORATOR
  )


def parse_annotation_options(node: ast.ClassDef) -> AnnotationOptions | None:
  """``@annotation`` / ``@annotation(inheritable=…, repeatable=…)`` → 选项；非注解类 ``None``。"""
  overrides: dict[str, bool] = {}
  found = False
  for dec in node.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == ANNOTATION_DECORATOR:
      found = True
      continue
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Name):
      continue
    if dec.func.id != ANNOTATION_DECORATOR:
      continue
    found = True
    for kw in dec.keywords:
      if kw.arg is None:
        raise NotImplementedError("@annotation 不支持 **kwargs 解包")
      if kw.arg not in ("inheritable", "repeatable"):
        raise NotImplementedError(f"@annotation 不支持关键字 {kw.arg!r}")
      val = kw.value
      if not isinstance(val, ast.Constant) or not isinstance(val.value, bool):
        raise NotImplementedError(f"@annotation({kw.arg}=…) 须为 bool 常量")
      overrides[kw.arg] = val.value
  if not found:
    return None
  return AnnotationOptions(**overrides)


def annotation_options_for(classes: dict[str, ClassInfo], name: str) -> AnnotationOptions | None:
  info = classes.get(name)
  if info is None or not info.is_annotation:
    return None
  opts = info.annotation_options
  if isinstance(opts, AnnotationOptions):
    return opts
  return AnnotationOptions()


def is_skip_base_for_mro(info: ClassInfo) -> bool:
  return info.is_mixin or info.is_annotation or info.is_protocol


def walk_entity_bases(host: ClassInfo, classes: dict[str, ClassInfo]) -> list[ClassInfo]:
  """实体基类链（声明序、深度优先、去重；跳过 mixin/annotation/protocol）。"""
  out: list[ClassInfo] = []
  seen: set[str] = set()

  def walk(ci: ClassInfo) -> None:
    for base_ast in ci.node.bases:
      name = class_base_name(base_ast)
      if not name or name in seen:
        continue
      bi = classes.get(name)
      if bi is None or is_skip_base_for_mro(bi):
        continue
      seen.add(name)
      walk(bi)
      out.append(bi)

  walk(host)
  return out


def parse_self_iter_call_options(
  node: ast.expr,
  *,
  allowed: frozenset[str],
  label: str,
) -> IterReflectOptions | None:
  if not isinstance(node, ast.Call):
    return None
  if node.args:
    raise NotImplementedError(f"{label} 不支持位置实参")
  public_only = False
  mro = False
  glob_pat: str | None = None
  for kw in node.keywords:
    if kw.arg not in allowed:
      allowed_s = "、".join(f"``{k}=``" for k in sorted(allowed))
      raise NotImplementedError(f"{label} 仅支持 {allowed_s} 关键字")
    if kw.arg == "glob":
      if not isinstance(kw.value, ast.Constant) or not isinstance(kw.value.value, str):
        raise NotImplementedError(f"{label}(glob=…) 须为编译期 str 常量")
      glob_pat = kw.value.value
      continue
    if not isinstance(kw.value, ast.Constant) or not isinstance(kw.value.value, bool):
      raise NotImplementedError(f"{label}({kw.arg}=…) 须为编译期 bool 常量")
    if kw.arg in ("public_only", "publicOnly"):
      public_only = kw.value.value
    elif kw.arg == "mro":
      mro = kw.value.value
  return IterReflectOptions(public_only=public_only, mro=mro, glob=glob_pat)


def collect_iter_field_names(
  ci: ClassInfo,
  classes: dict[str, ClassInfo],
  *,
  public_only: bool,
  mro: bool,
  host_iter_field_names,
  glob: str | None = None,
) -> list[str]:
  """``iter_fields`` / ``enum_fields`` 字段名（宿主优先；``mro=True`` 时合并实体基类，同名宿主覆盖）。"""
  names = host_iter_field_names(ci, public_only=public_only)
  if mro:
    seen = set(names)
    for bi in walk_entity_bases(ci, classes):
      for fname in host_iter_field_names(bi, public_only=public_only):
        if fname not in seen:
          seen.add(fname)
          names.append(fname)
  return filter_iter_names(names, glob)


def _class_has_marker(
  ci: ClassInfo,
  marker: str,
  classes: dict[str, ClassInfo],
  *,
  mro: bool,
  inheritable: bool,
  has_decorator,
) -> bool:
  if has_decorator(ci.node, marker):
    return True
  if mro and inheritable:
    for bi in walk_entity_bases(ci, classes):
      if has_decorator(bi.node, marker):
        return True
  return False


def _annotation_decorator_names(
  decorator_list: list[ast.expr],
  classes: dict[str, ClassInfo],
) -> list[str]:
  out: list[str] = []
  for dec in decorator_list:
    name: str | None = None
    if isinstance(dec, ast.Name):
      name = dec.id
    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
      name = dec.func.id
    if name is None:
      continue
    info = classes.get(name)
    if info is not None and info.is_annotation:
      out.append(name)
  return out


def _check_marker_list_repeatable(
  markers: list[str],
  classes: dict[str, ClassInfo],
  *,
  site: str,
  symbol: str,
) -> None:
  for name, count in Counter(markers).items():
    if count <= 1:
      continue
    opts = annotation_options_for(classes, name)
    if opts is not None and not opts.repeatable:
      raise ValueError(
        f"注解 {name!r} 不可重复（repeatable=False），出现于 {site} {symbol!r}"
      )


def check_annotation_repeatable(tr: Translator) -> None:
  """``repeatable=False`` 时同一目标上不得重复同一注解类名（翻译期失败）。"""
  classes = tr.classes
  for info in classes.values():
    _check_marker_list_repeatable(
      _annotation_decorator_names(info.node.decorator_list, classes),
      classes,
      site="类",
      symbol=info.name,
    )
    for field_name, markers in info.field_annotation_markers.items():
      _check_marker_list_repeatable(
        list(markers),
        classes,
        site="字段",
        symbol=f"{info.name}.{field_name}",
      )
    for method in info.methods.values():
      _check_marker_list_repeatable(
        _annotation_decorator_names(method.decorator_list, classes),
        classes,
        site="方法",
        symbol=f"{info.name}.{method.name}",
      )
