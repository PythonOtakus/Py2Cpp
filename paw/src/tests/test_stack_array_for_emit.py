"""栈数组 ``for x in buf`` 索引 for 内联（含 ``Offset``）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class StackArrayForEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_stack_array_for_index_inline(self):
    cpp = self._translate(
      '''
def run(buf: int[:4]) -> int:
  total: int = 0
  for x in buf:
    total = total + x
  return total
''',
    )
    self.assertIn("for (PyInt fi", cpp)
    self.assertIn(".__getitem__", cpp)
    self.assertNotIn("PyStackArrayIterator", cpp)
    self.assertNotIn("while (true)", cpp)

  def test_stack_array_offset_for(self):
    cpp = self._translate(
      '''
def run(seg: int[1:3]) -> int:
  total: int = 0
  for x in seg:
    total = total + x
  return total
''',
    )
    self.assertIn("(1) + (", cpp)
    self.assertNotIn("PyStackArrayIterator", cpp)


if __name__ == "__main__":
  unittest.main()
