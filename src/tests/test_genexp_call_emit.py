"""Iterable 形参 + genexp 实参：用户函数调用点内联。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translation_error import TranslationError
from src.translator import Translator


class GenexpCallEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_total_genexp_inline(self):
    cpp = self._translate(
      '''
from py2cpp import Iterable

def total[T](xs: Iterable[T], start: int = 0) -> int:
  acc: int = start
  for x in xs:
    acc += x
  return acc

def run(data: list[int]) -> int:
  base: int = total(data)
  scaled: int = total(x * 2 for x in data)
  return base + scaled
''',
    )
    self.assertIn("[&]() ->", cpp)
    self.assertIn("(x * 2)", cpp)
    self.assertNotIn(".append(", cpp)
    run_part = cpp.split("run(", 1)[-1] if "run(" in cpp else cpp
    self.assertNotIn("total(x", run_part)
    inline_part = cpp.split("[&]() ->", 1)[-1].split("return base", 1)[0]
    self.assertIn(".__getitem__(", inline_part)
    self.assertNotIn("__iter__", inline_part)

  def test_total_list_normal_call(self):
    cpp = self._translate(
      '''
from py2cpp import Iterable

def total[T](xs: Iterable[T]) -> int:
  acc: int = 0
  for x in xs:
    acc += x
  return acc

def run(data: list[int]) -> int:
  a: int = total(data)
  b: int = total(data)
  return a + b
''',
    )
    self.assertIn("total(", cpp)

  def test_non_iterable_genexp_fails(self):
    with self.assertRaises(TranslationError):
      self._translate(
        '''
def pick(xs: list[int]) -> int:
  acc: int = 0
  for x in xs:
    acc += x
  return acc

def run(data: list[int]) -> int:
  return pick(x for x in data)
''',
      )

  def test_unanalyzable_body_fails(self):
    with self.assertRaises(TranslationError):
      self._translate(
        '''
from py2cpp import Iterable

def bad[T](xs: Iterable[T]) -> int:
  if xs:
    return 1
  return 0

def run(data: list[int]) -> int:
  return bad(x for x in data)
''',
      )

  def test_two_iterable_genexp_fails(self):
    with self.assertRaises(TranslationError):
      self._translate(
        '''
from py2cpp import Iterable

def merge_first[T](a: Iterable[T], b: Iterable[T]) -> int:
  s: int = 0
  for x in a:
    s += x
  return s

def run(xs: list[int], ys: list[int]) -> int:
  return merge_first((x for x in xs), (y for y in ys))
''',
      )


if __name__ == "__main__":
  unittest.main()
