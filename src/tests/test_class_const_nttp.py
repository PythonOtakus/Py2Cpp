"""类 ``@const`` 用于 NTTP / 默认形参。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.analyzer import TypeParser
from src.analysis.ir import ClassInfo
from src.passes.mixins import expand_mixins, is_mixin_class
from src.translator import Translator


class ClassConstNttpTests(unittest.TestCase):
  def test_array_nttp_from_merged_mixin_const(self):
    src = """
from py2cpp import mixin, const, array

@mixin
class CapMixin:
  _SSO_CAP: int @const = 22

class Box(CapMixin):
  data: array[int, _SSO_CAP]
"""
    tr = Translator("mod", "mod.py")
    tr.classes = {}
    mod = ast.parse(src)
    for node in mod.body:
      if isinstance(node, ast.ClassDef):
        info = ClassInfo(node, "mod")
        info.is_mixin = is_mixin_class(info)
        tr.classes[node.name] = info
    expand_mixins(tr)
    tp = TypeParser()
    tp.set_classes(tr.classes)
    box = tr.classes["Box"]
    ann: ast.expr | None = None
    for stmt in box.node.body:
      if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        if stmt.target.id == "data":
          ann = stmt.annotation
          break
    self.assertIsNotNone(ann)
    cpp = tp.parse_type(ann, set(), self_class=box.template_cpp_type())
    self.assertIn("_SSO_CAP", cpp)
    self.assertIn("PyArray", cpp)

  def test_stack_slice_dim_from_class_const(self):
    src = """
class Box:
  _N: int @const = 32
  buf: int[:_N]
"""
    tr = Translator("mod", "mod.py")
    tr.classes = {}
    mod = ast.parse(src)
    for node in mod.body:
      if isinstance(node, ast.ClassDef):
        tr.classes[node.name] = ClassInfo(node, "mod")
    tp = TypeParser()
    tp.set_classes(tr.classes)
    box = tr.classes["Box"]
    ann: ast.expr | None = None
    for stmt in box.node.body:
      if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        if stmt.target.id == "buf":
          ann = stmt.annotation
          break
    self.assertIsNotNone(ann)
    cpp = tp.parse_type(ann, set(), self_class=box.cpp_name())
    self.assertIn("_N", cpp)
    self.assertNotIn(", 32,", cpp)


if __name__ == "__main__":
  unittest.main()
