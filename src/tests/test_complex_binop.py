"""``PyComplex`` 等类型的 ``/`` 可走全局 ``::__truediv__``（转发成员 dunder）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ComplexBinopEmitTests(unittest.TestCase):
  def _translate(self, body: str, *, extra: str = "") -> str:
    src = f"""from py2cpp import *
from py2cpp.numeric.complex import complex
{extra}

def probe():
{body}"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_unary_neg_complex_mul_uses_dunder(self):
    cpp = self._translate(
      "  z: complex = 1 + 1j\n  w: complex = (-z) * z\n  return w.real\n",
    )
    self.assertTrue(
      "operator*" in cpp.replace(" ", "")
      or ".__mul__(" in cpp
      or ".__rmul__(" in cpp,
    )
    self.assertNotIn("::__mul__(", cpp)

  def test_complex_truediv_uses_global_forward(self):
    cpp = self._translate(
      "  a: complex = 1 + 2j\n  b: complex = 3 + 4j\n  q: complex = a / b\n  return q.real\n",
    )
    self.assertIn("::__truediv__(", cpp)
    self.assertNotIn("(a / b)", cpp)

  def test_unannotated_call_quotient_uses_global_forward(self):
    cpp = self._translate(
      "  half: complex = new(0.5, 0)\n"
      "  a: complex = 1 + 0j\n  q: complex = a / half\n  return q.real\n",
    )
    self.assertIn("::__truediv__(", cpp)

  def test_module_const_complex_mul_uses_left_mul(self):
    cpp = self._translate(
      "  z: complex = 0.5 + 0.25j\n"
      "  w: complex = _i * z\n"
      "  return w.imag\n",
      extra="_i: complex = 1j",
    )
    self.assertIn(".__mul__(", cpp)
    self.assertNotIn(".__rmul__(_i)", cpp.replace(" ", ""))


if __name__ == "__main__":
  unittest.main()
