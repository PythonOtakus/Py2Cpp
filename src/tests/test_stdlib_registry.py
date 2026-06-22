"""``constant.stdlib_discovery``：``py2cpp/`` 遍历发现标准库模块。"""
from __future__ import annotations

import unittest
from pathlib import Path

from src.constant.paths import PY2CPP_ROOT
from src.constant.stdlib_discovery import (
  STDLIB_REL_PATHS,
  STDLIB_REL_PATH_SET,
  discover_stdlib_rel_paths,
)

_REPO = Path(__file__).resolve().parents[2]


class StdlibRegistryTests(unittest.TestCase):
  def test_discover_matches_py_files(self):
    paths = discover_stdlib_rel_paths(PY2CPP_ROOT)
    self.assertEqual(frozenset(paths), STDLIB_REL_PATH_SET)
    self.assertEqual(len(paths), len(STDLIB_REL_PATH_SET))
    for rel in paths:
      mod_py = PY2CPP_ROOT.joinpath(*rel.split("/")).with_suffix(".py")
      pkg_init = PY2CPP_ROOT.joinpath(*rel.split("/"), "__init__.py")
      self.assertTrue(mod_py.is_file() or pkg_init.is_file(), msg=rel)

  def test_package_root_not_listed(self):
    self.assertNotIn("", STDLIB_REL_PATH_SET)
    self.assertNotIn("py2cpp", STDLIB_REL_PATH_SET)

  def test_core_util_samples_present(self):
    for rel in (
      "util/list",
      "util/vars",
      "text/str",
      "core/exceptions",
      "numeric/modint",
    ):
      self.assertIn(rel, STDLIB_REL_PATH_SET, msg=rel)

  def test_reflect_not_translated(self):
    self.assertNotIn("reflect/mixin", STDLIB_REL_PATH_SET)
    self.assertNotIn("reflect", STDLIB_REL_PATH_SET)

  def test_py2cpp_test_not_auto_discovered(self):
    self.assertNotIn("test/unittest", STDLIB_REL_PATH_SET)
    self.assertNotIn("test/test_temp", STDLIB_REL_PATH_SET)

  def test_domain_reexport_inits_skipped(self):
    self.assertNotIn("util", STDLIB_REL_PATH_SET)
    self.assertNotIn("numeric", STDLIB_REL_PATH_SET)
    self.assertNotIn("alg", STDLIB_REL_PATH_SET)

  def test_order_tiers_and_priority(self):
    from src.constant.stdlib_discovery import _stdlib_tier_index, order_stdlib_rel_paths
    from src.constant.stdlib_modules import UMBRELLA_PREFIX_TIERS, UMBRELLA_PRIORITY_MODULES

    ordered = order_stdlib_rel_paths(STDLIB_REL_PATH_SET)
    self.assertEqual(ordered, STDLIB_REL_PATHS)
    idx_dt = ordered.index("system/datetime")
    idx_mq = ordered.index("alg/mono_queue")
    self.assertLess(idx_dt, idx_mq)
    idx_misc = ordered.index("util/misc")
    idx_stat = ordered.index("math/stat")
    self.assertLess(idx_misc, idx_stat)
    idx_set = ordered.index("util/set")
    idx_json = ordered.index("serde/json")
    self.assertLess(idx_set, idx_json)
    idx_prot = ordered.index("alg/protocols")
    idx_nav = ordered.index("alg/navigate")
    self.assertLess(idx_prot, idx_nav)
    last_tier = -1
    for mod in ordered:
      tier = _stdlib_tier_index(mod)
      if mod not in UMBRELLA_PRIORITY_MODULES:
        self.assertGreaterEqual(tier, last_tier)
        last_tier = tier
    for prefix in UMBRELLA_PREFIX_TIERS:
      self.assertTrue(
        any(p.startswith(prefix) or p == prefix.rstrip("/") for p in STDLIB_REL_PATH_SET),
        msg=prefix,
      )


if __name__ == "__main__":
  unittest.main()
