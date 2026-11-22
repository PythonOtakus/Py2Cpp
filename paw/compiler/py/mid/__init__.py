"""MidIR：发射器可消费的结构化 IR（无 ast.AST 字段）。"""
from __future__ import annotations

from .mutate import append_mid_method, find_mid_class, mid_class_for_info, replace_module_mid
from .nodes import MidClass, MidEnum, MidFunction, MidImport, MidModule, MidOpaque

SCHEMA_VERSION = "paw-mid-0.1.0"

__all__ = [
  "SCHEMA_VERSION",
  "MidClass",
  "MidEnum",
  "MidFunction",
  "MidImport",
  "MidModule",
  "MidOpaque",
  "append_mid_method",
  "find_mid_class",
  "mid_class_for_info",
  "replace_module_mid",
]
