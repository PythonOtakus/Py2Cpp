"""``long`` 的 ``//`` / ``%`` / ``/`` 须走实例 dunder，勿误用 ``PyInt`` 全局算子。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class LongBinopEmitTests(unittest.TestCase):
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

  def test_floordiv_long_dunder(self):
    cpp = self._translate(
      "  a: long = 7\n  b: long = 3\n  q: long = a // b\n  return int(q)\n",
    )
    self.assertTrue(".__floordiv__(" in cpp or "::__floordiv__(" in cpp)
    self.assertNotIn("(a // b)", cpp)

  def test_mod_long_dunder(self):
    cpp = self._translate(
      "  a: long = 7\n  b: long = 3\n  r: long = a % b\n  return int(r)\n",
    )
    self.assertTrue(".__mod__(" in cpp or "::__mod__(" in cpp)
    self.assertNotIn("(a % b)", cpp)

  def test_truediv_long_dunder(self):
    cpp = self._translate(
      "  a: long = 7\n  b: long = 3\n  return a / b\n",
    )
    self.assertTrue(".__truediv__(" in cpp or "::__truediv__(" in cpp)
    self.assertNotIn("(a / b)", cpp)


if __name__ == "__main__":
  unittest.main()
