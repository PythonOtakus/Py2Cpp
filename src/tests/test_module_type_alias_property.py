"""模块级 ``type`` 别名：``@property`` 仍派发 ``<name>__get()``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ModuleTypeAliasPropertyTests(unittest.TestCase):
  def _translate(self, body: str) -> str:
    src = f"""from py2cpp import new
from py2cpp.numeric.modint import ModInt

type Int = ModInt[int, 1000000007]

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

  def test_property_via_type_alias(self):
    cpp = self._translate("  a: Int = new(1)\n  x: Int = a.inv\n")
    self.assertIn("inv__get()", cpp)
    self.assertNotIn(".inv", cpp)


if __name__ == "__main__":
  unittest.main()
