"""``@union`` 泛型类内 ``type`` 别名生成 ``using``。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class UnionTypeAliasTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, _cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return h_path.read_text(encoding="utf-8")

  def test_union_class_type_alias_using(self):
    text = self._translate(
      '''
from py2cpp import *

@union
class Box[Value]:
  @variant
  class Some:
    value: Value
'''
    )
    self.assertRegex(
      text,
      re.compile(
        r"template<typename _Value>\n"
        r"  class Box\n"
        r"  \{\n"
        r"  using Value = _Value;\n"
        r"\n"
        r"  private:",
        re.MULTILINE,
      ),
    )


if __name__ == "__main__":
  unittest.main()
