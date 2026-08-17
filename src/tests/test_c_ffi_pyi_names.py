"""FFI 导出名：``c_ident_to_pascal`` / ``pyi_*_export_name``；默认 ``.pyi`` 路径。"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from src.tools.c_ffi_pyi import (
  FFI_ROOT,
  c_ident_to_pascal,
  default_pyi_path,
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
    self.assertEqual(c_ident_to_pascal("OVERFLOW"), "Overflow")
    self.assertEqual(c_ident_to_pascal("UNDERFLOW"), "Underflow")
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
    self.assertEqual(pyi_type_export_name("_exception", is_enum=False), "PyiExceptionRec")

  def test_variadic_renders_star_underscore(self):
    from src.tools.c_ffi_pyi import FuncDef, FfiModel, ParamDef, render_pyi
    from pathlib import Path

    model = FfiModel(
      funcs=[
        FuncDef(
          c_name="printf",
          py_name="pyiPrintf",
          ret="int",
          params=[ParamDef(py_name="_Format", ann="CStr")],
          variadic=True,
        ),
      ],
    )
    text = render_pyi(Path("stdio.h"), model)
    self.assertIn("def pyiPrintf(_Format: CStr, *_) -> int:", text)


class DefaultPyiPathTests(unittest.TestCase):
  def test_third_party_and_system_buckets(self):
    root = FFI_ROOT.parent
    self.assertEqual(
      default_pyi_path(root / "third_party" / "sqlite" / "sqlite3.h"),
      FFI_ROOT / "sqlite" / "sqlite3.pyi",
    )
    um = Path(r"C:\Program Files (x86)\Windows Kits\10\Include\10.0.22621.0\um\windows.h")
    with patch("src.tools.c_ffi_pyi.windows_sdk_include_bucket", return_value="um"):
      self.assertEqual(default_pyi_path(um), FFI_ROOT / "windows" / "windows.pyi")
    ucrt = Path(r"C:\Program Files (x86)\Windows Kits\10\Include\10.0.22621.0\ucrt\stdio.h")
    with patch("src.tools.c_ffi_pyi.windows_sdk_include_bucket", return_value="ucrt"):
      self.assertEqual(default_pyi_path(ucrt), FFI_ROOT / "crt" / "stdio.pyi")


if __name__ == "__main__":
  unittest.main()
