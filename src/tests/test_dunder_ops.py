"""``constant/dunder_ops`` 表完整性。"""
from __future__ import annotations

import unittest

from src.constant.dunder_ops import (
  BINARY_DUNDER_TO_CPP_OP,
  BINARY_DUNDER_TO_INPLACE,
  BINARY_DUNDER_TO_REVERSE,
  COMPARE_DUNDERS,
  SKIP_OPERATOR_DUNDERS,
  UNARY_DUNDER_TO_CPP_OP,
)


class TestDunderOps(unittest.TestCase):
  def test_reverse_pairs_cover_arithmetic_ops(self):
    skip = SKIP_OPERATOR_DUNDERS | COMPARE_DUNDERS
    for fwd in BINARY_DUNDER_TO_CPP_OP:
      if fwd in skip:
        continue
      self.assertIn(fwd, BINARY_DUNDER_TO_REVERSE)

  def test_inplace_pairs_cover_arithmetic_ops(self):
    skip = SKIP_OPERATOR_DUNDERS | COMPARE_DUNDERS
    for fwd in BINARY_DUNDER_TO_CPP_OP:
      if fwd in skip:
        continue
      self.assertIn(fwd, BINARY_DUNDER_TO_INPLACE)

  def test_compare_dunders_subset(self):
    self.assertLessEqual(COMPARE_DUNDERS, frozenset(BINARY_DUNDER_TO_CPP_OP))

  def test_unary_ops_non_empty(self):
    self.assertTrue(UNARY_DUNDER_TO_CPP_OP)


if __name__ == "__main__":
  unittest.main()
