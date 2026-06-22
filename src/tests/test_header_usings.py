"""``header_usings``：由 ``ClassInfo`` 推导 ``using``，无 ``TestCase`` 硬编码表。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.header_usings import build_header_usings_index, usings_for_headers
from src.analysis.ir import ClassInfo
from src.constant.stdlib_layout import RUNTIME_PKG, stdlib_header_include


def _info(
  name: str,
  module_path: str,
  *,
  cpp_rename: str | None = None,
) -> ClassInfo:
  decs = []
  if cpp_rename:
    decs = [
      ast.Call(
        func=ast.Name(id="native_name", ctx=ast.Load()),
        args=[ast.Constant(cpp_rename)],
      )
    ]
  node = ast.ClassDef(
    name=name,
    bases=[],
    keywords=[],
    decorator_list=decs,
    body=[ast.Pass()],
    lineno=1,
  )
  ci = ClassInfo(node, module_path=module_path)
  if cpp_rename:
    ci.cpp_rename = cpp_rename
  return ci


class HeaderUsingsTests(unittest.TestCase):
  def test_list_header_from_native_name_classes(self):
    classes = {
      "list": _info("list", "py2cpp/util/list", cpp_rename="PyList"),
      "list_iterator": _info(
        "list_iterator", "py2cpp/util/list", cpp_rename="PyListIterator"
      ),
      "TestCase": _info("TestCase", "py2cpp/test/unittest"),
    }
    index = build_header_usings_index(classes)
    list_h = stdlib_header_include("util/list")
    syms = {sym for _ns, sym in index[list_h]}
    self.assertIn("PyList", syms)
    self.assertIn("PyListIterator", syms)
    unittest_h = stdlib_header_include("test/unittest")
    self.assertIn("TestCase", {sym for _ns, sym in index[unittest_h]})

  def test_util_range_header(self):
    from src.constant.stdlib_layout import stdlib_header_include

    classes = {
      "range": _info("range", "py2cpp/util/range", cpp_rename="PyRange"),
    }
    index = build_header_usings_index(classes)
    range_h = stdlib_header_include("util/range")
    pairs = index[range_h]
    self.assertEqual(pairs, [("py2cpp::util::range", "PyRange")])

  def test_global_namespace_module_omitted(self):
    classes = {
      "stack_array": _info(
        "stack_array", "py2cpp/util/stack_array", cpp_rename="PyStackArray"
      ),
    }
    index = build_header_usings_index(classes)
    self.assertEqual(index.get(stdlib_header_include("util/stack_array"), []), [])

  def test_usings_for_headers_dedupes(self):
    index = {
      "a.h": [("ns", "Foo")],
      "b.h": [("ns", "Foo"), ("ns", "Bar")],
    }
    out = usings_for_headers(["a.h", "b.h", "a.h"], index)
    self.assertEqual(out, [("ns", "Foo"), ("ns", "Bar")])


if __name__ == "__main__":
  unittest.main()
