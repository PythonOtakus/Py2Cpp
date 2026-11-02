"""字面量容器内联：dict / set / list / str。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class DictLiteralLookupTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    if "from py2cpp import" not in src:
      src = "from py2cpp import *\n\n" + src
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_subscript_const_keys_ternary_or_if(self):
    cpp = self._translate(
      '''
def f(k: int) -> int:
  return {1: 10, 2: 20}[k]
'''
    )
    self.assertIn("k == 1", cpp)
    self.assertNotIn("__setitem__", cpp)

  def test_get_const_keys_nested_ternary(self):
    cpp = self._translate(
      '''
def g(k: int) -> int:
  return {1: 10, 2: 20}.get(k, -1)
'''
    )
    self.assertIn("k == 1 ? 10", cpp)
    self.assertIn("k == 2 ? 20", cpp)
    self.assertIn("-1", cpp)
    self.assertNotIn("__setitem__", cpp)

  def test_set_literal_in_or_chain(self):
    cpp = self._translate(
      '''
def f(c: int) -> bool:
  return c in {9, 10, 32}
'''
    )
    self.assertIn("c == 9", cpp)
    self.assertIn("||", cpp)
    self.assertNotIn(".add(", cpp)

  def test_set_literal_attr_in_or_chain(self):
    cpp = self._translate(
      '''
@enum
class KindEnum:
  A = 0
  B = 1

def f(k: KindEnum) -> bool:
  return k in {KindEnum.A, KindEnum.B}
'''
    )
    self.assertIn("KindEnum::A", cpp)
    self.assertIn("||", cpp)
    self.assertNotIn("PySet<", cpp)
    self.assertNotIn(".add(", cpp)

  def test_set_literal_starred_in_or_chain(self):
    cpp = self._translate(
      '''
def f(x: int, items: list[int, 0]) -> bool:
  return x in {1, *items, 9}
'''
    )
    self.assertIn("x == 1", cpp)
    self.assertIn("__contains__", cpp)
    self.assertIn("x == 9", cpp)
    self.assertIn("||", cpp)
    self.assertNotIn("PySet<", cpp)
    self.assertNotIn(".add(", cpp)

  def test_list_literal_starred_in_or_chain(self):
    cpp = self._translate(
      '''
def f(x: int, items: list[int, 0]) -> bool:
  return x in [1, *items, 9]
'''
    )
    self.assertIn("x == 1", cpp)
    self.assertIn("__contains__", cpp)
    self.assertIn("x == 9", cpp)
    self.assertIn("||", cpp)
    self.assertNotIn(".append(", cpp)
    self.assertNotIn(".extend(", cpp)

  def test_list_literal_name_in_or(self):
    cpp = self._translate(
      '''
X: int = 1
Y: int = 2

def f(v: int) -> bool:
  return v in [X, Y]
'''
    )
    self.assertIn("v == X", cpp)
    self.assertIn("||", cpp)
    self.assertNotIn(".append(", cpp)

  def test_list_literal_subscript_tbl(self):
    cpp = self._translate(
      '''
def f(i: int) -> int:
  return [10, 20, 30][i]
'''
    )
    self.assertIn("static const", cpp)
    self.assertIn("_tbl[]", cpp)
    self.assertNotIn(".append(", cpp)

  def test_pure_literal_list_subscript_uses_static_table(self):
    cpp = self._translate(
      r'''
def escape(i: int) -> char:
  return [ord("a"), ord("b")][i]
'''
    )
    self.assertIn("static const PyInt _tbl[]", cpp)
    self.assertNotIn(".append(", cpp)

  def test_list_literal_const_index(self):
    cpp = self._translate(
      '''
def f() -> int:
  return [10, 20, 30][1]
'''
    )
    self.assertIn("return 20", cpp)
    self.assertNotIn("_tbl", cpp)

  def test_list_literal_in_or(self):
    cpp = self._translate(
      '''
def f(x: int) -> bool:
  return x in [1, 2, 3]
'''
    )
    self.assertIn("x == 1", cpp)
    self.assertIn("||", cpp)

  def test_str_literal_find_index_inline(self):
    cpp = self._translate(
      '''
def f() -> int:
  return "abc".find("b")
def g() -> int:
  return "abc".index("b")
def h() -> int:
  return "abc".rfind("b")
def i() -> int:
  return "abc".rindex("a")
'''
    )
    self.assertIn("static const PyChar _h[]", cpp)
    self.assertIn("return pos;", cpp)
    self.assertNotIn('PyStr("abc").find', cpp)

  def test_str_literal_find_substr_pychar_init(self):
    cpp = self._translate(
      '''
def f() -> int:
  return "spam and eggs".find("eggs")
'''
    )
    self.assertIn("static const PyChar _s[]", cpp)
    self.assertIn("PyChar(101)", cpp)

  def test_str_literal_find_char_var(self):
    cpp = self._translate(
      '''
def f(c: char) -> int:
  return "abc".find(c)
'''
    )
    self.assertIn("_h[pos] == _c", cpp)

  def test_str_literal_index_not_found_throws(self):
    cpp = self._translate(
      '''
def f() -> int:
  return "abc".index("z")
'''
    )
    self.assertIn("ValueError", cpp)

  def test_str_literal_subscript_and_in(self):
    cpp = self._translate(
      '''
def f(c: int) -> bool:
  return c in "ab"
def g() -> int:
  return "xy"[1]
'''
    )
    self.assertIn("PyChar(", cpp)
    self.assertIn("c == PyChar", cpp)

  def test_subscript_nonconst_key_uses_temp_dict(self):
    cpp = self._translate(
      '''
def h(a: int, k: int) -> int:
  return {a: 10}[k]
'''
    )
    self.assertIn("__setitem__", cpp)
    self.assertIn("__getitem__", cpp)

  def test_pure_literal_dict_get_uses_static_dict(self):
    cpp = self._translate(
      r'''
def escape(c: char) -> str:
  return {
    ord("'"): "\\'",
    ord("\\"): "\\\\",
  }.get(c, "")
'''
    )
    self.assertIn("static PyDict<", cpp)
    self.assertIn(".__setitem__(", cpp)
    self.assertIn(".get(c", cpp)


if __name__ == "__main__":
  unittest.main()
