"""并行多目标赋值 ``a, b = b, a`` / ``xs[i], xs[j] = xs[j], xs[i]``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class ParallelAssignEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False, strict=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_int_rotate(self):
    src = '''
def f():
  a: int = 1
  b: int = 2
  c: int = 3
  a, b, c = b, c, a + b
'''
    cpp = self._translate(src)
    self.assertIn("par", cpp)
    self.assertIn("a = par", cpp)
    self.assertIn("b = par", cpp)
    self.assertIn("c = par", cpp)

  def test_call_return_unpack(self):
    src = '''
from py2cpp import *

def triple() -> (int, int, int):
  return (1, 2, 3)

def f():
  a: int = 0
  b: int = 0
  c: int = 0
  a, b, c = triple()
'''
    cpp = self._translate(src)
    self.assertIn("pytuple_unpack", cpp)
    self.assertIn("template get<0>()", cpp)
    self.assertIn("template get<2>()", cpp)

  def test_subscript_swap(self):
    src = '''
from py2cpp.util.list import list

def f(xs: list[int]):
  xs[0], xs[1] = xs[1], xs[0]
'''
    cpp = self._translate(src)
    self.assertIn("par", cpp)
    self.assertIn("__setitem__", cpp)
    self.assertIn("xs.__setitem__(0", cpp)
    self.assertIn("xs.__setitem__(1", cpp)


if __name__ == "__main__":
  unittest.main()
