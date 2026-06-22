"""聚合内建 + 生成器表达式：IIFE 内嵌套 for，无临时容器。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class BuiltinAggregateGenExpEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_sum_genexp_nested(self):
    cpp = self._translate(
      '''
def run(xs: list[int], ys: list[int]) -> int:
  return sum(x * y for x in xs for y in ys)
''',
    )
    self.assertIn("for (PyInt", cpp)
    self.assertIn("(x * y)", cpp)
    self.assertNotIn(".append(", cpp)
    self.assertNotIn("while (true)", cpp)

  def test_stack_array_offset_genexp(self):
    cpp = self._translate(
      '''
def run(seg: int[1:3]) -> int:
  return sum(x for x in seg)
''',
    )
    self.assertIn("(1) + (", cpp)
    self.assertNotIn("PyStackArrayIterator", cpp)

  def test_genexp_outside_aggregate_fails(self):
    from src.translation_error import TranslationError

    with self.assertRaises(TranslationError):
      self._translate(
        '''
def run(xs: list[int]) -> int:
  g = (x for x in xs)
  return 0
''',
      )


if __name__ == "__main__":
  unittest.main()
