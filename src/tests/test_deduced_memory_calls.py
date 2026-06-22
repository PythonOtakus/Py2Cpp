"""``id`` / ``init`` / ``destroy`` / ``free`` / ``freeArray`` 省略类型实参。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator
from src.translation_error import TranslationError


class DeducedMemoryCallEmitTests(unittest.TestCase):
  def test_id_without_type_arg(self):
    src = """
class Widget:
  pass

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
      compact = cpp_path.read_text(encoding="utf-8").replace(" ", "")
      self.assertIn("return(&(w))", compact)

  def test_destroy_free_emit_without_template_args(self):
    src = """
class Widget:
  pass

def clear_buf(buf: Pointer[Widget], n: int) -> None:
  i: int = 0
  while i < n:
    destroy(buf + i)
    i += 1
  freeArray(buf)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("destroy((buf + i))", cpp)
      self.assertIn("freeArray(buf)", cpp)
      self.assertNotIn("destroy<", cpp)
      self.assertNotIn("freeArray<", cpp)

  def test_init_without_type_arg(self):
    src = """
class Widget:
  def __init__(self, n: int):
    self.n: int = n

def emplace(buf: Pointer[Widget], n: int) -> None:
  init(buf, n)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("init(buf, n)", cpp)
      self.assertNotIn("init<", cpp)

  def test_explicit_subscript_rejected_under_strict(self):
    src = """
class Node:
  pass

def drop(p: Pointer[Node]) -> None:
  destroy[Node](p)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(out), include_stdlib=False, strict=True,
        )
      self.assertIn("[S07]", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
