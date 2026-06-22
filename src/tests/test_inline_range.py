"""``expand_inline_range``：``@mixin`` 内 ``inline_range`` 完全展开（无 ``for`` / ``range``）。"""
from __future__ import annotations

import ast
import textwrap
import unittest

from src.analysis.ir import ClassInfo
from src.passes.inline_range import expand_inline_range


class ExpandInlineRangeTests(unittest.TestCase):
  def _host(self, src: str) -> ClassInfo:
    return ClassInfo(ast.parse(textwrap.dedent(src)).body[0])

  def _method(self, src: str) -> ast.FunctionDef:
    mod = ast.parse(textwrap.dedent(src))
    return mod.body[0].body[0]

  def _assert_no_for_range(self, expanded: ast.FunctionDef) -> None:
    dump = ast.dump(expanded, include_attributes=False)
    self.assertNotIn("inline_range", dump)
    self.assertNotIn("range", dump)
    self.assertNotIn("For(", dump)

  def test_dim_unroll(self):
    method = self._method(
      '''
      class M:
        def fill_diag(self):
          for i in inline_range(Self._dim):
            self[i, i] = 1.0
      '''
    )
    host = self._host(
      '''
      class Matrix3:
        _dim: int @const = 3
      '''
    )
    expanded = expand_inline_range(method, host)
    self._assert_no_for_range(expanded)
    dump = ast.dump(expanded, include_attributes=False)
    self.assertIn("Constant(value=0", dump)
    self.assertIn("Constant(value=1", dump)
    self.assertIn("Constant(value=2", dump)

  def test_dim_minus_one(self):
    method = self._method(
      '''
      class M:
        def row(self):
          for j in inline_range(Self._dim - 1):
            pass
      '''
    )
    host = self._host(
      '''
      class Matrix4:
        _dim: int @const = 4
      '''
    )
    expanded = expand_inline_range(method, host)
    self._assert_no_for_range(expanded)

  def test_var_start_plus_one(self):
    method = self._method(
      '''
      class M:
        def elim(self):
          for k in inline_range(Self._dim):
            for r in inline_range(k + 1, Self._dim):
              pass
      '''
    )
    host = self._host(
      '''
      class Matrix3:
        _dim: int @const = 3
      '''
    )
    expanded = expand_inline_range(method, host)
    self._assert_no_for_range(expanded)

  def test_nested_loop_vars_in_stop(self):
    method = self._method(
      '''
      class M:
        def nest(self):
          for i in inline_range(Self._dim):
            for j in inline_range(i + 1, Self._dim):
              for k in inline_range(j + 1, i + j + Self._dim):
                pass
      '''
    )
    host = self._host(
      '''
      class Matrix3:
        _dim: int @const = 3
      '''
    )
    expanded = expand_inline_range(method, host)
    self._assert_no_for_range(expanded)

  def test_rejects_runtime_bound(self):
    method = self._method(
      '''
      class M:
        def bad(self, n: int):
          for i in inline_range(n):
            pass
      '''
    )
    host = self._host(
      '''
      class Matrix3:
        _dim: int @const = 3
      '''
    )
    with self.assertRaises(NotImplementedError):
      expand_inline_range(method, host)

  def test_rejects_continue(self):
    method = self._method(
      '''
      class M:
        def bad(self):
          for i in inline_range(Self._dim):
            if i == 0:
              continue
            pass
      '''
    )
    host = self._host(
      '''
      class Matrix3:
        _dim: int @const = 3
      '''
    )
    with self.assertRaises(NotImplementedError):
      expand_inline_range(method, host)

  def test_const_if_r_ne_k_inlined(self):
    method = self._method(
      '''
      class M:
        def elim(self):
          for k in inline_range(Self._dim):
            for r in inline_range(Self._dim):
              if r != k:
                self[r, k] = 0.0
      '''
    )
    host = self._host(
      '''
      class Matrix3:
        _dim: int @const = 3
      '''
    )
    expanded = expand_inline_range(method, host)
    self._assert_no_for_range(expanded)
    dump = ast.dump(expanded, include_attributes=False)
    self.assertNotIn("If(", dump)
    self.assertNotIn("Compare(", dump)
    assign_count = dump.count("Assign(")
    # k=0: r=1,2 → 2; k=1: r=0,2 → 2; k=2: r=0,1 → 2
    self.assertEqual(assign_count, 6)


if __name__ == "__main__":
  unittest.main()
