"""类体 ``if T is …``：Mid 不摊平分支；ast_from_mid 保留 If 链供 ``class_type_if``。"""
from __future__ import annotations

import ast
import unittest

from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.source import FileId
from compiler.py.frontend.parser import parse_tokens
from compiler.py.mid.ast_from_mid import classdef_from_mid_class
from compiler.py.mid.nodes import MidClass
from compiler.py.sema.bind import bind_module, lower_to_mid
from host.analysis.analyzer import TypeParser
from host.analysis.ir import ClassInfo
from host.passes.class_type_if import plan_class_type_if
from host.translator import Translator


_CELL_SRC = """
class Cell[Element]:
  if Element is int:
    type V = int
    seed: V = 0
    band: int = 10
    static def tag() -> int:
      return 1
  elif Element is str:
    type V = str
    seed: V = new()
    band: int = 20
    static def tag() -> int:
      return 2
  else:
    type V = float64
    seed: V = 0.0
    band: int = 30
    static def tag() -> int:
      return 3

  serial: int = 0

  def read(self) -> V:
    return self.seed
"""


def _mid_class(src: str, name: str = "Cell") -> MidClass:
  syn = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
  mid = lower_to_mid(bind_module(syn, path="cell.paw"))
  for it in mid.items:
    if isinstance(it, MidClass) and it.name == name:
      return it
  raise AssertionError(f"MidClass {name!r} not found")


class ClassTypeIfMidTests(unittest.TestCase):
  def test_mid_keeps_type_if_chain_opaque_not_flattened(self):
    cls = _mid_class(_CELL_SRC)
    self.assertEqual([n for n, _t, _v in cls.fields], ["serial"])
    self.assertNotIn("else", [n for n, _t, _v in cls.fields])
    self.assertEqual(len(cls.opaque_members), 1)
    opaque = cls.opaque_members[0]
    self.assertTrue(opaque.lstrip().startswith("if Element is int:"))
    self.assertIn("elif Element is str:", opaque)
    self.assertIn("else:", opaque)
    self.assertIn("static def tag()", opaque)
    self.assertEqual([m.name for m in cls.methods], ["read"])

  def test_ast_from_mid_preserves_if_chain_for_class_type_if(self):
    cls = _mid_class(_CELL_SRC)
    node = classdef_from_mid_class(cls)
    self.assertIsInstance(node.body[0], ast.If)
    top_fns = [s.name for s in node.body if isinstance(s, ast.FunctionDef)]
    self.assertEqual(top_fns, ["read"])
    self.assertNotIn("tag", top_fns)
    if_node = node.body[0]
    assert isinstance(if_node, ast.If)
    self.assertTrue(
      any(isinstance(s, ast.FunctionDef) and s.name == "tag" for s in if_node.body)
    )
    self.assertTrue(if_node.orelse and isinstance(if_node.orelse[0], ast.If))

    info = ClassInfo(node, "cell")
    tr = Translator("cell", "cell.paw")
    tr.type_parser = TypeParser()
    plan = plan_class_type_if(tr, info)
    self.assertIsNotNone(plan)
    assert plan is not None
    self.assertEqual(plan.chain.type_param, "Element")
    self.assertEqual(len(plan.tail), 2)  # serial + read


if __name__ == "__main__":
  unittest.main()
