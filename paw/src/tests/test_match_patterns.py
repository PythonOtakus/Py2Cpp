"""``match`` 序列/映射模式代码生成。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class MatchPatternEmitTests(unittest.TestCase):
  def _translate(self, body: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_tuple_fixed_get(self):
    cpp = self._translate(
      '''
def f(p: (int, int)) -> int:
  match p:
    case [a, b]:
      return a + b
    case _:
      return 0
'''
    )
    self.assertIn("template get<0>()", cpp)
    self.assertIn("template get<1>()", cpp)

  def test_list_star_suffix_negative_index(self):
    cpp = self._translate(
      '''
def f(xs: list[int]) -> int:
  match xs:
    case [a, *mid, b]:
      return a + b
    case _:
      return 0
'''
    )
    self.assertIn("__getitem__(-1)", cpp)
    self.assertIn("PySlice<int, int>", cpp)

  def test_tuple_star_bind_is_tuple(self):
    cpp = self._translate(
      '''
def f(t: (int, int, int)) -> int:
  match t:
    case [a, *mid, c]:
      return mid[0]
    case _:
      return 0
'''
    )
    self.assertIn("PyTuple<", cpp)
    self.assertIn("template get<1>()", cpp)

  def test_mapping_literal_key(self):
    cpp = self._translate(
      '''
def f(cfg: dict[str, int]) -> int:
  match cfg:
    case {"port": p}:
      return p
    case _:
      return 0
'''
    )
    self.assertIn("__contains__", cpp)
    self.assertIn("__getitem__", cpp)

  def test_new_class_keyword_literal(self):
    cpp = self._translate(
      '''
@dataclass
class Point:
  x: int = 0
  y: int = 0

def f(p: Point) -> int:
  match p:
    case new(x=0, y=y):
      return y
    case new(x=x, y=y):
      return x + y
    case _:
      return -1
'''
    )
    self.assertIn("(p.x) == (0)", cpp)
    self.assertIn("p.y", cpp)

  def test_new_class_readonly_property(self):
    cpp = self._translate(
      '''
class Box:
  value: int @property = 0

def f(b: Box) -> int:
  match b:
    case new(value=1):
      return 1
    case _:
      return 0
'''
    )
    self.assertIn("(b.value__get()) == (1)", cpp)

  def test_new_class_match_or_rejects_mismatched_captures(self):
    with self.assertRaises(Exception):
      self._translate(
        '''
@dataclass
class Point:
  x: int = 0
  y: int = 0

def f(p: Point) -> int:
  match p:
    case new(x=a, y=b) | new(x=c, y=d):
      return 0
    case _:
      return -1
'''
      )

  def test_new_match_or_allows_reordered_captures(self):
    cpp = self._translate(
      '''
@dataclass
class Point:
  x: int = 0
  y: int = 0

def f(p: Point) -> int:
  match p:
    case new(x=a, y=b) | new(y=b, x=a):
      return a + b
    case _:
      return 0
'''
    )
    self.assertIn("else if", cpp)
    self.assertIn("PyInt a;", cpp)
    self.assertIn("a = p.x", cpp)

  def test_sequence_match_or_reordered_captures(self):
    cpp = self._translate(
      '''
def f(xs: list[int]) -> int:
  match xs:
    case [a, b] | [b, a]:
      return a + b
    case _:
      return 0
'''
    )
    self.assertIn("else if", cpp)

  def test_sequence_match_or(self):
    cpp = self._translate(
      '''
def f(xs: list[int]) -> int:
  match xs:
    case [1, x] | [2, x]:
      return x
    case _:
      return 0
'''
    )
    self.assertIn("||", cpp)
    self.assertIn("auto x =", cpp)
    self.assertEqual(cpp.count("auto x ="), 1)

  def test_mapping_match_or(self):
    cpp = self._translate(
      '''
def f(cfg: dict[str, int]) -> int:
  match cfg:
    case {"a": 1, "b": v} | {"a": 2, "b": v}:
      return v
    case _:
      return 0
'''
    )
    self.assertIn("||", cpp)
    self.assertIn("auto v =", cpp)
    self.assertEqual(cpp.count("auto v ="), 1)

  def test_new_class_match_or(self):
    cpp = self._translate(
      '''
@dataclass
class Point:
  x: int = 0
  y: int = 0

def f(p: Point) -> int:
  match p:
    case new(x=1) | new(x=2):
      return 0
    case _:
      return -1
'''
    )
    self.assertIn("||", cpp)
    self.assertIn("(p.x) == (1)", cpp)
    self.assertIn("(p.x) == (2)", cpp)

  def test_optional_match_sugar(self):
    cpp = self._translate(
      '''
from py2cpp.core.optional import Optional

def f(opt: Optional[int]) -> int:
  match opt:
    case None:
      return -1
    case 7:
      return 0
    case v:
      return v
'''
    )
    self.assertIn("PyOptional<PyInt>::Enum::None_", cpp)
    self.assertIn("PyOptional<PyInt>::Enum::Some", cpp)
    self.assertIn("_variant_Some().value", cpp)
    self.assertIn(".value == 7", cpp)

  def test_enum_match_or(self):
    cpp = self._translate(
      '''
from py2cpp import enum

@enum
class Mode:
  A = 1
  B = 2

def f(m: Mode) -> int:
  match m:
    case Mode.A | Mode.B:
      return 1
    case _:
      return 0
'''
    )
    self.assertIn("||", cpp)
    self.assertIn("Mode::A", cpp)
    self.assertIn("Mode::B", cpp)


if __name__ == "__main__":
  unittest.main()
