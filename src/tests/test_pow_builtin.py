"""全局 ``pow``：``::pow`` 分发与三参数模幂。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class PowBuiltinEmitTests(unittest.TestCase):
  def _translate(self, body: str) -> str:
    src = f"""from py2cpp import *

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

  def test_pow_pyint_two_args(self):
    cpp = self._translate("  return pow(2, 10)\n")
    self.assertIn("::pow(2, 10)", cpp)

  def test_pow_pyint_three_args(self):
    cpp = self._translate("  return pow(3, -1, 5)\n")
    self.assertIn("::pow(3, -1, 5)", cpp)

  def test_pow_long_star_star(self):
    cpp = self._translate("  a: long = 3\n  b: long = 2\n  return a ** b\n")
    self.assertIn(".__pow__(b)", cpp)
    self.assertNotIn("__pow__(a", cpp)

  def test_pow_long_three_args(self):
    cpp = self._translate(
      "  a: long = 3\n  m: long = 5\n  return pow(a, -1, m)\n",
    )
    self.assertIn("::pow(a, -1, m)", cpp)

  def test_pow_pyint_star_star(self):
    cpp = self._translate("  return 2 ** 10\n")
    self.assertIn("pow(2, 10)", cpp)


if __name__ == "__main__":
  unittest.main()
