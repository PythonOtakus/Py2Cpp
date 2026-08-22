"""``order_stdlib_modules_by_header_deps``：analyze 后 umbrella 顺序。"""
from __future__ import annotations

import unittest

from src.analysis.ir import ModuleAnalysis
from src.analysis.stdlib_module_order import (
  header_path_to_stdlib_rel,
  order_stdlib_modules_by_header_deps,
)
from src.constant.stdlib_discovery import STDLIB_REL_PATH_SET, order_stdlib_rel_paths
from src.constant.stdlib_layout import stdlib_header_include, stdlib_module_path


class StdlibModuleOrderTests(unittest.TestCase):
  def test_header_path_to_rel(self):
    self.assertEqual(
      header_path_to_stdlib_rel(stdlib_header_include("util/list")),
      "util/list",
    )
    self.assertIsNone(header_path_to_stdlib_rel("<stdio.h>"))

  def test_topo_within_util_tier(self):
    base = order_stdlib_rel_paths(STDLIB_REL_PATH_SET)
    pool_i = base.index("util/pool")
    list_i = base.index("util/list")
    self.assertGreater(pool_i, list_i)
    ma = {
      stdlib_module_path("util/pool"): ModuleAnalysis(
        path=stdlib_module_path("util/pool"),
        includes=[
          stdlib_header_include("util/list"),
          stdlib_header_include("util/stack_array"),
        ],
      ),
    }
    mods = ("util/pool", "util/list", "util/stack_array", "util/misc")
    ordered = order_stdlib_modules_by_header_deps(mods, ma)
    self.assertLess(ordered.index("util/list"), ordered.index("util/pool"))
    self.assertLess(ordered.index("util/stack_array"), ordered.index("util/pool"))

  def test_package_root_after_children(self):
    mods = ("console", "console/exceptions", "console/render", "console/popen")
    ma = {
      stdlib_module_path("console"): ModuleAnalysis(
        path=stdlib_module_path("console"),
        includes=[],
      ),
    }
    ordered = order_stdlib_modules_by_header_deps(mods, ma)
    self.assertLess(ordered.index("console/exceptions"), ordered.index("console"))
    self.assertLess(ordered.index("console/render"), ordered.index("console"))
    self.assertLess(ordered.index("console/popen"), ordered.index("console"))
