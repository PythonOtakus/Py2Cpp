"""Paw HIR：绑定后的语义树（不依赖 CPython ast）。"""
from __future__ import annotations

from .nodes import (
  HirClass,
  HirEnum,
  HirEnumMember,
  HirFunction,
  HirImport,
  HirModule,
  HirOpaque,
  ObjectModel,
)

SCHEMA_VERSION = "paw-hir-0.1.0"

__all__ = [
  "SCHEMA_VERSION",
  "HirClass",
  "HirEnum",
  "HirEnumMember",
  "HirFunction",
  "HirImport",
  "HirModule",
  "HirOpaque",
  "ObjectModel",
]
