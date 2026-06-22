"""类体字段默认值 ``new(...)`` / ``""`` 在声明阶段须用字段类型推断，勿 ``visit(Call)``。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ClassFieldDefaultMakeTests(unittest.TestCase):
  def _translate_class(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, _cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return h_path.read_text(encoding="utf-8")

  def test_class_field_empty_char_heap_default(self):
    text = self._translate_class(
      '''
from py2cpp import char

class Enc:
  _buf: char[:] = ""
'''
    )
    self.assertRegex(
      text,
      re.compile(r"_buf\s*=\s*PyArray<PyChar>\(0\)"),
    )

  def test_class_field_new_default(self):
    text = self._translate_class(
      '''
from py2cpp import char, new

class Enc:
  _buf: char[:] = new()
'''
    )
    self.assertRegex(
      text,
      re.compile(r"_buf\s*=\s*PyArray<PyChar>\(\)"),
    )

  def test_class_field_empty_dict_str_str_default(self):
    text = self._translate_class(
      '''
from py2cpp import *

@copyable
class Opts:
  headers: dict[str, str] = {}
'''
    )
    self.assertRegex(
      text,
      re.compile(r"PyDict<PyStr,\s*PyStr>\s+headers\s*=\s*PyDict<PyStr,\s*PyStr>\(\)"),
    )
    self.assertNotIn("__dict_lit", text)


if __name__ == "__main__":
  unittest.main()
