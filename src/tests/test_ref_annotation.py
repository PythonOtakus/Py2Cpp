"""``T @ref`` → C++ ``T&``。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.analyzer import SignatureBuilder, TypeParser
from src.analysis.ir import iter_matmult_marker_names


class RefAnnotationTypeParseTests(unittest.TestCase):
  def test_param_and_return_ref_suffix(self):
    src = """
def f(x: ECSComponentTable[int] @ref) -> int @ref:
  pass
"""
    tree = ast.parse(src)
    func = tree.body[0]
    tp = TypeParser()
    tparams: set[str] = set()
    param_ann = func.args.args[0].annotation
    self.assertIn("ref", iter_matmult_marker_names(param_ann))
    self.assertTrue(
      tp.parse_type(param_ann, tparams).endswith("&"),
    )
    ret_ann = func.returns
    self.assertTrue(tp.parse_type(ret_ann, tparams).endswith("&"))

  def test_out_name_without_ref_is_const_container(self):
    decl = SignatureBuilder._format_param_decl(
      "PyList<PyInt>",
      "out",
      pass_by_ref=True,
    )
    self.assertEqual(decl, "const PyList<PyInt>& out")

  def test_ref_annotation_makes_mutable_container(self):
    decl = SignatureBuilder._format_param_decl(
      "PyList<PyInt>&",
      "buf",
      pass_by_ref=True,
    )
    self.assertEqual(decl, "PyList<PyInt>& buf")


if __name__ == "__main__":
  unittest.main()
