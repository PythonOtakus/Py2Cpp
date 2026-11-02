"""类内 ``type`` 别名 ``using`` 与成员同级缩进（``public:`` 下 ``_use_indent``）。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ClassTypeUsingIndentTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, _cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return h_path.read_text(encoding="utf-8")

  def test_type_alias_using_indented_with_members(self):
    text = self._translate(
      '''
from py2cpp import *

class Box:
  type Element = int
  value: int
'''
    )
    self.assertRegex(
      text,
      re.compile(
        r"public:\n"
        r"(?:    using .+\n)*"
        r"    using Element = PyInt;\n"
        r"    PyInt value;",
        re.MULTILINE,
      ),
    )
    self.assertNotRegex(
      text,
      re.compile(r"public:\n  using Element", re.MULTILINE),
    )

  def test_generator_single_public_with_indented_associated_types(self):
    text = self._translate(
      '''
from py2cpp import *

def gen_three() -> GeneratorType[int, None, None]:
  yield 1
'''
    )
    self.assertRegex(
      text,
      re.compile(
        r"class gen_three_generator\n  \{\n  public:\n"
        r"    using Element = PyInt;\n"
        r"    using SendType = PyNone;\n"
        r"    using ReturnType = PyNone;",
        re.MULTILINE,
      ),
    )
    self.assertNotIn(
      "using ReturnType = PyNone;\n  public:",
      text,
    )


if __name__ == "__main__":
  unittest.main()
