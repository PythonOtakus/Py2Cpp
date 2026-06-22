"""``uint`` / ``uint64`` / ``uintptr`` 注解须映射 ``PyUInt`` / ``PyUInt64`` / ``PyUPtr``，勿被 ``type … = int`` 别名展开为 ``PyInt``。"""
import ast
import unittest

from src.analysis.analyzer import TypeParser
from src.analysis.ir import TypeAliasInfo, cpp_ident


class TestUInt64TypeAlias(unittest.TestCase):
  def test_uint64_wins_over_module_alias(self):
    tp = TypeParser()
    tp.set_type_aliases(
      {
        "uint64": TypeAliasInfo(
          name="uint64",
          value=ast.Name(id="int", ctx=ast.Load()),
          type_params=[],
        ),
      },
    )
    ann = ast.Name(id="uint64", ctx=ast.Load())
    self.assertEqual(tp.parse_type(ann, set()), cpp_ident("uint64"))
    self.assertNotEqual(tp.parse_type(ann, set()), cpp_ident("int"))

  def test_uint_wins_over_module_alias(self):
    tp = TypeParser()
    tp.set_type_aliases(
      {
        "uint": TypeAliasInfo(
          name="uint",
          value=ast.Name(id="int", ctx=ast.Load()),
          type_params=[],
        ),
      },
    )
    ann = ast.Name(id="uint", ctx=ast.Load())
    self.assertEqual(tp.parse_type(ann, set()), cpp_ident("uint"))

  def test_uintptr_wins_over_module_alias(self):
    tp = TypeParser()
    tp.set_type_aliases(
      {
        "uintptr": TypeAliasInfo(
          name="uintptr",
          value=ast.Name(id="int", ctx=ast.Load()),
          type_params=[],
        ),
      },
    )
    ann = ast.Name(id="uintptr", ctx=ast.Load())
    self.assertEqual(tp.parse_type(ann, set()), cpp_ident("uintptr"))
    self.assertNotEqual(tp.parse_type(ann, set()), cpp_ident("int"))


if __name__ == "__main__":
  unittest.main()
