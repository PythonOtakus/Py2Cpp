"""``T @lazy`` 注解解析。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.analyzer import SignatureBuilder, TypeParser
from src.analysis.lazy_param import (
  is_lazy_type_annotation,
  lazy_param_has_ref,
  lazy_supplier_cpp_type,
  strip_lazy_type_annotation,
)


class LazyParamAnnotationTests(unittest.TestCase):
  def _ann(self, src: str) -> ast.expr:
    func = ast.parse(f"def f({src}): pass").body[0]
    return func.args.args[0].annotation

  def test_lazy_marker(self):
    ann = self._ann("x: int @lazy")
    self.assertTrue(is_lazy_type_annotation(ann))
    inner = strip_lazy_type_annotation(ann)
    self.assertIsInstance(inner, ast.Name)
    self.assertEqual(inner.id, "int")

  def test_ref_lazy_order(self):
    ann = self._ann("x: int @ref @lazy")
    self.assertTrue(is_lazy_type_annotation(ann))
    self.assertTrue(lazy_param_has_ref(ann))

  def test_supplier_cpp_type(self):
    self.assertEqual(lazy_supplier_cpp_type("PyInt"), "PyCallable<PyInt>")
    self.assertEqual(lazy_supplier_cpp_type("PyInt&"), "PyCallable<PyInt>")

  def test_param_cpp_type_lazy(self):
    from src.analysis.ir import FuncTypeParams

    src = """
def f(default: int @lazy = None) -> int:
  return default
"""
    func = ast.parse(src).body[0]
    arg = func.args.args[0]
    tp = TypeParser()
    sb = SignatureBuilder(tp)
    func_ft = FuncTypeParams.collect(func)
    cpp = sb._param_cpp_type(arg, class_type_params=[], func_ft=func_ft)
    self.assertEqual(cpp, "PyCallable<PyInt>")


if __name__ == "__main__":
  unittest.main()
