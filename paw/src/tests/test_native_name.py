"""``@native_name``：Python 类名与 C++ 类名分离。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class NativeNameTests(unittest.TestCase):
  def _translate(self, body: str) -> str:
    src = f"""from py2cpp import native_name, new

@native_name("PyFoo")
class Foo:
  x: int

def probe():
{body}"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, _cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return Path(h_path).read_text(encoding="utf-8")

  def test_class_cpp_name(self):
    h = self._translate("  o: Foo = new()\n")
    self.assertIn("class PyFoo", h)
    self.assertNotIn("class Foo", h)


if __name__ == "__main__":
  unittest.main()
