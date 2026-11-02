"""全局 ``__cmp__``：标量三目、``py_cmp``、``__cmp__`` dunder。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class CmpBuiltinEmitTests(unittest.TestCase):
  def _translate(self, body: str, *, extra: str = "") -> str:
    src = f"""from py2cpp import *
{extra}

def probe():
{body}"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_cmp_pyint_ternary(self):
    cpp = self._translate("  return __cmp__(1, 2)\n")
    self.assertIn("1 < 2 ? -1", cpp)
    self.assertNotIn("::py2cpp::py_cmp", cpp)

  def test_cmp_long_dunder(self):
    cpp = self._translate(
      "  a: long = long('3')\n  b: long = long('5')\n"
      "  return __cmp__(a, b)\n",
    )
    self.assertIn("__cmp__(b)", cpp)
    self.assertNotIn("::py2cpp::py_cmp", cpp)

  def test_cmp_equal_scalar(self):
    cpp = self._translate("  return __cmp__(4, 4)\n")
    self.assertIn("4 < 4 ? -1", cpp)

  def test_cmp_or_chain_short_circuit(self):
    cpp = self._translate(
      "  return __cmp__(1, 2) or __cmp__(3, 3) or __cmp__(4, 5)\n",
    )
    self.assertIn("1 < 2 ? -1", cpp)
    self.assertIn("3 < 3 ? -1", cpp)
    self.assertIn(" ? ", cpp)


if __name__ == "__main__":
  unittest.main()
