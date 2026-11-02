"""``id(x)`` → 对象地址（``Pointer[T]`` / ``T*``）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator
from src.translation_error import TranslationError


class IdBuiltinEmitTests(unittest.TestCase):
  def test_value_type_emits_address_of(self):
    src = """
class Widget:
  def __init__(self, n: int):
    self.n: int = n

def take_addr(w: Widget) -> Pointer[Widget]:
  return id(w)
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
      self.assertIn("return(&(w))", compact)

  def test_refcount_emits_deref_address(self):
    src = """
from py2cpp import refcount

@refcount
class Node:
  pass

def take_addr(n: Node) -> Pointer[Node]:
  return id(n)
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
      self.assertIn("return(&(*(n)))", compact)

  def test_literal_arg_rejected(self):
    src = """
def bad() -> Pointer[int]:
  return id(1)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(TranslationError):
        Translator.translate_file(
          str(py), output_dir=str(out), include_stdlib=False,
        )

  def test_is_same_address_as_id(self):
    src = """
class Widget:
  pass

def same(a: Widget, b: Widget) -> bool:
  return id(a) == id(b)
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

  def test_pointer_field_from_self_is_this_not_address_of_this(self):
    src = """
from py2cpp import *

class Doc:
  peer: Pointer[Self] = None

  def wire(self) -> None:
    self.peer = self
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True, strict=False,
      )
      compact = cpp_path.read_text(encoding="utf-8").replace(" ", "")
      self.assertIn("this->peer=this", compact)
      self.assertNotIn("=&this", compact)


if __name__ == "__main__":
  unittest.main()
