"""宿主统一前端入口：方言选择、缓存、Syntax→HIR→MidIR（无 Paw→legacy 全文改写）。"""
from __future__ import annotations

from .api import (
  SCHEMA_VERSION,
  Dialect,
  ParsedModule,
  clear_parse_cache,
  parse_expression,
  parse_module,
  parse_module_file,
  parse_type,
)
from .dialect import dialect_from_path

__all__ = [
  "SCHEMA_VERSION",
  "Dialect",
  "ParsedModule",
  "clear_parse_cache",
  "dialect_from_path",
  "parse_expression",
  "parse_module",
  "parse_module_file",
  "parse_type",
]
