"""``uint64`` / ``uint`` 整型字面量 C++ 后缀。"""
import unittest

from src.analysis.ir import format_cpp_uint, format_cpp_uint64


class TestUIntLiteralFormat(unittest.TestCase):
  def test_uint64_large_hex(self):
    self.assertEqual(format_cpp_uint64(0x8080808080808080), "0x8080808080808080ULL")

  def test_uint64_zero(self):
    self.assertEqual(format_cpp_uint64(0), "0ULL")

  def test_uint_large(self):
    self.assertEqual(format_cpp_uint(0xFFFFFFFF), "4294967295U")


if __name__ == "__main__":
  unittest.main()
