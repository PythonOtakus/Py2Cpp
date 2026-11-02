"""默认 ``Py`` 类名前缀（``default_py_class_cpp_name`` / ``cpp_ident``）。"""
from __future__ import annotations

import unittest

from src.analysis.ir import cpp_ident
from src.constant.language import default_py_class_cpp_name


class DefaultPyClassCppNameTests(unittest.TestCase):
  def test_leading_underscores_move_before_py(self):
    self.assertEqual(default_py_class_cpp_name("Handle"), "PyHandle")
    self.assertEqual(default_py_class_cpp_name("_Handle"), "_PyHandle")
    self.assertEqual(default_py_class_cpp_name("__Foo"), "__PyFoo")
    self.assertEqual(default_py_class_cpp_name("_ThreadHandle"), "_PyThreadHandle")

  def test_lowercase_builtin_capitalizes(self):
    self.assertEqual(default_py_class_cpp_name("list"), "PyList")
    self.assertEqual(default_py_class_cpp_name("str"), "PyStr")
    self.assertEqual(default_py_class_cpp_name("dict"), "PyDict")
    self.assertEqual(default_py_class_cpp_name("atomic"), "PyAtomic")

  def test_no_double_py_prefix(self):
    self.assertEqual(default_py_class_cpp_name("PyList"), "PyList")
    self.assertEqual(default_py_class_cpp_name("PyDictEntryUnsafe"), "PyDictEntryUnsafe")

  def test_ffi_pyi_untouched(self):
    self.assertEqual(default_py_class_cpp_name("PyiSqlite3"), "PyiSqlite3")
    self.assertEqual(default_py_class_cpp_name("pyiSqlite3Open"), "pyiSqlite3Open")
    self.assertEqual(default_py_class_cpp_name("Pyi_sqlite3"), "Pyi_sqlite3")

  def test_cpp_ident_scalars_and_default(self):
    self.assertEqual(cpp_ident("int"), "PyInt")
    self.assertEqual(cpp_ident("void"), "void")
    self.assertEqual(cpp_ident("Self"), "Self")
    self.assertEqual(cpp_ident("Handle"), "PyHandle")
    self.assertEqual(cpp_ident("DictEntryUnsafe"), "PyDictEntryUnsafe")

  def test_self_stays_self(self):
    self.assertEqual(default_py_class_cpp_name("Self"), "Self")

  def test_single_letter_type_param_untouched(self):
    self.assertEqual(default_py_class_cpp_name("T"), "T")
    self.assertEqual(default_py_class_cpp_name("U"), "U")
    self.assertEqual(default_py_class_cpp_name("_T"), "_T")
    self.assertEqual(cpp_ident("T"), "T")

  def test_multi_letter_class_still_gets_py(self):
    # 形参名如 YieldValue 在调用处靠 _active_type_params 跳过；类名仍加 Py
    self.assertEqual(default_py_class_cpp_name("YieldValue"), "PyYieldValue")
    self.assertEqual(default_py_class_cpp_name("Handle"), "PyHandle")


if __name__ == "__main__":
  unittest.main()
