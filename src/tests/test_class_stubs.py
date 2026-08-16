"""标准库 ``@native_name`` AST 扫描与 ``cpp_ident`` 联动。"""
from __future__ import annotations

import unittest

from src.analysis.stubs.class_stubs import (
  load_host_bound_iterator_view_cpp_bases,
  load_native_cpp_base_headers,
  load_stdlib_native_names,
)
from src.analysis.ir import CPP_RENAME, cpp_ident, cpp_type_rename

# 仍由 ``CPP_RENAME`` 静态维护（内置标量）
_CPP_RENAME_ONLY = frozenset({
  "int", "int64", "uint", "uint64", "uintptr", "float", "float64", "bool", "char", "byte",
})

_CODEGEN_NATIVE_SAMPLES = {
  "SetReverseIterator": "PySetReverseIterator",
  "TupleIterator": "PyTupleIterator",
  "StackArrayIterator": "PyStackArrayIterator",
}

# 抽样：原 ``CPP_RENAME`` 大表项，现由标准库类装饰器提供
_SAMPLE_NATIVE_NAMES = {
  "list": "PyList",
  "dict": "PyDict",
  "str": "PyStr",
  "range": "PyRange",
  "Optional": "PyOptional",
  "datetime": "PyDateTime",
}


class ClassStubRegistryTests(unittest.TestCase):
  def test_cpp_rename_only_entries(self):
    for name in _CPP_RENAME_ONLY:
      self.assertIn(name, CPP_RENAME)
      self.assertIsNone(load_stdlib_native_names().get(name))

  def test_codegen_iterator_native_names(self):
    renames = load_stdlib_native_names()
    for py, cpp in _CODEGEN_NATIVE_SAMPLES.items():
      self.assertEqual(renames.get(py), cpp, msg=py)
      self.assertEqual(cpp_ident(py), cpp)
      self.assertNotIn(py, CPP_RENAME)

  def test_native_cpp_base_headers_for_iterators(self):
    headers = load_native_cpp_base_headers()
    from src.constant.stdlib_layout import stdlib_header_include

    self.assertEqual(headers["PyTupleIterator"], stdlib_header_include("util/tuple"))
    self.assertEqual(headers["PyStackArrayIterator"], stdlib_header_include("util/stack_array"))
    self.assertEqual(headers["PySetReverseIterator"], stdlib_header_include("util/set"))

  def test_native_name_samples(self):
    renames = load_stdlib_native_names()
    for py, cpp in _SAMPLE_NATIVE_NAMES.items():
      self.assertEqual(renames.get(py), cpp, msg=py)
      self.assertEqual(cpp_ident(py), cpp)
      self.assertEqual(cpp_type_rename(py), cpp)

  def test_cpp_ident_prefers_native_name(self):
    self.assertEqual(cpp_ident("list"), "PyList")
    self.assertEqual(cpp_ident("int"), "PyInt")

  def test_host_bound_iterator_view_cpp_bases(self):
    bases = load_host_bound_iterator_view_cpp_bases()
    self.assertIn(cpp_ident("ListIterator"), bases)
    self.assertIn(cpp_ident("DictKeysView"), bases)
    self.assertIn("ECSComponentTableIterator", bases)
    self.assertNotIn(cpp_ident("StrIterator"), bases)
    self.assertNotIn(cpp_ident("TupleIterator"), bases)


if __name__ == "__main__":
  unittest.main()
