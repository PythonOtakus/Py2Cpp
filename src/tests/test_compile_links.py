"""``compile._links_runtime_cpp``：``test/`` / ``examples/`` 勿链 ``py2cpp.cpp``。"""
from __future__ import annotations

import unittest
from pathlib import Path

from src.compile import (
  _cmd_msvc_cl,
  _links_runtime_cpp,
  _msvc_object_file_flags,
  discover_sqlite_include_dirs,
  runtime_has_sqlite_inl,
  sqlite3_obj_path,
)


class LinksRuntimeCppTests(unittest.TestCase):
  def test_test_dir_skips_runtime_cpp(self):
    src = Path("generated/test/ui/test_window.cpp")
    self.assertFalse(_links_runtime_cpp(src))

  def test_examples_dir_skips_runtime_cpp(self):
    src = Path("generated/examples/ui_panel_demo.cpp")
    self.assertFalse(_links_runtime_cpp(src))

  def test_user_module_links_runtime_cpp(self):
    src = Path("generated/myapp/main.cpp")
    self.assertTrue(_links_runtime_cpp(src))

  def test_msvc_fo_places_obj_beside_cpp(self):
    src = Path("generated/test/io/file/test_path.cpp").resolve()
    flags = _msvc_object_file_flags([src])
    self.assertEqual(flags, [f"/Fo{src.with_suffix('.obj')}"])

  def test_msvc_cl_command_includes_fo_for_parallel_safe_obj(self):
    src = Path("generated/test/io/test_path.cpp").resolve()
    cmd = _cmd_msvc_cl([src], [], src.with_suffix(".exe"), False, "c++14")
    fo = f"/Fo{src.with_suffix('.obj')}"
    self.assertIn(fo, cmd)

  def test_runtime_sqlite_inl_adds_include_dir(self):
    src = Path("generated/test/misc/test_print.cpp").resolve()
    self.assertTrue(runtime_has_sqlite_inl(src))
    incs = discover_sqlite_include_dirs(src)
    self.assertTrue(any(p.name == "sqlite" and (p / "sqlite3.h").is_file() for p in incs))

  def test_sqlite3_obj_path_unique_per_test_stem(self):
    a = Path("generated/test/lang/test_union.cpp").resolve()
    b = Path("generated/test/lang/test_staticproperty.cpp").resolve()
    obj_a = sqlite3_obj_path(a)
    obj_b = sqlite3_obj_path(b)
    self.assertEqual(obj_a.parent, a.parent)
    self.assertEqual(obj_b.parent, b.parent)
    self.assertNotEqual(obj_a, obj_b)
    self.assertEqual(obj_a.name, "test_union__sqlite3.obj")
    self.assertEqual(obj_b.name, "test_staticproperty__sqlite3.obj")


if __name__ == "__main__":
  unittest.main()
