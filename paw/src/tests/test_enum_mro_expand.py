"""``@enum.mro`` 类参数 ``base=`` 解析。"""
import ast
import unittest

from src.analysis.ir import parse_enum_mro_base


def _cls(src: str) -> ast.ClassDef:
  mod = ast.parse(src)
  node = mod.body[0]
  assert isinstance(node, ast.ClassDef)
  return node


class TestEnumMroBase(unittest.TestCase):
  def test_class_keyword_base(self):
    node = _cls("@enum.mro\nclass ExcType(base=Exception):\n  pass\n")
    self.assertEqual(parse_enum_mro_base(node), "Exception")

  def test_no_base(self):
    node = _cls("@enum.mro\nclass ExcType:\n  pass\n")
    self.assertIsNone(parse_enum_mro_base(node))


if __name__ == "__main__":
  unittest.main()
