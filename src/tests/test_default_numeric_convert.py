"""``expand_default_numeric_convert`` 注入断言。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class DefaultNumericConvertTests(unittest.TestCase):
  def _translate(self, body: str, *, extra: str = "") -> str:
    src = f"""from py2cpp import *

{extra}

@copyable
class Box:
  def __init__(self, v: int = 0):
    self._v: int = v

  @immutable
  def __int__(self) -> int:
    return self._v

def probe() -> int:
{body}"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_injects_float_and_complex_from_int(self):
    cpp = self._translate("  b: Box = new(7)\n  return int(b)\n")
    self.assertIn("__float__()", cpp)
    self.assertIn("__complex__()", cpp)

  def test_float_ctor_uses_static_cast(self):
    cpp = self._translate(
      "  b: Box = new(3)\n  return float(b)\n",
    )
    self.assertIn("static_cast<PyFloat>", cpp)
    self.assertNotIn(".__float__()", cpp)

  def test_complex_ctor_uses_static_cast(self):
    cpp = self._translate(
      "  b: Box = new(5)\n  c: complex = complex(b)\n  return c.real\n",
      extra="from py2cpp.numeric.complex import complex",
    )
    self.assertIn("static_cast<PyComplex", cpp)
    self.assertNotIn(".__complex__()", cpp)

  def test_int_ctor_uses_static_cast(self):
    cpp = self._translate("  b: Box = new(7)\n  return int(b)\n")
    self.assertIn("static_cast<PyInt>", cpp)
    self.assertNotIn(".__int__()", cpp)


if __name__ == "__main__":
  unittest.main()
