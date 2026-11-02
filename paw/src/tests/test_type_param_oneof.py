"""``oneof[…]`` 泛型约束：解析、混入传播与 C++ ``static_assert`` 生成。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.ir import (
  ClassInfo,
  cpp_oneof_static_assert_expr,
  parse_class_type_params,
  parse_typevar_oneof_bounds,
)
from src.passes.mixins import expand_mixins, is_mixin_class
from src.translator import Translator


def _parse_classes(src: str) -> dict[str, ClassInfo]:
  mod = ast.parse(src)
  out: dict[str, ClassInfo] = {}
  for node in mod.body:
    if isinstance(node, ast.ClassDef):
      info = ClassInfo(node, "mod")
      info.is_mixin = is_mixin_class(info)
      out[node.name] = info
  return out


class ParseTypevarOneofTests(unittest.TestCase):
  def test_oneof_char_byte(self):
    mod = ast.parse("class M[T: oneof[char, byte]]:\n  pass\n")
    cls = mod.body[0]
    tp = cls.type_params[0]
    self.assertEqual(parse_typevar_oneof_bounds(tp.bound), ("char", "byte"))

  def test_class_type_params_oneof(self):
    mod = ast.parse("class M[T: oneof[char, byte]]:\n  pass\n")
    _, _, _, proto, oneof, _, _, _ = parse_class_type_params(mod.body[0])
    self.assertEqual(oneof["T"], ("char", "byte"))
    self.assertNotIn("T", proto)

  def test_oneof_with_protocol_intersection(self):
    mod = ast.parse("class M[T: DictKeyType & oneof[int, str]]:\n  pass\n")
    _, _, _, proto, oneof, _, _, _ = parse_class_type_params(mod.body[0])
    self.assertEqual(oneof["T"], ("int", "str"))
    self.assertEqual(proto["T"], ("DictKeyType",))

  def test_cpp_oneof_expr(self):
    expr = cpp_oneof_static_assert_expr("T", ("char", "byte"))
    self.assertIn("PyChar", expr)
    self.assertIn("PyByte", expr)
    self.assertIn("||", expr)


class MixinOneofPropagationTests(unittest.TestCase):
  def test_concrete_mixin_subst_emits_on_host(self):
    src = """
from py2cpp import mixin

@mixin
class ElemMixin[T: oneof[char, byte]]:
  pass

class Host(ElemMixin[char]):
  x: int = 0
"""
    tr = Translator("mod", "mod.py")
    tr.classes = _parse_classes(src)
    expand_mixins(tr)
    host = tr.classes["Host"]
    self.assertEqual(host.concrete_oneof_constraints.get("char"), ("char", "byte"))


if __name__ == "__main__":
  unittest.main()
