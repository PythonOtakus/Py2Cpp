"""PEP 696：声明处 ``typename C = PyInt``；``Counter[str]`` → ``Counter<PyStr>``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class TypeParamDefaultTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_counter_omit_count_type_param(self):
    cpp = self._translate(
      '''
from py2cpp import *

def f() -> None:
  c: Counter[str] = new()
  c["a"] = 1
'''
    )
    self.assertIn("Counter<PyStr>", cpp)
    self.assertNotIn("Counter<PyStr, PyInt>", cpp)

  def test_counter_explicit_count_type_unchanged(self):
    cpp = self._translate(
      '''
from py2cpp import *

def g() -> None:
  c: Counter[str, int] = new()
'''
    )
    self.assertIn("Counter<PyStr, PyInt>", cpp)

  def test_counter_class_decl_template_default(self):
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      Translator.translate_file(
        str(root / "py2cpp" / "__init__.py"),
        output_dir=str(out),
        include_stdlib=True,
        emit_main=False,
      )
      header = out / "runtime" / "py2cpp" / "util" / "misc.h"
      text = header.read_text(encoding="utf-8")
    self.assertRegex(
      text,
      r"template\s*<\s*typename K\s*,\s*typename C\s*=\s*PyInt\s*>\s*\n\s*class Counter",
    )

  def test_float64_binop_infers_generic_type_argument(self):
    cpp = self._translate(
      '''
from py2cpp import *
from py2cpp.math import safeSqrt

def magnitude(x: float64, y: float64) -> float64:
  return safeSqrt(x * x + y * y)
'''
    )
    self.assertIn("safeSqrt<PyFloat64>", cpp)


if __name__ == "__main__":
  unittest.main()
