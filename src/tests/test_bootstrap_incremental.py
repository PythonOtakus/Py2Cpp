"""bootstrap 按模块增量：脏叶子 vs mixin/译器全量。"""
from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.codegen.bootstrap_incremental import (
  plan_bootstrap_incremental,
  py_rel_to_module_path,
)
from src.codegen.bootstrap_stamp import FORCE_ENV, write_stamp
from src.tests.test_bootstrap_stamp import _touch_layout


class BootstrapIncrementalPlanTests(unittest.TestCase):
  def setUp(self):
    self._old_force = os.environ.pop(FORCE_ENV, None)

  def tearDown(self):
    if self._old_force is None:
      os.environ.pop(FORCE_ENV, None)
    else:
      os.environ[FORCE_ENV] = self._old_force

  def test_py_rel_to_module_path(self):
    self.assertEqual(
      py_rel_to_module_path("py2cpp/io/path.py"),
      "py2cpp/io/path",
    )
    self.assertEqual(py_rel_to_module_path("py2cpp/io/__init__.py"), "py2cpp/io")
    self.assertIsNone(py_rel_to_module_path("templates/minimal.h"))

  def test_unchanged_is_empty_dirty(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      write_stamp(debug=False, header_only=False, root=root)
      plan = plan_bootstrap_incremental(root=root)
      self.assertFalse(plan.full)
      self.assertEqual(plan.dirty_modules, set())
      self.assertEqual(plan.reason, "unchanged")

  def test_leaf_py_is_incremental(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      sys_dir = root / "py2cpp" / "system"
      sys_dir.mkdir()
      (sys_dir / "environ.py").write_text("x = 1\n", encoding="utf-8")
      write_stamp(debug=False, header_only=False, root=root)
      time.sleep(0.05)
      (sys_dir / "environ.py").write_text("x = 2\n", encoding="utf-8")
      plan = plan_bootstrap_incremental(root=root)
      self.assertFalse(plan.full)
      self.assertEqual(plan.dirty_modules, {"py2cpp/system/environ"})

  def test_init_py_forces_full(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      write_stamp(debug=False, header_only=False, root=root)
      time.sleep(0.05)
      (root / "py2cpp" / "__init__.py").write_text("# changed\n", encoding="utf-8")
      plan = plan_bootstrap_incremental(root=root)
      self.assertTrue(plan.full)

  def test_mixin_file_forces_full(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      util = root / "py2cpp" / "util"
      util.mkdir()
      (util / "list.py").write_text("class X: pass\n", encoding="utf-8")
      write_stamp(debug=False, header_only=False, root=root)
      time.sleep(0.05)
      (util / "list.py").write_text("@mixin\nclass X: pass\n", encoding="utf-8")
      plan = plan_bootstrap_incremental(root=root)
      self.assertTrue(plan.full)

  def test_translator_change_forces_full(self):
    with TemporaryDirectory() as td:
      root = Path(td)
      _touch_layout(root)
      write_stamp(debug=False, header_only=False, root=root)
      time.sleep(0.05)
      (root / "src" / "translator.py").write_text("# changed\n", encoding="utf-8")
      plan = plan_bootstrap_incremental(root=root)
      self.assertTrue(plan.full)


class SkipCachedAnalysisModuleTests(unittest.TestCase):
  def test_skip_when_cached(self):
    from src.translator import Translator

    tr = Translator("x", "x.py")
    self.assertFalse(tr.skip_cached_analysis_module("py2cpp/system/environ"))
    tr.cached_analysis_modules = {"py2cpp/system/environ"}
    self.assertTrue(tr.skip_cached_analysis_module("py2cpp/system/environ"))
    self.assertTrue(tr.skip_cached_analysis_module("py2cpp\\system\\environ"))
    self.assertFalse(tr.skip_cached_analysis_module("py2cpp/io/path"))


if __name__ == "__main__":
  unittest.main()
