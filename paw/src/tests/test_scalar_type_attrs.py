"""标量类型静态属性 / 静态方法映射。"""
from __future__ import annotations

import unittest

from src.analysis.ir import (
  format_cpp_int,
  scalar_type_static_attr_cpp,
  scalar_type_static_attr_from_expr,
  scalar_type_static_method_cpp,
)
import ast


class ScalarTypeStaticAttrTests(unittest.TestCase):
  def test_float_inf_nan(self):
    self.assertEqual(scalar_type_static_attr_cpp("float", "Inf"), "PY2CPP_FLOAT_INF")
    self.assertEqual(scalar_type_static_attr_cpp("float", "NaN"), "PY2CPP_FLOAT_NAN")
    self.assertEqual(scalar_type_static_attr_cpp("float64", "Inf"), "PY2CPP_FLOAT64_INF")
    self.assertEqual(scalar_type_static_attr_cpp("float64", "NaN"), "PY2CPP_FLOAT64_NAN")

  def test_int_min_max(self):
    self.assertEqual(scalar_type_static_attr_cpp("int", "Min"), "PY2CPP_INT_MIN")
    self.assertEqual(scalar_type_static_attr_cpp("int", "Max"), "PY2CPP_INT_MAX")
    self.assertEqual(scalar_type_static_attr_cpp("int16", "Min"), "PY2CPP_INT16_MIN")
    self.assertEqual(scalar_type_static_attr_cpp("int16", "Max"), "PY2CPP_INT16_MAX")
    self.assertEqual(scalar_type_static_attr_cpp("int64", "Min"), "PY2CPP_INT64_MIN")
    self.assertEqual(scalar_type_static_attr_cpp("int64", "Max"), "PY2CPP_INT64_MAX")

  def test_uint_min_max(self):
    self.assertEqual(scalar_type_static_attr_cpp("uint", "Min"), "PY2CPP_UINT_MIN")
    self.assertEqual(scalar_type_static_attr_cpp("uint", "Max"), "PY2CPP_UINT_MAX")
    self.assertEqual(scalar_type_static_attr_cpp("uint16", "Min"), "PY2CPP_UINT16_MIN")
    self.assertEqual(scalar_type_static_attr_cpp("uint16", "Max"), "PY2CPP_UINT16_MAX")
    self.assertEqual(scalar_type_static_attr_cpp("uint64", "Min"), "PY2CPP_UINT64_MIN")
    self.assertEqual(scalar_type_static_attr_cpp("uint64", "Max"), "PY2CPP_UINT64_MAX")

  def test_float_min_max(self):
    self.assertEqual(scalar_type_static_attr_cpp("float", "Min"), "PY2CPP_FLOAT_MIN")
    self.assertEqual(scalar_type_static_attr_cpp("float", "Max"), "PY2CPP_FLOAT_MAX")
    self.assertEqual(scalar_type_static_attr_cpp("float64", "Min"), "PY2CPP_FLOAT64_MIN")
    self.assertEqual(scalar_type_static_attr_cpp("float64", "Max"), "PY2CPP_FLOAT64_MAX")

  def test_no_legacy_inf_nan(self):
    self.assertIsNone(scalar_type_static_attr_cpp("int", "Inf"))
    self.assertIsNone(scalar_type_static_attr_cpp("float", "inf"))

  def test_int_min_from_expr(self):
    node = ast.parse("int.Min", mode="eval").body
    self.assertEqual(scalar_type_static_attr_from_expr(node), "PY2CPP_INT_MIN")

  def test_legacy_min_value_not_mapped(self):
    self.assertIsNone(scalar_type_static_attr_cpp("int", "MinValue"))

  def test_format_cpp_int_min(self):
    self.assertEqual(format_cpp_int(-(1 << 31)), "PY2CPP_INT_MIN")


class ScalarTypeStaticMethodTests(unittest.TestCase):
  def test_float64_is_inf(self):
    self.assertEqual(
      scalar_type_static_method_cpp("float64", "isInf", "x"),
      "PY2CPP_ISINF_F64(x)",
    )

  def test_float_is_nan(self):
    self.assertEqual(
      scalar_type_static_method_cpp("float", "isNaN", "v"),
      "PY2CPP_ISNAN_F(v)",
    )

  def test_legacy_isinf_not_mapped(self):
    self.assertIsNone(scalar_type_static_method_cpp("float64", "isinf", "x"))

  def test_int_has_no_is_inf(self):
    self.assertIsNone(scalar_type_static_method_cpp("int", "isInf", "x"))


if __name__ == "__main__":
  unittest.main()
