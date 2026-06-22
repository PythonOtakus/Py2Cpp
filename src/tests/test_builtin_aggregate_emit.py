"""``builtin_aggregate_emit`` 片段回归。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class BuiltinAggregateEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_min_multi_arg_iife(self):
    cpp = self._translate("def f() -> int:\n  return min(3, 1, 2)\n")
    self.assertIn("[&]()", cpp)
    self.assertIn(" < ", cpp)
    self.assertNotIn("? -1 :", cpp)

  def test_min_key_lambda(self):
    cpp = self._translate(
      "def f(xs: list[int]) -> int:\n  return min(xs, key=lambda x: -x)\n",
    )
    self.assertIn("[&](", cpp)
    self.assertIn("return(-x)", cpp.replace(" ", ""))
    self.assertRegex(cpp.replace(" ", ""), r"\(x6\)<\[&\]|return\(-x\);\}\(x6\)<")
    self.assertNotIn("? -1 :", cpp)

  def test_max_key_scalar_direct_gt(self):
    src = (
      "def _neg(v: int) -> int:\n"
      "  return -v\n"
      "def f(xs: list[int]) -> int:\n"
      "  return max(xs, key=_neg)\n"
    )
    cpp = self._translate(src)
    self.assertIn("_neg(", cpp)
    self.assertIn(">_neg(", cpp.replace(" ", ""))
    self.assertNotIn("? -1 :", cpp)

  def test_sum_range_native_for(self):
    cpp = self._translate("def f() -> int:\n  return sum(range(3))\n")
    self.assertIn("for (int", cpp)


if __name__ == "__main__":
  unittest.main()
