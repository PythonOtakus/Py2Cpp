"""Syntax AST 节点（与 schema 同步）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Union

from .source import Span


class ObjectModel(Enum):
  VALUE = auto()
  REF_COUNT = auto()


@dataclass
class NameTypeSyntax:
  name: str
  span: Span


@dataclass
class GenericApplyTypeSyntax:
  head: "TypeSyntax"
  arguments: list["TypeSyntax"]
  span: Span


@dataclass
class ReferenceTypeSyntax:
  inner: "TypeSyntax"
  span: Span


@dataclass
class NullableTypeSyntax:
  inner: "TypeSyntax"
  span: Span


@dataclass
class TupleTypeSyntax:
  items: list["TypeSyntax"]
  trailing_comma: bool
  span: Span


@dataclass
class ParenthesizedTypeSyntax:
  inner: "TypeSyntax"
  span: Span


@dataclass
class CallableTypeSyntax:
  """箭头类型。

  - ``is_py_callable=False``：裸 ``(T)->R`` / ``T->R`` ≡ C 函数指针（旧 ``Function[[…],R]``）
  - ``is_py_callable=True``：``Callable[(T)->R]`` ≡ PyCallable 槽（旧 ``Callable[[…],R]``）
  """
  parameter_types: list["TypeSyntax"]
  return_type: "TypeSyntax"
  span: Span
  is_py_callable: bool = False


@dataclass
class LazyTypeSyntax:
  """参数求值策略表面 ``lazy T`` / ``lazy ref T``（非通用 Lazy 值类型）。"""
  inner: "TypeSyntax"
  span: Span


@dataclass
class TypeAttrSyntax:
  """类型后置标记 ``@Name`` / ``@Name(...)``。"""
  name: str
  args_source: str | None
  span: Span


@dataclass
class AttributedTypeSyntax:
  """``T @Meta`` / ``T @Meta(...)``；与表达式 ``a @ b`` 分节点。"""
  inner: "TypeSyntax"
  attributes: list[TypeAttrSyntax]
  span: Span


@dataclass
class UnionTypeSyntax:
  """类型并 ``A | B | C``（与表达式按位或分叉；仅出现在类型位置）。"""
  options: list["TypeSyntax"]
  span: Span


@dataclass
class AttributeTypeSyntax:
  """类型属性 ``T.Attr`` / ``Generic[T].Attr``（≠ 表达式 ``AttributeExpr``）。"""
  inner: "TypeSyntax"
  attr: str
  span: Span


TypeSyntax = Union[
  NameTypeSyntax,
  GenericApplyTypeSyntax,
  ReferenceTypeSyntax,
  NullableTypeSyntax,
  TupleTypeSyntax,
  ParenthesizedTypeSyntax,
  CallableTypeSyntax,
  LazyTypeSyntax,
  AttributedTypeSyntax,
  UnionTypeSyntax,
  AttributeTypeSyntax,
]


@dataclass
class ConstField:
  name: str
  type_syntax: TypeSyntax | None
  value_source: str
  span: Span


@dataclass
class FieldDecl:
  """类体实例字段 ``name: T [= v]``（结构化，勿进 OpaqueMember）。"""
  name: str
  type_syntax: TypeSyntax | None
  value_source: str
  span: Span


@dataclass
class OpaqueMember:
  source: str
  span: Span


@dataclass
class EnumMember:
  name: str
  value_source: str | None
  span: Span


@dataclass
class EnumDecl:
  name: str
  is_type_enum: bool
  base_source: str | None
  flag: bool
  members: list[EnumMember]
  span: Span


@dataclass
class ClassDecl:
  name: str
  bases_source: str | None
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
  members: list["ConstField | FieldDecl | OpaqueMember | FunctionDecl"]
  span: Span
  header_source: str = ""
  decorators_source: str = ""
  is_native: bool = False
  # 含方括号，如 ``[Element]`` / ``[T: int = 0]``；无则 ""
  type_params_source: str = ""


@dataclass
class ParamDecl:
  name: str
  type_syntax: TypeSyntax | None
  default_source: str | None
  span: Span
  is_vararg: bool = False
  is_kwarg: bool = False
  kind: str = "pos"  # pos | kwonly | star | dstar


@dataclass
class FunctionDecl:
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
  # 结构化返回类型（与 return_source 并存；去桥后可删字符串）
  return_type: TypeSyntax | None = None
  params: list[ParamDecl] = field(default_factory=list)
  # P2：结构化函数体；解析失败时为空，仍用 body_source
  body: list["StmtSyntax"] = field(default_factory=list)
  # 泛型形参原文，如 ``[T]`` / ``[T: int]``；无则 ""
  type_params_source: str = ""


@dataclass
class ImportStmt:
  source: str
  span: Span


@dataclass
class ModuleConstDecl:
  """模块级 ``const NAME: T = value``。"""
  name: str
  type_syntax: TypeSyntax | None
  value_source: str
  span: Span


@dataclass
class OpaqueStmt:
  source: str
  span: Span


# --- P2 表达式 / 语句（seed 子集；与类型 GenericApply / Attributed 分叉）---


@dataclass
class NameExpr:
  name: str
  span: Span


@dataclass
class LiteralExpr:
  kind: str  # int | float | str | bool | none
  text: str
  span: Span


@dataclass
class AttributeExpr:
  value: "ExprSyntax"
  attr: str
  span: Span


@dataclass
class CallExpr:
  func: "ExprSyntax"
  args: list["ExprSyntax"]
  keywords: list[tuple[str, "ExprSyntax"]]
  span: Span


@dataclass
class BinOpExpr:
  left: "ExprSyntax"
  op: str
  right: "ExprSyntax"
  span: Span


@dataclass
class UnaryOpExpr:
  op: str
  operand: "ExprSyntax"
  span: Span


@dataclass
class CompareExpr:
  left: "ExprSyntax"
  ops: list[str]
  comparators: list["ExprSyntax"]
  span: Span


@dataclass
class BoolOpExpr:
  op: str  # and | or
  values: list["ExprSyntax"]
  span: Span


@dataclass
class SubscriptExpr:
  """值下标 ``arr[i]``（≠ ``GenericApplyTypeSyntax``）。"""
  value: "ExprSyntax"
  slice: "ExprSyntax"
  span: Span


@dataclass
class MatMultExpr:
  """表达式 ``a @ b``（≠ ``AttributedTypeSyntax``）。"""
  left: "ExprSyntax"
  right: "ExprSyntax"
  span: Span


@dataclass
class ListExpr:
  elts: list["ExprSyntax"]
  span: Span


@dataclass
class TupleExpr:
  elts: list["ExprSyntax"]
  span: Span


@dataclass
class DictExpr:
  keys: list["ExprSyntax | None"]
  values: list["ExprSyntax"]
  span: Span


@dataclass
class SliceExpr:
  """下标切片 ``lower:upper[:step]``（作为 SubscriptExpr.slice）。"""
  lower: "ExprSyntax | None"
  upper: "ExprSyntax | None"
  step: "ExprSyntax | None"
  span: Span


@dataclass
class IfExp:
  """三元 ``body if test else orelse``。"""
  body: "ExprSyntax"
  test: "ExprSyntax"
  orelse: "ExprSyntax"
  span: Span


@dataclass
class LambdaExpr:
  """``lambda [params]: expr``（参数原文保留；体为表达式）。"""
  params_source: str
  body: "ExprSyntax"
  span: Span


@dataclass
class StarredExpr:
  """赋值/调用中的 ``*x``。"""
  value: "ExprSyntax"
  span: Span


ExprSyntax = Union[
  NameExpr,
  LiteralExpr,
  AttributeExpr,
  CallExpr,
  BinOpExpr,
  UnaryOpExpr,
  CompareExpr,
  BoolOpExpr,
  SubscriptExpr,
  MatMultExpr,
  ListExpr,
  TupleExpr,
  DictExpr,
  SliceExpr,
  IfExp,
  LambdaExpr,
  StarredExpr,
]


@dataclass
class ExprStmt:
  value: ExprSyntax
  span: Span


@dataclass
class ReturnStmt:
  value: ExprSyntax | None
  span: Span


@dataclass
class RaiseStmt:
  exc: ExprSyntax | None
  span: Span


@dataclass
class AssignStmt:
  target: ExprSyntax
  value: ExprSyntax
  span: Span


@dataclass
class AnnAssignStmt:
  """``x: T [= v]`` / ``self.x: T [= v]``（target 为 Name / Attribute / Subscript）。"""
  target: "ExprSyntax"
  annotation: TypeSyntax | None
  value: ExprSyntax | None
  span: Span


@dataclass
class IfStmt:
  test: ExprSyntax
  body: list["StmtSyntax"]
  orelse: list["StmtSyntax"]
  span: Span


@dataclass
class WhileStmt:
  test: ExprSyntax
  body: list["StmtSyntax"]
  span: Span


@dataclass
class ForStmt:
  target: ExprSyntax
  iter: ExprSyntax
  body: list["StmtSyntax"]
  span: Span


@dataclass
class PassStmt:
  span: Span


@dataclass
class BreakStmt:
  span: Span


@dataclass
class ContinueStmt:
  span: Span


@dataclass
class GlobalStmt:
  """``global a, b``。"""
  names: list[str]
  span: Span


@dataclass
class NonlocalStmt:
  """``nonlocal a, b``。"""
  names: list[str]
  span: Span


@dataclass
class AugAssignStmt:
  target: ExprSyntax
  op: str
  value: ExprSyntax
  span: Span


@dataclass
class MatchCase:
  pattern_source: str
  body: list["StmtSyntax"]
  span: Span


@dataclass
class MatchStmt:
  subject: ExprSyntax
  cases: list[MatchCase]
  span: Span


@dataclass
class ExceptHandler:
  """``except [T [as name]]:``。"""
  type_expr: ExprSyntax | None
  name: str | None
  body: list["StmtSyntax"]
  span: Span


@dataclass
class TryStmt:
  """``try`` / ``except`` / ``else`` / ``finally``。"""
  body: list["StmtSyntax"]
  handlers: list[ExceptHandler]
  orelse: list["StmtSyntax"]
  finalbody: list["StmtSyntax"]
  span: Span


@dataclass
class WithItem:
  context_expr: ExprSyntax
  optional_vars: ExprSyntax | None
  span: Span


@dataclass
class WithStmt:
  """``with E [as t] [, …]:``。"""
  items: list[WithItem]
  body: list["StmtSyntax"]
  span: Span


@dataclass
class AssertStmt:
  test: ExprSyntax
  msg: ExprSyntax | None
  span: Span


@dataclass
class OpaqueStmtSyntax:
  """函数体内未能结构化的语句行。"""
  source: str
  span: Span


StmtSyntax = Union[
  ExprStmt,
  ReturnStmt,
  RaiseStmt,
  AssignStmt,
  AnnAssignStmt,
  IfStmt,
  WhileStmt,
  ForStmt,
  PassStmt,
  BreakStmt,
  ContinueStmt,
  GlobalStmt,
  NonlocalStmt,
  AugAssignStmt,
  MatchStmt,
  TryStmt,
  WithStmt,
  AssertStmt,
  OpaqueStmtSyntax,
]


ModuleItem = Union[
  EnumDecl,
  ClassDecl,
  FunctionDecl,
  ImportStmt,
  ModuleConstDecl,
  OpaqueStmt,
]


@dataclass
class SyntaxModule:
  items: list[ModuleItem] = field(default_factory=list)
  span: Span | None = None
  unsupported: list[str] = field(default_factory=list)
