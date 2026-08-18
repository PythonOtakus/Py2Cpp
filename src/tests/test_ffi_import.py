"""``ffi/**/*.pyi`` 模块发现与路径映射。"""
from __future__ import annotations

import unittest
from pathlib import Path

from src.analysis.import_resolver import (
  absolute_dotted_to_module_path,
  discover_translation_modules,
  resolve_import_target_path,
  ImportRequest,
)
from src.analysis.module_namespace import namespace_qualifier_for_module
from src.constant.ffi_layout import (
  FFI_ROOT,
  find_ffi_source_file,
  ffi_c_struct_using_target,
  ffi_header_include,
  ffi_opaque_c_tag,
  ffi_opaque_py_name,
  is_ffi_module_path,
)
from src.constant.paths import _REPO_ROOT
from src.constant.stdlib_layout import RUNTIME_PKG
from src.analysis.ir import ClassInfo
import ast


class TestFfiOpaqueNames(unittest.TestCase):
  def test_legacy_h_suffix_roundtrip(self) -> None:
    for c in ("sqlite3", "sqlite3_stmt", "Fts5Context", "sqlite3_api_routines"):
      py = ffi_opaque_py_name(c)
      self.assertNotEqual(py, c)
      self.assertTrue(py.endswith("_h"))
      self.assertEqual(ffi_opaque_c_tag(py), c)

  def test_using_target(self) -> None:
    node = ast.ClassDef(
      name="PyiSqlite3",
      bases=[],
      keywords=[],
      body=[ast.Pass()],
      decorator_list=[
        ast.Name(id="native", ctx=ast.Load()),
        ast.Call(
          func=ast.Name(id="native_name", ctx=ast.Load()),
          args=[ast.Constant(value="sqlite3")],
          keywords=[],
        ),
      ],
    )
    info = ClassInfo(node, module_path="ffi/sqlite/sqlite3")
    self.assertEqual(ffi_c_struct_using_target(info), "::sqlite3")
    self.assertEqual(info.cpp_name(), "PyiSqlite3")


class TestFfiLayout(unittest.TestCase):
  def test_paths(self) -> None:
    self.assertTrue(is_ffi_module_path("ffi/windows/windows"))
    self.assertTrue(is_ffi_module_path("ffi/crt/stdio"))
    self.assertTrue(is_ffi_module_path("ffi/sqlite/sqlite3"))
    self.assertFalse(is_ffi_module_path("py2cpp/ffi/windows"))
    self.assertEqual(
      absolute_dotted_to_module_path("ffi.windows.windows"),
      "ffi/windows/windows",
    )
    self.assertEqual(
      absolute_dotted_to_module_path("ffi.crt.stdio"),
      "ffi/crt/stdio",
    )
    self.assertEqual(
      absolute_dotted_to_module_path("ffi.sqlite.sqlite3"),
      "ffi/sqlite/sqlite3",
    )
    self.assertEqual(
      ffi_header_include("ffi/windows/windows"),
      "ffi/windows/windows.h",
    )
    self.assertEqual(
      namespace_qualifier_for_module("ffi/windows/windows"),
      "ffi::windows::windows",
    )
    self.assertEqual(
      namespace_qualifier_for_module("ffi/crt/stdio"),
      "ffi::crt::stdio",
    )
    self.assertEqual(
      namespace_qualifier_for_module("ffi/sqlite/sqlite3"),
      "ffi::sqlite::sqlite3",
    )

  def test_find_source(self) -> None:
    p = find_ffi_source_file("ffi/sqlite/sqlite3", project_root=_REPO_ROOT)
    self.assertIsNotNone(p)
    assert p is not None
    self.assertEqual(p, FFI_ROOT / "sqlite" / "sqlite3.pyi")
    self.assertTrue(p.is_file())
    win = find_ffi_source_file("ffi/windows/windows", project_root=_REPO_ROOT)
    self.assertIsNotNone(win)
    assert win is not None
    self.assertEqual(win, FFI_ROOT / "windows" / "windows.pyi")
    self.assertTrue(win.is_file())
    crt = find_ffi_source_file("ffi/crt/stdio", project_root=_REPO_ROOT)
    self.assertIsNotNone(crt)
    assert crt is not None
    self.assertEqual(crt, FFI_ROOT / "crt" / "stdio.pyi")
    self.assertTrue(crt.is_file())

  def test_resolve_import(self) -> None:
    runtime = _REPO_ROOT / RUNTIME_PKG
    req = ImportRequest(
      level=0,
      module="ffi.sqlite.sqlite3",
      names=(("pyiSqlite3Open", None),),
      is_star=False,
      is_plain_import=False,
    )
    path = resolve_import_target_path(
      "test/x",
      req,
      project_root=_REPO_ROOT,
      runtime_root=runtime,
    )
    self.assertEqual(path, "ffi/sqlite/sqlite3")


