"""PEP 695 形参协议约束：单协议与 ``A & B`` 交集。"""
import ast
import unittest

from src.analysis.ir import (
  parse_class_type_params,
  parse_typevar_protocol_bounds,
  type_param_nttp_value_type,
)


class ParseTypevarProtocolBoundsTests(unittest.TestCase):
  def test_single_name(self):
    node = ast.Name(id="Comparable", ctx=ast.Load())
    self.assertEqual(parse_typevar_protocol_bounds(node), ("Comparable",))

  def test_intersection(self):
    node = ast.BinOp(
      left=ast.Name(id="Comparable", ctx=ast.Load()),
      op=ast.BitAnd(),
      right=ast.Name(id="DictKey", ctx=ast.Load()),
    )
    self.assertEqual(parse_typevar_protocol_bounds(node), ("Comparable", "DictKey"))

  def test_class_type_params_intersection(self):
    mod = ast.parse("class C[T: Comparable & DictKey]:\n  pass\n")
    cls = mod.body[0]
    _, _, _, constraints, _, nttp, _ = parse_class_type_params(cls)
    self.assertEqual(constraints["T"], ("Comparable", "DictKey"))
    self.assertEqual(nttp, {})

  def test_class_type_param_nttp(self):
    mod = ast.parse("class ModInt[T: Integral, Mod: T]:\n  pass\n")
    cls = mod.body[0]
    params, _, _, constraints, _, nttp, _ = parse_class_type_params(cls)
    self.assertEqual(params, ["T", "Mod"])
    self.assertEqual(constraints["T"], ("Integral",))
    self.assertNotIn("Mod", constraints)
    self.assertEqual(nttp, {"Mod": "T"})
    self.assertEqual(type_param_nttp_value_type(ast.Name(id="T"), ["T"]), "T")
    self.assertIsNone(type_param_nttp_value_type(ast.Name(id="Integral"), ["T"]))


if __name__ == "__main__":
  unittest.main()
