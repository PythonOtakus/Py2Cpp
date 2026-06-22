"""``chr`` / ``ord`` 与 ``byte`` / ``PyByte`` 译器发射。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.analyzer import SemanticAnalyzer
from src.translator import Translator


def _emit_return(body: str, *, entry: str = "mod") -> str:
  mod_src = f"from py2cpp import char, byte\n\ndef probe():\n{body}"
  tree = ast.parse(mod_src)
  func = tree.body[1]
  assert isinstance(func, ast.FunctionDef)
  ret = func.body[-1]
  assert isinstance(ret, ast.Return) and ret.value is not None
  tr = Translator(entry, f"{entry}.py")
  tr.entry_module_path = entry
  tr._parse_modules([(entry, mod_src)])
  SemanticAnalyzer().analyze(tr)
  return tr.visit(ret.value)


class ChrOrdEmitTests(unittest.TestCase):
  def test_chr_variable_uses_global_chr(self):
    out = _emit_return("  i: int = 65\n  return chr(i)\n")
    self.assertIn("::chr(i)", out.replace(" ", ""))

  def test_chr_folded_literal(self):
    out = _emit_return("  return chr(65)\n")
    self.assertIn('PyStr("A")', out.replace(" ", ""))
    self.assertNotIn("::chr", out)

  def test_ord_literal_folds_to_pychar(self):
    out = _emit_return("  return ord('a')\n")
    compact = out.replace(" ", "")
    self.assertIn("PyChar(97)", compact)
    self.assertNotIn("::ord", compact)

  def test_ord_literal_folds_in_char_compare(self):
    out = _emit_return("  c: char = 97\n  return c == ord('a')\n")
    compact = out.replace(" ", "")
    self.assertIn("c==97", compact)
    self.assertNotIn("::ord", compact)

  def test_ord_non_literal_raises(self):
    mod_src = 'from py2cpp import char\n\ndef probe():\n  c: char = 65\n  return ord(c)\n'
    tree = ast.parse(mod_src)
    func = tree.body[1]
    ret = func.body[-1]
    assert isinstance(ret, ast.Return) and ret.value is not None
    tr = Translator("mod", "mod.py")
    tr._parse_modules([("mod", mod_src)])
    SemanticAnalyzer().analyze(tr)
    with self.assertRaises(NotImplementedError):
      tr.visit(ret.value)

  def test_char_eq_single_char_str_literal(self):
    out = _emit_return("  c: char = 97\n  return c == 'a'\n")
    compact = out.replace(" ", "")
    self.assertIn("c==PyChar(97)", compact)
    self.assertNotIn("::ord", compact)

  def test_int_eq_single_char_str_literal(self):
    out = _emit_return("  i: int = 116\n  return i == 't'\n")
    compact = out.replace(" ", "")
    self.assertIn("i==116", compact)

  def test_char_eq_single_char_str_uses_pychar(self):
    mod_src = (
      "class C:\n"
      "  s: str\n"
      "  def probe(self) -> bool:\n"
      "    return self.s[self.pos] == '\"'\n"
    )
    tree = ast.parse(mod_src)
    cls = tree.body[0]
    assert isinstance(cls, ast.ClassDef)
    func = next(n for n in cls.body if isinstance(n, ast.FunctionDef))
    ret = func.body[0]
    assert isinstance(ret, ast.Return) and ret.value is not None
    tr = Translator("mod", "mod.py")
    tr._parse_modules([("mod", mod_src)])
    SemanticAnalyzer().analyze(tr)
    tr.class_info = tr.classes["C"]
    out = tr.visit(ret.value)
    self.assertIn("== PyChar(", out)
    self.assertNotIn('== PyStr("\\"")', out.replace(" ", ""))

  def test_char_ctor_from_int(self):
    out = _emit_return("  return char(0)\n")
    compact = out.replace(" ", "")
    self.assertIn("PyChar(0)", compact)

  def test_byte_ctor_from_int(self):
    out = _emit_return("  return byte(0)\n")
    compact = out.replace(" ", "")
    self.assertIn("PyByte(0)", compact)

  def test_byte_ctor_from_char(self):
    out = _emit_return("  c: char = 65\n  return byte(c)\n")
    compact = out.replace(" ", "")
    self.assertIn("PyByte(pychar_to_byte(c))", compact)

  def test_int64_ctor_static_cast(self):
    out = _emit_return("  x: int = 42\n  return int64(x)\n")
    compact = out.replace(" ", "")
    self.assertIn("static_cast<PyInt64>(x)", compact)

  def test_float64_ctor_static_cast(self):
    out = _emit_return("  x: float = 1.5\n  return float64(x)\n")
    compact = out.replace(" ", "")
    self.assertIn("static_cast<PyFloat64>(x)", compact)


if __name__ == "__main__":
  unittest.main()
