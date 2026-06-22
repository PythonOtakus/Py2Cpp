"""``template_prefix_stubs`` 与 ``ir.CPP_*_PREFIX`` 一致。"""
from __future__ import annotations

import unittest

from src.analysis.ir import (
  CPP_ARRAY_PREFIX,
  CPP_CHUNK_DEQUE_PREFIX,
  CPP_COUNTER_PREFIX,
  CPP_DEQUE_PREFIX,
  CPP_DICT_PREFIX,
  CPP_LIST_PREFIX,
  CPP_OPTIONAL_PREFIX,
  CPP_REFCount_PREFIX,
  CPP_RESULT_PREFIX,
  CPP_SET_PREFIX,
  CPP_STACK_ARRAY_PREFIX,
  CPP_TUPLE_PREFIX,
)
from src.analysis.stubs.template_prefix_stubs import load_cpp_template_type_prefixes


class TemplatePrefixStubTests(unittest.TestCase):
  def test_native_name_derives_py_prefix(self):
    pfx = load_cpp_template_type_prefixes()
    self.assertEqual(CPP_LIST_PREFIX, pfx["list"])
    self.assertEqual(CPP_LIST_PREFIX, "PyList<")
    self.assertEqual(CPP_DICT_PREFIX, "PyDict<")
    self.assertEqual(CPP_SET_PREFIX, "PySet<")
    self.assertEqual(CPP_DEQUE_PREFIX, "PyDeque<")
    self.assertEqual(CPP_TUPLE_PREFIX, "PyTuple<")
    self.assertEqual(CPP_STACK_ARRAY_PREFIX, "PyStackArray<")
    self.assertEqual(CPP_ARRAY_PREFIX, "PyArray<")

  def test_constant_overrides_non_py_classes(self):
    pfx = load_cpp_template_type_prefixes()
    self.assertEqual(CPP_COUNTER_PREFIX, "Counter<")
    self.assertEqual(CPP_CHUNK_DEQUE_PREFIX, "ChunkDeque<")
    self.assertEqual(pfx["Counter"], "Counter<")

  def test_core_template_prefixes(self):
    pfx = load_cpp_template_type_prefixes()
    self.assertEqual(CPP_REFCount_PREFIX, pfx["RefCount"])
    self.assertEqual(CPP_RESULT_PREFIX, pfx["IterResult"])
    self.assertEqual(CPP_OPTIONAL_PREFIX, pfx["Optional"])


if __name__ == "__main__":
  unittest.main()
