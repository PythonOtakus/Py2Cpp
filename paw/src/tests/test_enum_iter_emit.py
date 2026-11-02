"""``len(Enum)`` / ``for x in Enum`` 内联 emit。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class EnumIterEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_len_enum_class(self):
    cpp = self._translate(
      '''
from py2cpp import enum

@enum
class Mode:
  OFF = 0
  ON = ...
  DEBUG = ...

def n() -> int:
  return len(Mode)
''',
    )
    self.assertIn("return 3", cpp)
    self.assertNotIn("__len__", cpp)

  def test_for_enum_class(self):
    cpp = self._translate(
      '''
from py2cpp import enum

@enum
class Mode:
  OFF = 0
  ON = ...
  DEBUG = ...

def run() -> int:
  n: int = 0
  for m in Mode:
    n += 1
  return n
''',
    )
    self.assertRegex(cpp, r"static const Mode enum_tbl\d+\[3\]")
    self.assertIn("Mode::OFF", cpp)
    self.assertIn("for (PyInt ei", cpp)
    self.assertNotIn("__iter__", cpp)


if __name__ == "__main__":
  unittest.main()
