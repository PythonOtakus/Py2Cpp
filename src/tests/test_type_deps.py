"""``type_deps``：按 ``ClassInfo`` / primitive 推导 include，无 ``TestCase`` 硬编码。"""
from __future__ import annotations

import unittest

from src.analysis.ir import ClassInfo
from src.analysis.type_deps import (
  PRIMITIVE_HEADER_MAP,
  collect_type_header_deps,
  header_for_module,
)
from src.constant.stdlib_layout import RUNTIME_PKG, stdlib_header_include


def _info(name: str, module_path: str, *, cpp_rename: str | None = None) -> ClassInfo:
  import ast

  decs = []
  if cpp_rename:
    decs = [ast.Call(func=ast.Name(id="native_name", ctx=ast.Load()), args=[ast.Constant(cpp_rename)])]
  node = ast.ClassDef(name=name, bases=[], keywords=[], decorator_list=decs, body=[ast.Pass()], lineno=1)
  ci = ClassInfo(node, module_path=module_path)
  if cpp_rename:
    ci.cpp_rename = cpp_rename
  return ci


class TypeDepsTests(unittest.TestCase):
  def test_primitive_int(self):
    h = collect_type_header_deps("PyInt", "py2cpp/util/list.h", {})
    self.assertEqual(h, [PRIMITIVE_HEADER_MAP["PyInt"]])

  def test_list_template_via_class_info(self):
    classes = {
      "list": _info("list", "py2cpp/util/list", cpp_rename="PyList"),
      "str": _info("str", "py2cpp/text/str", cpp_rename="PyStr"),
    }
    own = "py2cpp/util/dict.h"
    deps = collect_type_header_deps("PyDict<PyStr, PyList<PyInt>>", own, classes)
    self.assertIn(stdlib_header_include("util/list"), deps)
    self.assertIn(stdlib_header_include("text/str"), deps)
    self.assertIn(PRIMITIVE_HEADER_MAP["PyInt"], deps)
    self.assertNotIn(own.replace(".h", ""), deps)

  def test_testcase_not_in_primitive_map(self):
    self.assertNotIn("TestCase", PRIMITIVE_HEADER_MAP)

  def test_testcase_via_class_info(self):
    classes = {"TestCase": _info("TestCase", "py2cpp/test/unittest")}
    deps = collect_type_header_deps("TestCase", "py2cpp/foo.h", classes)
    self.assertEqual(deps, [header_for_module("py2cpp/test/unittest")])

  def test_str_without_import_binding(self):
    """``list.py`` 式：签名含 ``str`` 但无 import，靠 ``ClassInfo`` 定位 ``text/str.h``。"""
    classes = {"str": _info("str", "py2cpp/text/str", cpp_rename="PyStr")}
    deps = collect_type_header_deps("PyStr", "py2cpp/util/list.h", classes)
    self.assertEqual(deps, [stdlib_header_include("text/str")])

  def test_str_callable_uses_forward_declaration(self):
    deps = collect_type_header_deps(
      "PyCallable<PyUInt, utf8ptr, PyUInt>",
      stdlib_header_include("text/str"),
      {},
    )
    self.assertNotIn(stdlib_header_include("core/delegate"), deps)
  def test_own_header_excluded(self):
    classes = {"list": _info("list", "py2cpp/util/list", cpp_rename="PyList")}
    own = header_for_module("py2cpp/util/list")
    deps = collect_type_header_deps("PyList<PyInt>", own, classes)
    self.assertEqual(deps, [PRIMITIVE_HEADER_MAP["PyInt"]])

  def test_util_range_class(self):
    classes = {"range": _info("range", "py2cpp/util/range", cpp_rename="PyRange")}
    deps = collect_type_header_deps("PyRange", "py2cpp/io.h", classes)
    self.assertEqual(deps, [stdlib_header_include("util/range")])

  def test_py_stack_array_template_base(self):
    own = stdlib_header_include("util/pool")
    deps = collect_type_header_deps("PyStackArray<PyInt, 32, 0>", own, {})
    self.assertIn(stdlib_header_include("util/stack_array"), deps)

  def test_pychar_ptr_prefers_char_header(self):
    """``PyChar*`` 须 ``char.h``，勿因包根 ``class char`` 误拉 ``py2cpp.h``。"""
    classes = {"char": _info("char", RUNTIME_PKG, cpp_rename="PyChar")}
    deps = collect_type_header_deps("PyChar*", "py2cpp/util/arena.h", classes)
    self.assertEqual(deps, [PRIMITIVE_HEADER_MAP["PyChar"]])
    self.assertNotIn(header_for_module(RUNTIME_PKG), deps)


if __name__ == "__main__":
  unittest.main()
