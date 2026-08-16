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
    node = ast.Name(id="ComparableType", ctx=ast.Load())
    self.assertEqual(parse_typevar_protocol_bounds(node), ("ComparableType",))

  def test_intersection(self):
    node = ast.BinOp(
      left=ast.Name(id="ComparableType", ctx=ast.Load()),
      op=ast.BitAnd(),
      right=ast.Name(id="DictKeyType", ctx=ast.Load()),
    )
    self.assertEqual(parse_typevar_protocol_bounds(node), ("ComparableType", "DictKeyType"))

  def test_class_type_params_intersection(self):
    mod = ast.parse("class C[T: ComparableType & DictKeyType]:\n  pass\n")
    cls = mod.body[0]
    _, _, _, constraints, oneof, _, nttp, _ = parse_class_type_params(cls)
    self.assertEqual(constraints["T"], ("ComparableType", "DictKeyType"))
    self.assertEqual(oneof, {})
    self.assertEqual(nttp, {})

  def test_class_type_param_nttp(self):
    mod = ast.parse("class ModInt[T: IntegralType, Mod: T]:\n  pass\n")
    cls = mod.body[0]
    params, _, _, constraints, oneof, _, nttp, _ = parse_class_type_params(cls)
    self.assertEqual(params, ["T", "Mod"])
    self.assertEqual(constraints["T"], ("IntegralType",))
    self.assertEqual(oneof, {})
    self.assertNotIn("Mod", constraints)
    self.assertEqual(nttp, {"Mod": "T"})
    self.assertEqual(type_param_nttp_value_type(ast.Name(id="T"), ["T"]), "T")
    self.assertIsNone(type_param_nttp_value_type(ast.Name(id="IntegralType"), ["T"]))


if __name__ == "__main__":
  unittest.main()
