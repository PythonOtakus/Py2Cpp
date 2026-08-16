"""FFI 导出名：``c_ident_to_pascal`` / ``pyi_*_export_name``。"""
from __future__ import annotations

import unittest

from src.tools.c_ffi_pyi import (
  c_ident_to_pascal,
  pyi_const_export_name,
  pyi_func_export_name,
  pyi_type_export_name,
)


class CIdentToPascalTests(unittest.TestCase):
  def test_snake_and_win32_digits(self):
    self.assertEqual(c_ident_to_pascal("WIN32_DATA_DIRECTORY_TYPE"), "Win32DataDirectoryType")
    self.assertEqual(c_ident_to_pascal("SQLITE_WIN32_DATA_DIRECTORY_TYPE"), "SqliteWin32DataDirectoryType")
    self.assertEqual(c_ident_to_pascal("SQLITE_FCNTL_DATA_VERSION"), "SqliteFcntlDataVersion")
    self.assertEqual(c_ident_to_pascal("sqlite3_open"), "Sqlite3Open")

  def test_trailing_aw_only_long_last_stem(self):
    self.assertEqual(c_ident_to_pascal("STATUSW"), "StatusW")
    self.assertEqual(c_ident_to_pascal("MESSAGEW"), "MessageW")
    self.assertEqual(c_ident_to_pascal("DATA"), "Data")
    self.assertEqual(c_ident_to_pascal("ROW"), "Row")
    self.assertEqual(c_ident_to_pascal("CreateWindowExW"), "CreateWindowExW")
    self.assertEqual(c_ident_to_pascal("XMLHttpRequest"), "XmlHttpRequest")
    self.assertEqual(c_ident_to_pascal("GLFWwindow"), "GlfwWindow")

  def test_pyi_export_wrappers(self):
    self.assertEqual(
      pyi_const_export_name("SQLITE_WIN32_DATA_DIRECTORY_TYPE"),
      "PyiSqliteWin32DataDirectoryType",
    )
    self.assertEqual(pyi_func_export_name("wglUseFontOutlinesA"), "pyiWglUseFontOutlinesA")
    self.assertEqual(pyi_type_export_name("sqlite3", is_enum=False), "PyiSqlite3")
    self.assertEqual(pyi_type_export_name("color", is_enum=True), "PyiColorEnum")


if __name__ == "__main__":
  unittest.main()
