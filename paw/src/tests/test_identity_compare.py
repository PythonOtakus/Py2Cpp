"""``is`` / ``is not`` 对象身份比较 emit。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class IdentityCompareEmitTests(unittest.TestCase):
  def test_value_type_uses_address_compare(self):
    src = """
from py2cpp import new, Self

class Widget:
  pass

def same_ref(a: Widget, b: Widget) -> bool:
  return a is b

def diff_copy(src: Widget) -> bool:
  other: Widget = src
  return src is other
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
      self.assertIn("(&(a))==(&(b))", compact)
      self.assertIn("(&(src))==(&(other))", compact)
      self.assertNotIn("a==b", compact.replace("(&(a))==(&(b))", ""))

  def test_is_not_uses_address_compare(self):
    src = """
class Widget:
  pass

def check(a: Widget, b: Widget) -> bool:
  return a is not b
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
      self.assertIn("(&(a))!=(&(b))", compact)

  def test_non_optional_is_none_is_false(self):
    src = """
def check(x: int) -> bool:
  return x is None
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
      self.assertIn("returnfalse", compact)

  def test_cstr_is_none_uses_nullptr(self):
    src = """
from py2cpp import *

def check(p: utf8ptr) -> bool:
  return p is None
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
      self.assertIn("p==nullptr", compact)
      self.assertNotIn("returnfalse", compact)

  def test_raw_ptr_is_not_none_uses_nullptr(self):
    src = """
from py2cpp import new, Self, boxing

@boxing
class NodeUnsafe:
  prev: Self
  def __init__(self):
    self.prev = None

def has_prev(n: NodeUnsafe) -> bool:
  return n.prev is not None
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
      self.assertIn("prev!=nullptr", compact)
      self.assertNotIn("if(true)", compact)

  def test_refcount_uses_deref_address(self):
    src = """
from py2cpp import refcount, new, Self

@refcount
class Node:
  pass

def same_ref(a: Node, b: Node) -> bool:
  return a is b
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
      self.assertIn("(&(*(a)))==(&(*(b)))", compact)


if __name__ == "__main__":
  unittest.main()
