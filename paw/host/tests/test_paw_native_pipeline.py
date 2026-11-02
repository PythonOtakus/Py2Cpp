"""原生 Syntax→HIR→MidIR 管道与 legacy adapter 冒烟。"""
from __future__ import annotations

import ast
import unittest

from compiler.py.frontend.syntax_nodes import ClassDecl, EnumDecl, ImportStmt
from compiler.py.hir.nodes import HirClass, HirEnum
from compiler.py.mid.nodes import MidClass, MidEnum
from host.frontend.api import Dialect, clear_parse_cache, parse_expression, parse_module
from host.frontend.cpython_adapter import from_cpython
from host.frontend.source import SourceManager


class PawNativePipelineTests(unittest.TestCase):
  def setUp(self) -> None:
    clear_parse_cache()

  def test_paw_builds_hir_and_mid(self) -> None:
    src = "enum E:\n  A = 0\n\nref class R:\n  x: int = 1\n"
    p = parse_module(src, path="t.paw", dialect=Dialect.PAW)
    self.assertIsNotNone(p.hir)
    self.assertIsNotNone(p.mid)
    self.assertTrue(any(isinstance(d, HirEnum) for d in p.hir.decls))
    self.assertTrue(any(isinstance(d, HirClass) for d in p.hir.decls))
    self.assertTrue(any(isinstance(d, MidEnum) for d in p.mid.items))
    self.assertTrue(any(isinstance(d, MidClass) for d in p.mid.items))
    self.assertTrue(any(isinstance(n, EnumDecl) for n in p.syntax.items))
    self.assertTrue(any(isinstance(n, ClassDecl) for n in p.syntax.items))

  def test_no_legacy_source_on_paw(self) -> None:
    p = parse_module("enum E:\n  A = 0\n", path="t.paw")
    self.assertEqual(p.legacy_source, "")

  def test_parse_expression_identifier(self) -> None:
    node = parse_expression("FooBar")
    self.assertIsInstance(node, ast.Name)
    self.assertEqual(node.id, "FooBar")

  def test_legacy_adapter_imports_and_functions(self) -> None:
    src = "import os\n\ndef f(x: int) -> int:\n  return x\n"
    tree = ast.parse(src)
    sm = SourceManager()
    sf = sm.add("t.py", src, "d")
    syn = from_cpython(tree, src, file_id=sf.file_id)
    self.assertTrue(any(isinstance(i, ImportStmt) for i in syn.items))
    kinds = {type(i).__name__ for i in syn.items}
    self.assertIn("FunctionDecl", kinds)


if __name__ == "__main__":
  unittest.main()