class TestFfiDiscover(unittest.TestCase):
  def test_discover_via_entry(self) -> None:
    entry = _REPO_ROOT / "src" / "tests" / "_ffi_entry_sqlite.py"
    self.assertTrue(entry.is_file(), msg="fixture missing")
    mods = discover_translation_modules(
      entry,
      include_stdlib=True,
      runtime_root=_REPO_ROOT / RUNTIME_PKG,
      project_root=_REPO_ROOT,
    )
    paths = {mp for mp, _ in mods}
    self.assertIn("ffi/sqlite/sqlite3", paths)


class TestFfiTranslateGlue(unittest.TestCase):
  def test_sqlite_glue_namespace(self) -> None:
    import tempfile

    from src.translator import Translator

    entry = _REPO_ROOT / "src" / "tests" / "_ffi_entry_sqlite.py"
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      Translator.translate_file(
        str(entry),
        output_dir=str(out),
        include_stdlib=True,
        emit_main=True,
      )
      header = out / "runtime" / "ffi" / "sqlite" / "sqlite3.h"
      self.assertTrue(header.is_file(), msg=f"missing {header}")
      text = header.read_text(encoding="utf-8").replace("\r\n", "\n")
      self.assertIn("namespace ffi", text)
      self.assertIn("namespace sqlite3", text)
      self.assertNotIn("namespace lib", text)
      self.assertNotIn("namespace py2cpp\n{\n  namespace ffi", text)
      self.assertIn('#include "ffi/sqlite/sqlite3.inl"', text)
      self.assertIn("#include <sqlite3.h>", text)
      self.assertNotIn("class sqlite3", text)
      self.assertNotIn("struct ::sqlite3", text)
      self.assertIn("using PyiSqlite3 = ::sqlite3;", text)
      self.assertIn("pyiSqlite3Open", text)
      self.assertIn("PyiSqliteOk", text)
      # 嵌套 C 结构体：using 右侧须带外层限定
      self.assertIn(
        "using PyiSqlite3IndexOrderby = ::sqlite3_index_info::sqlite3_index_orderby;",
        text,
      )
      inl = header.with_suffix(".inl")
      self.assertTrue(inl.is_file(), msg=f"missing glue {inl}")
      inl_text = inl.read_text(encoding="utf-8")
      self.assertIn("py2cpp FFI glue", inl_text)
      self.assertIn("#include <sqlite3.h>", inl_text)
      self.assertIn("::sqlite3_open", inl_text)
      self.assertIn("PyiSqlite3", inl_text)
      self.assertIn("inline", inl_text)
      self.assertNotIn("sqlite3_auto_extension", inl_text)


  def test_crt_stdio_and_io_glue_use_allowlisted_symbols(self) -> None:
    import tempfile

    from src.translator import Translator

    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      entry = out / "entry.py"
      entry.write_text(
        "from py2cpp import *\n"
        "from ffi.crt.io import pyiIsatty\n"
        "from ffi.crt.stdio import PyiIobuf, pyiFileno, pyiFflush\n"
        "\n"
        "def check_terminal(stream: Pointer[PyiIobuf]) -> bool:\n"
        "  pyiFflush(stream)\n"
        "  return pyiIsatty(pyiFileno(stream)) != 0\n",
        encoding="utf-8",
      )
      Translator.translate_file(
        str(entry),
        output_dir=str(out),
        include_stdlib=True,
        emit_main=False,
      )
      stdio_header = out / "runtime" / "ffi" / "crt" / "stdio.h"
      self.assertTrue(stdio_header.is_file(), msg=f"missing {stdio_header}")
      stdio_text = stdio_header.read_text(encoding="utf-8")
      self.assertIn("using PyiIobuf = ::_iobuf;", stdio_text)
      self.assertIn("pyiFileno", stdio_text)
      stdio_inl = stdio_header.with_suffix(".inl")
      self.assertIn("::fflush(_Stream)", stdio_inl.read_text(encoding="utf-8"))
      io_inl = out / "runtime" / "ffi" / "crt" / "io.inl"
      self.assertTrue(io_inl.is_file(), msg=f"missing {io_inl}")
      self.assertIn("::_isatty(_FileHandle)", io_inl.read_text(encoding="utf-8"))
  def test_crt_overload_glue_uses_allowlisted_exit(self) -> None:
    import tempfile

    from src.translator import Translator

    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      entry = out / "entry.py"
      entry.write_text(
        "from py2cpp import *\n"
        "from ffi.crt.stdlib import pyiExit\n"
        "\n"
        "def exit_now(code: int) -> None:\n"
        "  pyiExit(code)\n",
        encoding="utf-8",
      )
      Translator.translate_file(
        str(entry),
        output_dir=str(out),
        include_stdlib=True,
        emit_main=False,
      )
      inl = out / "runtime" / "ffi" / "crt" / "stdlib.inl"
      self.assertTrue(inl.is_file(), msg=f"missing {inl}")
      text = inl.read_text(encoding="utf-8")
      self.assertIn("inline void ffi::crt::stdlib::pyiExit", text)
      self.assertIn("::exit(_Code)", text)
if __name__ == "__main__":
  unittest.main()
