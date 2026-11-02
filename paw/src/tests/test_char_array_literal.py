"""``char[:]`` / ``char[:N]`` 由字符串或列表字面量初始化。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class CharArrayLiteralEmitTests(unittest.TestCase):
  def _translate(self, body: str) -> str:
    src = f"""from py2cpp import char

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

  def test_char_heap_array_from_str_literal(self):
    cpp = self._translate("  buf: char[:] = 'Hi'\n  return len(buf)\n")
    self.assertIn("PyArray<PyChar>", cpp)
    self.assertIn("PyChar(72)", cpp)
    self.assertIn("PyChar(105)", cpp)
    self.assertIn("__setitem__(0,", cpp)

  def test_char_stack_array_from_str_literal(self):
    cpp = self._translate("  buf: char[:2] = 'OK'\n  return len(buf)\n")
    self.assertIn("PyStackArray<PyChar", cpp)
    self.assertIn("PyChar(79)", cpp)
    self.assertIn("PyChar(75)", cpp)

  def test_char_heap_array_from_empty_str_literal(self):
    cpp = self._translate("  buf: char[:] = ''\n  return len(buf)\n")
    self.assertIn("PyArray<PyChar>(0)", cpp)

  def test_char_heap_array_from_list_literal(self):
    cpp = self._translate("  buf: char[:] = [72, 105]\n  return len(buf)\n")
    self.assertIn("PyArray<PyChar>(2)", cpp)
    self.assertIn("__setitem__(0, 72)", cpp)
    self.assertIn("__setitem__(1, 105)", cpp)

  def test_int_heap_array_from_list_literal(self):
    cpp = self._translate("  buf: int[:] = [1, 2, 3]\n  return len(buf)\n")
    self.assertIn("PyArray<PyInt>(3)", cpp)
    self.assertIn("__setitem__(0, 1)", cpp)
    self.assertIn("__setitem__(2, 3)", cpp)

  def test_self_field_heap_array_from_list_literal(self):
    src = """from py2cpp import char, copyable

@copyable
class Box:
  data: char[:]

  def __init__(self, c: char):
    self.data = [c]
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
    self.assertIn("this->data = PyArray<PyChar>(1)", cpp)
    self.assertIn("this->data.__setitem__(0,", cpp)

  def test_self_field_empty_char_heap_skips_init(self):
    src = """from py2cpp import char, copyable

@copyable
class Buf:
  def __init__(self):
    self._buf: char[:] = ""
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
    self.assertNotIn("__move__", cpp)
    self.assertNotIn("PyArray<PyChar>(0)", cpp)

  def test_self_field_char_heap_from_str_literal_no_move(self):
    src = """from py2cpp import char, copyable

@copyable
class Box:
  def __init__(self):
    self.data: char[:] = "Hi"
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
    self.assertIn("this->data = PyArray<PyChar>(2)", cpp)
    self.assertNotIn("__move__", cpp)


if __name__ == "__main__":
  unittest.main()
