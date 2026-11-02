"""HIR 节点（与 schema.md 同步）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from compiler.py.frontend.source import Span
from compiler.py.frontend.syntax_nodes import ObjectModel, ParamDecl, StmtSyntax

__all__ = [
  "ObjectModel",
  "HirEnumMember",
  "HirEnum",
  "HirClass",
  "HirFunction",
  "HirImport",
  "HirOpaque",
  "HirModule",
]


@dataclass
class HirEnumMember:
  name: str
  value_source: str | None
  span: Span


@dataclass
class HirEnum:
  decl_id: int
  name: str
  is_type_enum: bool
  flag: bool
  members: list[HirEnumMember]
  span: Span
  base_source: str | None = None


@dataclass
class HirClass:
  decl_id: int
  name: str
  object_model: ObjectModel
  is_final: bool
  is_record: bool
  is_frozen: bool
  is_ordered: bool
  is_lazy: bool
  is_protocol: bool
  is_mixin: bool
  is_union: bool
  is_variant: bool
  bases_source: str | None
  const_fields: list[tuple[str, str | None, str, Span]]
  fields: list[tuple[str, str | None, str, Span]]
  opaque_members: list[tuple[str, Span]]
  span: Span
  decorators_source: str = ""
  is_native: bool = False
  methods: list["HirFunction"] = field(default_factory=list)
  type_params_source: str = ""


@dataclass
class HirFunction:
  decl_id: int
  name: str
  decorators_source: str
  params_source: str
  return_source: str | None
  body_source: str
  is_async: bool
  span: Span
  is_static: bool = False
  is_native: bool = False
  is_override: bool = False
  is_final: bool = False
  is_abstract: bool = False
  is_virtual: bool = False
  is_delegate: bool = False
  is_property: bool = False
  params: list[ParamDecl] = field(default_factory=list)
  body: list[StmtSyntax] = field(default_factory=list)
  type_params_source: str = ""


@dataclass
class HirImport:
  source: str
  span: Span


@dataclass
class HirModuleConst:
  name: str
  type_name: str | None
  value_source: str
  span: Span


@dataclass
class HirOpaque:
  source: str
  span: Span


HirDecl = HirEnum | HirClass | HirFunction | HirImport | HirModuleConst | HirOpaque


@dataclass
class HirModule:
  path: str
  decls: list[HirDecl] = field(default_factory=list)
  span: Span | None = None
  diagnostics: list[str] = field(default_factory=list)
