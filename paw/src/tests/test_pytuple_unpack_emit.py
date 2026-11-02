"""``PyTuple`` 解包：``*_`` / 负 ``get`` / S1202。"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from src.emit.pytuple_unpack_emit import pytuple_unpack_slots
from src.translation_error import TranslationError
from src.translator import Translator


def _name(id: str) -> ast.Name:
  return ast.Name(id=id, ctx=ast.Store())


def _star_name(id: str) -> ast.Starred:
  return ast.Starred(value=_name(id), ctx=ast.Store())


class PyTupleUnpackEmitTests(unittest.TestCase):
  def test_prefix_star_discard_uses_nonneg_only(self):
    elts = [_name("d"), _star_name("_")]
    slots = pytuple_unpack_slots(elts, arity=3)
    self.assertEqual([(s.get_index, s.target.id) for s in slots], [(0, "d")])

  def test_star_discard_suffix_uses_negative_index(self):
    elts = [_star_name("_"), _name("t")]
    slots = pytuple_unpack_slots(elts, arity=3)
    self.assertEqual([(s.get_index, s.target.id) for s in slots], [(-1, "t")])

  def _translate_cpp(self, body: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out / "generated"), include_stdlib=True,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_emit_star_discard_unpack(self):
    cpp = self._translate_cpp(
      """
def parts() -> (str, str, list[str]):
  out: list[str] = []
  return "", "", out

def drive() -> str:
  d: str
  d, *_ = parts()
  return d
"""
    )
    self.assertIn("template get<0>()", cpp)
    self.assertNotRegex(cpp, r"template get<1>\(\)")
    self.assertNotRegex(cpp, r"template get<2>\(\)")

  def test_emit_star_prefix_negative_tail(self):
    cpp = self._translate_cpp(
      """
def triple() -> (str, str, str):
  return "a", "b", "c"

def tail() -> str:
  rest: str
  *_, rest = triple()
  return rest
"""
    )
    self.assertIn("template get<-1>()", cpp)

  def test_star_rest_slice_slots(self):
    elts = [_name("a"), _star_name("mid"), _name("c")]
    slots = pytuple_unpack_slots(elts, arity=4)
    self.assertEqual(len(slots), 3)
    self.assertEqual(slots[0].get_index, 0)
    self.assertEqual(slots[0].target.id, "a")
    self.assertEqual(slots[1].slice_start, 1)
    self.assertEqual(slots[1].slice_stop, 3)
    self.assertEqual(slots[1].target.id, "mid")
    self.assertEqual(slots[2].get_index, -1)
    self.assertEqual(slots[2].target.id, "c")

  def test_emit_star_rest_binding(self):
    cpp = self._translate_cpp(
      """
def quad() -> (str, str, str, str):
  return "a", "b", "c", "d"

def mid() -> (str, str):
  b: PyTuple[str, str]
  _, *b, _ = quad()
  return b
"""
    )
    self.assertIn("template get_slice<1, 3>()", cpp)
    self.assertNotRegex(cpp, r"template get<0>\(\)")
    self.assertNotRegex(cpp, r"template get<-1>\(\)")
    self.assertIn("PyTuple<", cpp)

  def test_emit_empty_star_rest(self):
    cpp = self._translate_cpp(
      """
def pair() -> (str, str):
  return "x", "y"

def empty_mid() -> PyTuple[()]:
  b: PyTuple[()]
  _, *b, _ = pair()
  return b
"""
    )
    self.assertIn("template get_slice<1, 1>()", cpp)
    self.assertIn("PyTuple<>", cpp)


class TupleUnpackStrictS36Tests(unittest.TestCase):
  def _expect_s1202(self, body: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py), output_dir=str(out / "generated"), include_stdlib=True, strict=True,
        )
      self.assertIn("[S1202]", str(ctx.exception))

  def test_s1202_unused_unpack_binding(self):
    self._expect_s1202(
      """
def bad() -> int:
  a: int
  b: int
  a, b = (1, 2)
  _ = b
  return a
"""
    )

  def test_s1202_allows_underscore_slot(self):
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(
        "from py2cpp import *\n\n"
        "def ok() -> int:\n"
        "  a: int\n"
        "  a, _ = (1, 2)\n"
        "  return a\n",
        encoding="utf-8",
      )
      Translator.translate_file(
        str(py), output_dir=str(out / "generated"), include_stdlib=True, strict=True,
      )


if __name__ == "__main__":
  unittest.main()
