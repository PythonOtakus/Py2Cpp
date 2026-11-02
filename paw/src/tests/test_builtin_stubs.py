"""``builtin_stubs`` / ``class_stubs``：翻译期桩与 ``@global_call`` 扫描。"""
from __future__ import annotations

import unittest

from src.analysis.ir import resolve_decorator_string_pattern

from src.analysis.stubs.builtin_stubs import (
  load_builtins_cpp_runtime_funcs,
  load_translation_only_funcs,
)
from src.analysis.stubs.class_stubs import load_stdlib_exception_types
from src.analysis.stubs.class_stubs import lookup_module_function_cpp_name
from src.constant.stdlib_layout import RUNTIME_BUILTINS_MODULE, RUNTIME_PKG, stdlib_module_path


class BuiltinStubTests(unittest.TestCase):
  def test_decorator_string_wildcard(self):
    self.assertEqual(resolve_decorator_string_pattern("fs_*", "getcwd"), "fs_getcwd")
    self.assertEqual(resolve_decorator_string_pattern("fs_*", "getCwd"), "fs_getCwd")
    self.assertEqual(resolve_decorator_string_pattern("Py*", "Foo"), "PyFoo")
    self.assertEqual(resolve_decorator_string_pattern("PyFoo", "Foo"), "PyFoo")

  def test_translation_only_includes_decorators_and_memory_api(self):
    names = load_translation_only_funcs()
    for name in (
      "refcount",
      "dataclass",
      "native",
      "alloc",
      "free",
      "id",
    ):
      self.assertIn(name, names, msg=name)

  def test_runtime_funcs_include_global_call_builtins(self):
    from src.analysis.stubs.builtin_stubs import builtin_global_call

    names = load_builtins_cpp_runtime_funcs()
    self.assertIn("abs", names)
    self.assertIn("__cmp__", names)
    self.assertIn("__truediv__", names)
    self.assertIn("hash", names)
    self.assertIn("input", names)
    self.assertIsNotNone(builtin_global_call("__mod__"))
    self.assertIsNotNone(builtin_global_call("__truediv__"))
    self.assertIsNotNone(builtin_global_call("__floordiv__"))

  def test_translation_only_excludes_runtime_builtins(self):
    names = load_translation_only_funcs()
    self.assertNotIn("len", names)
    self.assertNotIn("new", names)

  def test_package_root_global_call_aliases(self):
    from src.analysis.stubs.builtin_stubs import _package_root_global_call_cpp_aliases

    aliases = _package_root_global_call_cpp_aliases()
    self.assertIn("py_virtual", aliases)
    self.assertIn("py_abs", aliases)

  def test_module_function_cpp_rename_from_global_call(self):
    self.assertEqual(
      lookup_module_function_cpp_name(stdlib_module_path("io"), "open"),
      "py_open",
    )
    self.assertEqual(
      lookup_module_function_cpp_name(RUNTIME_BUILTINS_MODULE, "abs"),
      "py_abs",
    )
    self.assertEqual(
      lookup_module_function_cpp_name(RUNTIME_BUILTINS_MODULE, "virtual"),
      "py_virtual",
    )
    self.assertEqual(
      lookup_module_function_cpp_name(RUNTIME_BUILTINS_MODULE, "input"),
      "py_input",
    )


if __name__ == "__main__":
  unittest.main()
