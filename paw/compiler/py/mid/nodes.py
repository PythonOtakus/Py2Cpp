"""MidIR 节点。"""
from __future__ import annotations

from dataclasses import dataclass, field

from compiler.py.frontend.source import Span
from compiler.py.frontend.syntax_nodes import ObjectModel, ParamDecl, StmtSyntax


@dataclass
class MidEnum:
  decl_id: int
  name: str
  is_type_enum: bool
  flag: bool
  members: list[tuple[str, str | None]]
  span: Span
  base_source: str | None = None


@dataclass
class MidClass:
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
  const_fields: list[tuple[str, str | None, str]]
  fields: list[tuple[str, str | None, str]]
  opaque_members: list[str]
  span: Span
  decorators_source: str = ""
  is_native: bool = False
  methods: list["MidFunction"] = field(default_factory=list)
  type_params_source: str = ""


@dataclass
class MidFunction:
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
class MidImport:
  source: str
  span: Span


@dataclass
class MidModuleConst:
  name: str
  type_name: str | None
  value_source: str
  span: Span


@dataclass
class MidOpaque:
  source: str
  span: Span


MidItem = MidEnum | MidClass | MidFunction | MidImport | MidModuleConst | MidOpaque


@dataclass
class MidModule:
  path: str
  items: list[MidItem] = field(default_factory=list)
  span: Span | None = None
  diagnostics: list[str] = field(default_factory=list)
