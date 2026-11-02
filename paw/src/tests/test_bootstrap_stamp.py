"""bootstrap stamp 跳过与写盘去重。"""
from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.codegen.bootstrap_stamp import (
  FORCE_ENV,
  should_skip_translate,
  stamp_path,
  write_stamp,
)
from src.codegen.write_if_changed import write_text_if_changed


def _touch_layout(root: Path) -> None:
  (root / "py2cpp").mkdir()
  (root / "py2cpp" / "__init__.py").write_text("# runtime\n", encoding="utf-8")
  (root / "templates").mkdir()
  (root / "templates" / "minimal.h").write_text("// t\n", encoding="utf-8")
  (root / "src").mkdir()
  (root / "src" / "translator.py").write_text("# tr\n", encoding="utf-8")
  (root / "src" / "tests").mkdir()
  (root / "src" / "tests" / "test_x.py").write_text("# test\n", encoding="utf-8")
  (root / "main.py").write_text("# cli\n", encoding="utf-8")
  umb = root / "generated" / "runtime" / "py2cpp"
  umb.mkdir(parents=True)
  (umb / "minimal.h").write_text("// umbrella\n", encoding="utf-8")


class WriteIfChangedTests(unittest.TestCase):
  def test_skip_same_body_ignores_generated_at(self):
    with TemporaryDirectory() as td:
      p = Path(td) / "a.h"
      first = "// 由 py2cpp 根据 x 生成\n// 生成时间: 2000-01-01 00:00:00\nint x;\n"
      self.assertTrue(write_text_if_changed(p, first))
      m0 = p.stat().st_mtime
      time.sleep(0.05)
      second = "// 由 py2cpp 根据 x 生成\n// 生成时间: 2099-12-31 23:59:59\nint x;\n"
      self.assertFalse(write_text_if_changed(p, second))
      self.assertEqual(p.stat().st_mtime, m0)
      self.assertEqual(p.read_text(encoding="utf-8"), first)

  def test_rewrite_when_body_changes(self):
    with TemporaryDirectory() as td:
      p = Path(td) / "a.h"
      write_text_if_changed(p, "// 生成时间: a\nint x;\n")
      self.assertTrue(write_text_if_changed(p, "// 生成时间: b\nint y;\n"))
      self.assertIn("int y;", p.read_text(encoding="utf-8"))


class BootstrapStampTests(unittest.TestCase):
  def setUp(self):
    self._old_force = os.environ.pop(FORCE_ENV, None)

  def tearDown(self):
    if self._old_force is None:
      os.environ.pop(FORCE_ENV, None)
    else:
      os.environ[FORCE_ENV] = self._old_force

  def test_skip_when_stamp_newer_than_inputs(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      write_stamp(debug=False, header_only=False, root=root)
      self.assertTrue(
        should_skip_translate(debug=False, header_only=False, root=root)
      )

  def test_no_skip_when_py2cpp_newer(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      write_stamp(debug=False, header_only=False, root=root)
      time.sleep(0.05)
      (root / "py2cpp" / "__init__.py").write_text("# changed\n", encoding="utf-8")
      self.assertFalse(
        should_skip_translate(debug=False, header_only=False, root=root)
      )

  def test_templates_macro_do_not_invalidate(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      write_stamp(debug=False, header_only=False, root=root)
      time.sleep(0.05)
      macro = root / "templates" / "~macro" / "text"
      macro.mkdir(parents=True)
      (macro / "+str.h.h").write_text("// clangd stub\n", encoding="utf-8")
      self.assertTrue(
        should_skip_translate(debug=False, header_only=False, root=root)
      )

  def test_src_tests_do_not_invalidate(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      write_stamp(debug=False, header_only=False, root=root)
      time.sleep(0.05)
      (root / "src" / "tests" / "test_x.py").write_text("# later\n", encoding="utf-8")
      self.assertTrue(
        should_skip_translate(debug=False, header_only=False, root=root)
      )

  def test_debug_mismatch_does_not_skip(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      write_stamp(debug=False, header_only=False, root=root)
      self.assertFalse(
        should_skip_translate(debug=True, header_only=False, root=root)
      )

  def test_force_env_disables_skip(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      write_stamp(debug=False, header_only=False, root=root)
      os.environ[FORCE_ENV] = "1"
      self.assertFalse(
        should_skip_translate(debug=False, header_only=False, root=root)
      )

  def test_stamp_path_under_generated_runtime(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      self.assertEqual(
        stamp_path(root),
        root / "generated" / "runtime" / ".bootstrap.stamp",
      )


if __name__ == "__main__":
  unittest.main()
