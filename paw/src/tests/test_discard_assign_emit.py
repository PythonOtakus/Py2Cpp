"""``_ = expr`` 丢弃赋值须 ``(void)(expr)``，勿复用带类型的 ``_`` 变量。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class DiscardAssignEmitTests(unittest.TestCase):
  def test_mixed_type_discard_uses_void_cast(self):
    src = """
from py2cpp import *

def discard_mixed(buffering: int, errors: str, newline: str) -> None:
  _ = buffering
  _ = errors
  _ = newline
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("(void)(buffering)", cpp)
      self.assertIn("(void)(errors)", cpp)
      self.assertIn("(void)(newline)", cpp)
      self.assertNotIn("PyInt _", cpp)
      self.assertNotIn("PyStr _", cpp)


if __name__ == "__main__":
  unittest.main()
