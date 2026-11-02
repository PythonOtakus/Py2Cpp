"""``int64`` 注解须映射 ``PyInt64``，勿被 ``type int64 = int`` 别名展开为 ``PyInt``。"""
import ast
import unittest

from src.analysis.analyzer import TypeParser
from src.analysis.ir import TypeAliasInfo, cpp_ident


class TestInt64TypeAlias(unittest.TestCase):
  def test_int64_wins_over_module_alias(self):
    tp = TypeParser()
    tp.set_type_aliases(
      {
        "int64": TypeAliasInfo(
          name="int64",
          value=ast.Name(id="int", ctx=ast.Load()),
          type_params=[],
        ),
      },
    )
    ann = ast.Name(id="int64", ctx=ast.Load())
    self.assertEqual(tp.parse_type(ann, set()), cpp_ident("int64"))
    self.assertNotEqual(tp.parse_type(ann, set()), cpp_ident("int"))


if __name__ == "__main__":
  unittest.main()
