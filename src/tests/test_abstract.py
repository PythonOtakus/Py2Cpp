"""``@abstract`` 译期规则与 C++ ``= 0`` 生成。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class AbstractRulesTests(unittest.TestCase):
  def _translate(self, source: str, *, strict: bool = True) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(source, encoding="utf-8")
      Translator.translate_file(
        str(py),
        output_dir=str(out / "generated"),
        include_stdlib=False,
        strict=strict,
      )
      headers = list((out / "generated").rglob("*.h"))
      self.assertTrue(headers, "expected at least one .h output")
      return headers[0].read_text(encoding="utf-8")

  def test_abstract_emits_pure_virtual_decl(self):
    text = self._translate(
      """from py2cpp import *

class Shape:
  @abstract
  def area(self) -> int:
    ...

def main():
  pass
"""
    )
    self.assertIn("virtual PyInt area() = 0;", text.replace("\n", " ").replace("  ", " "))

  def test_abstract_class_new_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(
        """from py2cpp import *

class Shape:
  @abstract
  def area(self) -> int:
    ...

def main():
  s: Shape = new()
  return s.area()
""",
        encoding="utf-8",
      )
      out = Path(tmp) / "generated"
      with self.assertRaises(Exception) as ctx:
        Translator.translate_file(str(py), output_dir=str(out), include_stdlib=False, strict=True)
      self.assertIn("abstract", str(ctx.exception).lower())

  def test_abstract_body_must_be_ellipsis(self):
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(
        """from py2cpp import *

class Shape:
  @abstract
  def area(self) -> int:
    return 0

def main():
  pass
""",
        encoding="utf-8",
      )
      out = Path(tmp) / "generated"
      with self.assertRaises(Exception) as ctx:
        Translator.translate_file(str(py), output_dir=str(out), include_stdlib=False, strict=True)
      self.assertIn("abstract", str(ctx.exception).lower())


if __name__ == "__main__":
  unittest.main()
