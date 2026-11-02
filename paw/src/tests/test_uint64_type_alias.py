"""``uint`` / ``uint64`` / ``uintptr`` 注解须映射 ``PyUInt`` / ``PyUInt64`` / ``PyUIntPtr``，勿被 ``type … = int`` 别名展开为 ``PyInt``。"""
import ast
import tempfile
import unittest
from pathlib import Path

from src.analysis.analyzer import TypeParser
from src.analysis.ir import TypeAliasInfo, cpp_ident
from src.analysis.imports import resolve_ctor_cpp_type
from src.translator import Translator


class TestUInt64TypeAlias(unittest.TestCase):
  def test_int16_and_uint16_are_constructor_types(self):
    tr = Translator("test/mod", "test/mod.py")
    self.assertEqual(resolve_ctor_cpp_type(tr, "int16"), cpp_ident("int16"))
    self.assertEqual(resolve_ctor_cpp_type(tr, "uint16"), cpp_ident("uint16"))
  def test_int16_wins_over_module_alias(self):
    tp = TypeParser()
    tp.set_type_aliases(
      {
        "int16": TypeAliasInfo(
          name="int16",
          value=ast.Name(id="int", ctx=ast.Load()),
          type_params=[],
        ),
      },
    )
    ann = ast.Name(id="int16", ctx=ast.Load())
    self.assertEqual(tp.parse_type(ann, set()), cpp_ident("int16"))
    self.assertNotEqual(tp.parse_type(ann, set()), cpp_ident("int"))
  def test_uint16_wins_over_module_alias(self):
    tp = TypeParser()
    tp.set_type_aliases(
      {
        "uint16": TypeAliasInfo(
          name="uint16",
          value=ast.Name(id="int", ctx=ast.Load()),
          type_params=[],
        ),
      },
    )
    ann = ast.Name(id="uint16", ctx=ast.Load())
    self.assertEqual(tp.parse_type(ann, set()), cpp_ident("uint16"))
    self.assertNotEqual(tp.parse_type(ann, set()), cpp_ident("int"))

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



  def test_module_alias_is_visible_in_class_method_body(self):
    src = """
from py2cpp import *

type Ints = list[int]

@copyable
class Box:
  def make(self) -> Ints:
    values: Ints = new()
    return values

  def makeFromCall(self) -> Ints:
    return Ints()
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
    self.assertIn("PyList<PyInt", cpp)
    self.assertNotIn("PyInts", cpp)

if __name__ == "__main__":
  unittest.main()
