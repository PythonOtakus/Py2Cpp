"""``expand_default_ne``：有 ``__eq__`` 无 ``__ne__`` 时注入默认 ``__ne__``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class DefaultNeTests(unittest.TestCase):
  def test_injects_ne_when_eq_only(self):
    src = """
from py2cpp import immutable, new, Self

class Widget:
  @immutable
  def __eq__(self, other: Self) -> bool:
    return True

def main():
  a: Widget = new()
  b: Widget = new()
  return a != b
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
      self.assertIn("__ne__", cpp)
      self.assertIn("(!(*this==other))", compact)

  def test_skips_when_ne_written(self):
    src = """
from py2cpp import immutable, new, Self

class Widget:
  @immutable
  def __eq__(self, other: Self) -> bool:
    return True

  @immutable
  def __ne__(self, other: Self) -> bool:
    return False

def main():
  a: Widget = new()
  return a != a
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("returnfalse", cpp.replace(" ", ""))


if __name__ == "__main__":
  unittest.main()
