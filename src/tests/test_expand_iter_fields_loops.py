"""``expand_iter_fields_loops``：混入形参 ``Vec.iter_fields`` 译期展开。"""
from __future__ import annotations

import ast
import textwrap
import unittest

from src.analysis.ir import ClassInfo
from src.passes.inline_range import expand_inline_range
from src.passes.match_case import expand_iter_fields_loops
from src.passes.varstack import expand_varstack


class ExpandIterFieldsLoopsTests(unittest.TestCase):
  def _host(self, src: str) -> ClassInfo:
    return ClassInfo(ast.parse(textwrap.dedent(src)).body[0])

  def _method(self, src: str) -> ast.FunctionDef:
    mod = ast.parse(textwrap.dedent(src))
    return mod.body[0].body[0]

  def test_vec_iter_fields_unrolls(self) -> None:
    method = self._method(
      '''
      class MatrixMixin:
        @immutable
        def apply_to_vector(self, other):
          vs: VarStack = new()
          for i in inlineRange(Self._dim - 1):
            s: float64 = 0.0
            j: int = 0
            for f in Vec.iter_fields(public_only=True):
              s += self[i, j] * getattr(other, f)
              j += 1
            vs.push(s)
          return new(*vs)
      '''
    )
    matrix_host = self._host(
      '''
      class Matrix3:
        _dim: int @const = 3
      '''
    )
    vec_host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    expanded = expand_iter_fields_loops(
      method,
      matrix_host,
      type_hosts={"Vec": vec_host},
    )
    self.assertIsNotNone(expanded)
    assert expanded is not None
    expanded = expand_inline_range(expanded, matrix_host)
    expanded = expand_varstack(expanded, matrix_host)
    dump = ast.unparse(expanded)
    self.assertIn("other.x", dump)
    self.assertIn("other.y", dump)
    self.assertNotIn("iter_fields", dump)
    self.assertNotIn("getattr", dump)

  def test_vec_enum_fields_unrolls_index_and_name(self) -> None:
    method = self._method(
      '''
      class MatrixMixin:
        def set_axis(self, i, axis):
          for j, f in Vec.enum_fields(public_only=True):
            self[j, i] = getattr(axis, f)
      '''
    )
    matrix_host = self._host(
      '''
      class Matrix3:
        _dim: int @const = 3
      '''
    )
    vec_host = self._host(
      '''
      class Vector2:
        x: float64 = 0.0
        y: float64 = 0.0
      '''
    )
    expanded = expand_iter_fields_loops(
      method,
      matrix_host,
      type_hosts={"Vec": vec_host},
    )
    self.assertIsNotNone(expanded)
    assert expanded is not None
    dump = ast.unparse(expanded)
    self.assertIn("axis.x", dump)
    self.assertIn("axis.y", dump)
    self.assertNotIn("enum_fields", dump)
    self.assertNotIn("getattr", dump)


if __name__ == "__main__":
  unittest.main()
