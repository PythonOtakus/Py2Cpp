"""``__add__`` 等 dunder 自动生成 C++ ``operator`` 重载（含非 ``@immutable`` 方法）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.analysis.analyzer import SemanticAnalyzer
from src.emit.dunder_ops_emit import emit_class_operator_overloads
from src.translator import Translator


class OperatorFromDunderTests(unittest.TestCase):
  def test_non_immutable_add_emits_operator_plus(self):
    src = """
from py2cpp import copyable

@copyable
class Widget:
  def __add__(self, other: Self) -> Self:
    return other

def use(a: Widget, b: Widget) -> Self:
  return a + b
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, _ = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      h = h_path.read_text(encoding="utf-8")
      compact = h.replace(" ", "")
      self.assertIn("operator+(constWidget&other)", compact)
      self.assertIn("return__add__(other)", compact)

  def test_ne_method_body_uses_eq_negation_not_pointer_compare(self):
    src = """
from py2cpp import immutable, new, Self

class Widget:
  @immutable
  def __eq__(self, other: Self) -> bool:
    return True

  @immutable
  def __ne__(self, other: Self) -> bool:
    return not (self == other)

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
      self.assertIn("(!(*this==other))", compact)
      self.assertNotIn("this!=other", compact)

  def test_emit_class_operator_overloads_direct(self):
    src = """
from py2cpp import copyable, immutable, Self

@copyable
class Num:
  @immutable
  def __eq__(self, other: Self) -> bool:
    return True

  def __add__(self, other: Self) -> Self:
    return other
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      tr = Translator("mod", str(py))
      tr._parse_modules([("mod", src)])
      SemanticAnalyzer().analyze(tr)
      info = tr.classes["Num"]
      lines = emit_class_operator_overloads(info)
      text = "\n".join(lines)
      compact = text.replace(" ", "")
      self.assertIn("operator+(constNum&other)", compact)
      self.assertNotIn("operator+(constNum&other)const", compact)
      self.assertIn("booloperator==(constNum&other)const", compact)


if __name__ == "__main__":
  unittest.main()
