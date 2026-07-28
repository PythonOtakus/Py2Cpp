"""``@property`` getter/setter 内 ``self.__value__`` → 存储字段 ``{name}__value``。"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from src.analysis.ir import ClassInfo
from src.passes.field_properties import expand_property_value_references, property_storage_field
from src.translator import Translator


class PropertyStorageFieldTests(unittest.TestCase):
  def test_field_property_uses_value_suffix(self):
    info = ClassInfo(ast.parse("class Holder: pass").body[0])
    info.fields.append("value")
    info.field_properties.add("value")
    self.assertEqual(property_storage_field(info, "value"), "value__value")

  def test_explicit_property_uses_value_suffix(self):
    src = """
class Window:
  pass
"""
    info = ClassInfo(ast.parse(src).body[0])
    self.assertEqual(property_storage_field(info, "title"), "title__value")


class PropertyValueEmitTests(unittest.TestCase):
  def test_rejects_legacy_name_setter(self):
    src = """
class Window:
  @property
  def title(self) -> str:
    return self.__value__

  @title.setter
  def title(self, value: str) -> None:
    self.__value__ = value
"""
    tree = ast.parse(src)
    cls = tree.body[0]
    assert isinstance(cls, ast.ClassDef)
    with self.assertRaises(ValueError) as ctx:
      ClassInfo(cls)
    self.assertIn("@property.setter", str(ctx.exception))

  def test_emits_value_storage_in_getter(self):
    src = """
from py2cpp import *

class Window:
  @property
  def title(self) -> str:
    return self.__value__

  @property.setter
  def title(self, value: str) -> None:
    self.__value__ = value
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      compact = cpp.replace(" ", "")
      self.assertIn("returnthis->title__value;", compact)
      self.assertIn("this->title__value=value;", compact)
      self.assertNotIn("__value__", cpp)
      self.assertIn("title__get()const", compact)
      self.assertIn("title__set(PyStrvalue)", compact)

  def test_emits_static_property_getter_name(self):
    src = """
from py2cpp import *

class Counter:
  @staticproperty
  def zero() -> int:
    return 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      h = cpp_path.with_suffix(".h").read_text(encoding="utf-8")
      compact_h = h.replace(" ", "")
      compact = cpp.replace(" ", "")
      self.assertIn("staticPyIntzero__get()", compact_h)
      self.assertIn("Counter::zero__get()", compact)
      self.assertNotIn("zero()", cpp.replace("zero__get()", ""))

  def test_transforms_getter_body(self):
    src = """
class Window:
  @property
  def title(self) -> str:
    return self.__value__
"""
    tree = ast.parse(src)
    cls = tree.body[0]
    assert isinstance(cls, ast.ClassDef)
    info = ClassInfo(cls)
    expand_property_value_references({info.name: info})
    getter = info.properties["title"].getter
    assert getter is not None
    ret = getter.body[0]
    assert isinstance(ret, ast.Return)
    attr = ret.value
    assert isinstance(attr, ast.Attribute)
    self.assertEqual(attr.attr, "title__value")


class PropertyDunderNamingTests(unittest.TestCase):
  def test_dunder_property_getter_suffix(self):
    from src.analysis.patterns import (
      property_getter_method_for,
      property_postsetter_method_for,
      property_setter_method_for,
      property_storage_field_for,
    )

    self.assertEqual(property_getter_method_for("__id__"), "__id____get")
    self.assertEqual(property_getter_method_for("__class_id__"), "__class_id____get")
    self.assertEqual(property_getter_method_for("__enum__"), "__enum____get")
    self.assertEqual(property_getter_method_for("title"), "title__get")
    self.assertEqual(property_setter_method_for("__id__"), "__id____set")
    self.assertEqual(property_postsetter_method_for("__value__"), "__value____postset")
    self.assertEqual(property_storage_field_for("__id__"), "__id____value")
    self.assertEqual(property_storage_field_for("__value__"), "__value____value")
    self.assertEqual(property_storage_field_for("title"), "title__value")
    from src.passes.descriptors import storage_field_for

    self.assertEqual(storage_field_for("__foo__"), property_storage_field_for("__foo__"))


if __name__ == "__main__":
  unittest.main()
