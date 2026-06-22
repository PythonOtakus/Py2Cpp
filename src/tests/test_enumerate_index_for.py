"""``for i, x in enumerate(seq)`` 对可索引容器内联为 C++ 索引 for。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class EnumerateIndexForTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_list_enumerate_index_for(self):
    cpp = self._translate(
      '''
from py2cpp.util.list import list

def run(xs: list[int]) -> int:
  s: int = 0
  for i, x in enumerate(xs):
    if i == 1:
      s = x
  return s
''',
    )
    self.assertIn("for (PyInt fi", cpp)
    self.assertIn(".__getitem__", cpp)
    self.assertNotIn("enumerate_iterator", cpp)

  def test_enumerate_with_start(self):
    cpp = self._translate(
      '''
from py2cpp.util.list import list

def run(xs: list[int]) -> int:
  i: int = 0
  for idx, x in enumerate(xs, 5):
    i = idx
  return i
''',
    )
    self.assertIn("(5) + fi", cpp)
    self.assertNotIn("enumerate_iterator", cpp)

  def test_enumerate_reversed_list(self):
    cpp = self._translate(
      '''
from py2cpp.util.list import list

def run(xs: list[int]) -> int:
  v: int = 0
  for i, x in enumerate(reversed(xs)):
    v = x
  return v
''',
    )
    self.assertIn("__len__() - 1 - fi", cpp)
    self.assertNotIn("enumerate_iterator", cpp)


if __name__ == "__main__":
  unittest.main()
