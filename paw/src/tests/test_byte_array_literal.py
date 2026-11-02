"""``byte[:]`` / ``bytes`` 由 ``b\"...\"`` 字面量初始化。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ByteArrayLiteralEmitTests(unittest.TestCase):
  def _translate(self, body: str) -> str:
    src = f"""from py2cpp import byte, bytes

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

  def test_byte_heap_array_from_empty_bytes_literal(self):
    cpp = self._translate("  buf: byte[:] = b''\n  return len(buf)\n")
    self.assertIn("PyArray<PyByte>(0)", cpp)

  def test_byte_heap_array_from_bytes_literal(self):
    cpp = self._translate("  buf: byte[:] = b'Hi'\n  return len(buf)\n")
    self.assertIn("PyArray<PyByte>", cpp)
    self.assertIn("PyByte(72)", cpp)
    self.assertIn("PyByte(105)", cpp)

  def test_bytes_from_bytes_literal(self):
    cpp = self._translate("  enc: bytes = b'Hi'\n  return len(enc)\n")
    self.assertIn("bytes_from_literal", cpp)
    self.assertIn("{72, 105}", cpp)

  def test_bytes_ctor_from_bytes_literal(self):
    cpp = self._translate("  enc: bytes = bytes(b'OK')\n  return len(enc)\n")
    self.assertIn("bytes_from_literal", cpp)


if __name__ == "__main__":
  unittest.main()
