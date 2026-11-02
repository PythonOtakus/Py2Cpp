"""翻译失败信息含文件路径与行号。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translation_error import TranslationError, format_translation_failure
from src.translator import Translator


class TranslationErrorFormatTests(unittest.TestCase):
  def test_emit_failure_includes_line(self):
    src = '''\
from py2cpp import *

def run() -> None:
  xs: list[int] = [1, 2, 3]
  y = new(x=1)
'''
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(Exception) as ctx:
        Translator.translate_file(str(py), output_dir=tmp, include_stdlib=False)
    msg = format_translation_failure(ctx.exception, entry_path=py)
    self.assertIn("mod.py:5:", msg)
    self.assertIn("new()", msg)

  def test_format_shows_source_line(self):
    err = TranslationError(
      "示例错误",
      location=__import__(
        "src.translation_error", fromlist=["SourceLocation"]
      ).SourceLocation(
        display="test/util/test_list.py",
        absolute=Path(__file__).resolve().parents[2] / "test/util/test_list.py",
        lineno=1,
      ),
    )
    text = format_translation_failure(err)
    self.assertIn("test/util/test_list.py:1:", text)


if __name__ == "__main__":
  unittest.main()
