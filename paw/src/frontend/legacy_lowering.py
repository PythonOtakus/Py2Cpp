"""【已废弃生产路径】旧 Paw→legacy 文本改写桥。

生产编译请走 ``src.frontend.api.parse_module``（Syntax→HIR→MidIR→materialize）。
本模块仅保留离线/测试对照；``paw_source_to_ast`` 会发出 DeprecationWarning。
"""
from __future__ import annotations

import ast
import warnings

from compiler.py.frontend.source import FileId
from compiler.py.frontend.surface_rewrite import rewrite_paw_to_legacy
from compiler.py.frontend.syntax_nodes import SyntaxModule


def paw_source_to_ast(
  source: str,
  *,
  filename: str = "<paw>",
  file_id: FileId | None = None,
) -> tuple[ast.Module, str]:
  warnings.warn(
    "paw_source_to_ast / rewrite_paw_to_legacy 已退出生产路径；"
    "请使用 parse_module（MidIR materialize）",
    DeprecationWarning,
    stacklevel=2,
  )
  fid = file_id or FileId(0)
  legacy = rewrite_paw_to_legacy(source, file_id=fid)
  tree = ast.parse(legacy, filename=filename)
  return tree, legacy


def syntax_to_ast(
  module: SyntaxModule,
  source: str,
  *,
  filename: str = "<paw>",
  file_id: FileId | None = None,
) -> ast.Module:
  warnings.warn(
    "syntax_to_ast 已废弃；生产路径使用 MidIR ast_module_from_mid",
    DeprecationWarning,
    stacklevel=2,
  )
  tree, _ = paw_source_to_ast(source, filename=filename, file_id=file_id)
  _ = module
  return tree
