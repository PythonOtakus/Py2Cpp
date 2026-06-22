"""``range`` 原生 for 条件：运行期 step 符号不进入每轮循环条件。"""
import unittest

from src.emit.loops_emit import (
  cpp_native_for_range_header,
  cpp_range_loop_cond,
  range_step_is_negative,
)


class RangeLoopEmitTests(unittest.TestCase):
  def test_const_positive_step(self):
    self.assertIs(range_step_is_negative("1"), False)
    self.assertEqual(cpp_range_loop_cond("i", "n", "1"), "i < n")
    self.assertEqual(
      cpp_native_for_range_header("i", "0", "n", "1"),
      "for (int i = 0; i < n; i += 1)",
    )

  def test_const_negative_step(self):
    self.assertIs(range_step_is_negative("-2"), True)
    self.assertEqual(cpp_range_loop_cond("i", "0", "-2"), "i > 0")
    self.assertEqual(
      cpp_native_for_range_header("i", "10", "0", "-2"),
      "for (int i = 10; i > 0; i += -2)",
    )

  def test_runtime_step_splits_for(self):
    self.assertIsNone(range_step_is_negative("step"))
    hdr = cpp_native_for_range_header("i", "a", "b", "step")
    self.assertIn("if ((step) < 0)", hdr)
    self.assertIn("i > b", hdr)
    self.assertIn("i < b", hdr)
    self.assertNotIn("step) < 0 ?", hdr)

  def test_runtime_cond_uses_hoisted_flag(self):
    cond = cpp_range_loop_cond("i", "b", "step", neg_step_flag="neg")
    self.assertEqual(cond, "(neg ? i > b : i < b)")
    self.assertNotIn("step", cond)


if __name__ == "__main__":
  unittest.main()
