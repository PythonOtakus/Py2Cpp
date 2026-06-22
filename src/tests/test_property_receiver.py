"""``@property`` 接收者推断：``self`` / 局部变量 / 构造调用须生成 ``getter()``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class PropertyReceiverTests(unittest.TestCase):
  def test_self_and_ctor_property_read_use_getter_call(self):
    src = """
from py2cpp import copyable, Self

@copyable
class Node:
  @property
  def parent(self) -> Self:
    return Self("x")

  def check(self) -> None:
    par: Node = self.parent
    _ = par

def use() -> None:
  _ = Node().parent
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("this->get_parent()", cpp.replace(" ", ""))
      self.assertIn("Node().get_parent()", cpp.replace(" ", ""))
      self.assertNotIn("this->parent;", cpp)
      self.assertNotIn("Node().parent;", cpp)

  def test_list_subscript_property_read_uses_getter_call(self):
    src = """
from py2cpp import *

@copyable
class Item:
  @property
  def tag(self) -> int:
    return 1

def read(items: list[Item]) -> None:
  _ = items[0].tag
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("tag__get()", cpp)
      self.assertNotRegex(cpp, r"__getitem__\([^)]+\)\.tag[^_]")

  def test_with_as_enter_type_enables_property_read(self):
    src = """
from py2cpp import *

@copyable
class Box:
  def __enter__(self) -> Self:
    return self

  def __exit__(self) -> None:
    pass

  @property
  def value(self) -> str:
    return "x"

def use() -> None:
  with Box() as b:
    _ = b.value
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("Box b =", cpp)
      self.assertIn("value__get()", cpp)
      self.assertNotRegex(cpp, r"\bb\.value[^_]")