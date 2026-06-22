"""类形参自动 ``using Alias = _Alias`` 与 C++ 模板 ``_`` 前缀。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class TypeParamAutoAliasTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, _cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return h_path.read_text(encoding="utf-8")

  def test_class_template_underscore_and_using(self):
    text = self._translate(
      '''
from py2cpp import *

class Box[Element]:
  value: Element
'''
    )
    self.assertRegex(
      text,
      re.compile(
        r"template<typename _Element>\n"
        r"  class Box\n"
        r"  \{\n"
        r"    using Element = _Element;",
        re.MULTILINE,
      ),
    )

  def test_s43_rejects_manual_forward(self):
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(
        '''
from py2cpp import *

class Box[T]:
  type Element = T
  value: T
''',
        encoding="utf-8",
      )
      with self.assertRaises(Exception) as ctx:
        Translator.translate_file(str(py), output_dir=str(out), include_stdlib=True)
      self.assertIn("S43", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
