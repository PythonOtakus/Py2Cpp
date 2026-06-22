"""``@protocol``：标记协议类并收集抽象方法名（``...`` 体）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import (
  ClassInfo,
  ProtocolMemberConstraint,
  has_named_decorator,
  is_stub_function_body,
)

if TYPE_CHECKING:
  from ..translator import Translator


def is_protocol_static_virtual_method(stmt: ast.FunctionDef) -> bool:
  """``@protocol`` 内 ``@staticmethod`` + ``@virtual``/``@abstract``（编译期静态契约）。"""
  return (
    has_named_decorator(stmt, "staticmethod")
    and (
      has_named_decorator(stmt, "virtual")
      or has_named_decorator(stmt, "abstract")
    )
  )


def is_protocol_instance_method(stmt: ast.FunctionDef, cls_info: ClassInfo) -> bool:
  """实例协议成员：``...``/``pass`` 桩体，非 ``@staticmethod``。"""
  return (
    not has_named_decorator(stmt, "staticmethod")
    and is_stub_function_body(stmt.body)
    and stmt.name not in cls_info.properties
  )


def _collect_protocol_methods(node: ast.ClassDef) -> list[str]:
  methods: list[str] = []
  for stmt in node.body:
    if not isinstance(stmt, ast.FunctionDef):
      continue
    if is_stub_function_body(stmt.body) or is_protocol_static_virtual_method(stmt):
      methods.append(stmt.name)
  return methods


def expand_protocol(tr: Translator) -> None:
  for info in tr.classes.values():
    info.is_protocol = has_named_decorator(info.node, "protocol")
    if info.is_protocol:
      info.protocol_methods = _collect_protocol_methods(info.node)
      for prop in info.properties.values():
        if not prop.getter or not is_stub_function_body(prop.getter.body):
          continue
        if any(m.name == prop.name and m.kind == "property" for m in info.protocol_members):
          continue
        info.protocol_members.append(
          ProtocolMemberConstraint(prop.name, "property", prop.getter.returns),
        )
