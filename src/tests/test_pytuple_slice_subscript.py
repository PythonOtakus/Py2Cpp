"""``PyTuple`` 定长切片 ``s[i:j]`` → ``get_slice``（含负索引）。"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from src.analysis.ir import parse_pytuple_slice_template_bounds
from src.translator import Translator


class ParsePyTupleSliceBoundsTests(unittest.TestCase):
  def test_negative_stop(self):
    sl = ast.Slice(
      lower=ast.Constant(value=1),
      upper=ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=1)),
      step=None,
    )
    self.assertEqual(parse_pytuple_slice_template_bounds(sl, arity=3), (1, -1))

  def test_omit_bounds(self):
    sl = ast.Slice(lower=None, upper=None, step=None)
    self.assertEqual(parse_pytuple_slice_template_bounds(sl, arity=3), (0, 3))


class PyTupleSliceEmitTests(unittest.TestCase):
  def _translate_cpp(self, body: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out / "generated"), include_stdlib=True,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_emit_tuple_subscript_negative_stop(self):
    cpp = self._translate_cpp(
      """
def triple() -> (int, int, int):
  return 1, 2, 3

def middle() -> (int,):
  t: (int, int, int)
  t = triple()
  return t[1:-1]
"""
    )
    self.assertIn("template get_slice<1, -1>()", cpp)

  def test_emit_tuple_subscript_prefix(self):
    cpp = self._translate_cpp(
      """
def pair() -> (int, int):
  return 1, 2

def tail() -> (int,):
  t: (int, int)
  t = pair()
  return t[1:]
"""
    )
    self.assertIn("template get_slice<1, 2>()", cpp)


if __name__ == "__main__":
  unittest.main()
