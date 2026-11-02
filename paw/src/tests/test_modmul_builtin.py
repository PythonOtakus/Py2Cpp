"""全局 ``modmul``：``::modmul`` 分发与 ``__modmul__``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ModmulBuiltinEmitTests(unittest.TestCase):
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

  def test_modmul_pyint(self):
    cpp = self._translate("  return modmul(1000000005, 2, 1000000007)\n")
    self.assertIn("::modmul(1000000005, 2, 1000000007)", cpp)

  def test_modmul_long(self):
    cpp = self._translate(
      "  a: long = 3\n  b: long = 4\n  m: long = 11\n  return modmul(a, b, m)\n",
    )
    self.assertIn("::modmul(a, b, m)", cpp)


if __name__ == "__main__":
  unittest.main()
