"""全局 ``abs``：标量三目、``::py2cpp::abs``、``__abs__``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class AbsBuiltinEmitTests(unittest.TestCase):
  def _translate(self, body: str, *, extra: str = "") -> str:
    src = f"""from py2cpp import varint
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

  def test_abs_pyint_ternary(self):
    cpp = self._translate("  n: int = -3\n  return abs(n)\n")
    self.assertIn("n < 0 ? -n : n", cpp)
    self.assertNotIn("::py2cpp::py_abs", cpp)

  def test_abs_varint_dunder(self):
    cpp = self._translate("  v: varint = varint('-5')\n  return abs(v)\n")
    self.assertIn("__abs__()", cpp)

  def test_abs_self_uses_dunder(self):
    cpp = self._translate(
      "  return abs(self)\n",
      extra="""from py2cpp import Self, copyable

@copyable
class Box:
  def snap(self) -> int:
    return abs(self)
  def __abs__(self) -> int:
    return 1
""",
    )
    self.assertIn("this->__abs__()", cpp)


if __name__ == "__main__":
  unittest.main()
