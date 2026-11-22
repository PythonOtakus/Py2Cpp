"""原生 Syntax→HIR→MidIR 管道冒烟（无 CPython adapter）。"""
from __future__ import annotations

import unittest

from compiler.py.frontend.syntax_nodes import ClassDecl, EnumDecl
from compiler.py.hir.nodes import HirClass, HirEnum
from compiler.py.mid.nodes import MidClass, MidEnum
from host.frontend.api import Dialect, clear_parse_cache, parse_expression, parse_module


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
    self.assertEqual(p.tree.body, [])

  def test_no_legacy_source_on_paw(self) -> None:
    p = parse_module("enum E:\n  A = 0\n", path="t.paw")
    self.assertEqual(p.legacy_source, "")

  def test_parse_expression_identifier(self) -> None:
    from compiler.py.frontend.syntax_nodes import NameExpr

    node = parse_expression("FooBar")
    self.assertIsInstance(node, NameExpr)
    self.assertEqual(node.name, "FooBar")


if __name__ == "__main__":
  unittest.main()
