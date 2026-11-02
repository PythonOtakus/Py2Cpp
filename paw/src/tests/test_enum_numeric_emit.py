"""``@enum`` 标量转换：``int(E.MEM)`` / ``E(n)`` emit。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class EnumNumericEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      return h_path.read_text(encoding="utf-8") + cpp_path.read_text(encoding="utf-8")

  def test_int_enum_member_uses_pyint_wrapper(self):
    cpp = self._translate(
      '''
from py2cpp import enum

@enum
class Mode:
  OFF = 0
  ON = ...

def f() -> int:
  return int(Mode.ON)
''',
    )
    self.assertIn("struct ModePyInt", cpp)
    self.assertIn("explicit operator PyInt() const", cpp)
    self.assertIn("static_cast<PyInt>(ModePyInt{", cpp)
    self.assertIn("Mode::ON", cpp)

  def test_enum_ctor_from_int(self):
    cpp = self._translate(
      '''
from py2cpp import enum

@enum
class Mode:
  OFF = 0
  ON = ...

def f() -> int:
  return int(Mode(1))
''',
    )
    self.assertIn("static_cast<Mode>(static_cast<PyInt>(1))", cpp)

  def test_int64_enum_scalar_wrapper(self):
    cpp = self._translate(
      '''
from py2cpp import enum, int64

@enum
class Wide(int64):
  LO = 1
  HI = ...

def f() -> int:
  return int(Wide.LO)
''',
    )
    self.assertIn("struct WidePyInt64", cpp)
    self.assertIn("explicit operator PyInt64() const", cpp)
    self.assertIn("static_cast<PyInt>(static_cast<PyInt64>(WidePyInt64{", cpp)
    self.assertIn("Wide::LO", cpp)

  def test_int64_enum_ctor(self):
    cpp = self._translate(
      '''
from py2cpp import enum, int64

@enum
class Wide(int64):
  LO = 1
  HI = ...

def f() -> int:
  return int(Wide(1))
''',
    )
    self.assertIn("static_cast<Wide>(static_cast<PyInt64>(1))", cpp)


if __name__ == "__main__":
  unittest.main()
