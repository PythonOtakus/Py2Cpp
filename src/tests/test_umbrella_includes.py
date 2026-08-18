"""``expand_umbrella_include_paths`` 与万能头 include 顺序。"""
from __future__ import annotations

import unittest

from src.codegen.umbrella_gen import build_py2cpp_umbrella_header
from src.constant.stdlib_discovery import STDLIB_REL_PATHS
from src.constant.stdlib_modules import UMBRELLA_IO_LATE_IF_PRESENT
from src.constant.umbrella import (
  UMBRELLA_BULK_SKIP,
  UMBRELLA_EARLY_SPECS,
  UMBRELLA_PREFIX_SPECS,
  expand_umbrella_include_paths,
)
from src.constant.stdlib_layout import stdlib_header_include


def _include_lines(header: str) -> list[str]:
  return [ln.strip() for ln in header.splitlines() if ln.strip().startswith("#include")]


def _unwrap_umbrella_path(p: str) -> str:
  if p.startswith("__py2cpp_guard_inl__:"):
    return p.split(":", 1)[1]
  return p


class UmbrellaIncludesTests(unittest.TestCase):
  def setUp(self):
    self.runtime_prefix = "py2cpp"
    self.modules = STDLIB_REL_PATHS

  def test_expand_prefix_order(self):
    paths = expand_umbrella_include_paths(self.runtime_prefix, self.modules)
    prefix = [f"{self.runtime_prefix}/char.h", f"{self.runtime_prefix}/byte.h"]
    self.assertEqual(paths[:2], prefix)

  def test_datetime_before_mono_queue_in_bulk(self):
    paths = expand_umbrella_include_paths(self.runtime_prefix, self.modules)
    dt = stdlib_header_include("system/datetime")
    mq = stdlib_header_include("alg/mono_queue")
    self.assertIn(dt, paths)
    self.assertIn(mq, paths)
    self.assertLess(paths.index(dt), paths.index(mq))

  def test_bulk_skip_covers_early_and_prefix_modules(self):
    for kind, name in UMBRELLA_PREFIX_SPECS:
      if kind == "module":
        self.assertIn(name, UMBRELLA_BULK_SKIP, msg=name)
    for kind, payload in UMBRELLA_EARLY_SPECS:
      if kind == "always":
        self.assertIn(str(payload), UMBRELLA_BULK_SKIP)
      elif kind == "if_member":
        self.assertIn(str(payload), UMBRELLA_BULK_SKIP)

  def test_build_header_matches_expand(self):
    header = build_py2cpp_umbrella_header(
      "PY2CPP_H",
      "test",
      self.runtime_prefix,
      self.modules,
    )
    expected = [
      f'#include "{_unwrap_umbrella_path(p)}"'
      for p in expand_umbrella_include_paths(self.runtime_prefix, self.modules)
    ]
    self.assertEqual(_include_lines(header), expected)

  def test_io_late_literals_after_bulk(self):
    paths = expand_umbrella_include_paths(self.runtime_prefix, self.modules)
    bulk_io_proto = stdlib_header_include("io/protocols")
    self.assertIn(bulk_io_proto, paths)
    if not UMBRELLA_IO_LATE_IF_PRESENT:
      self.assertNotIn(stdlib_header_include("io"), paths)
      return
    late_file = stdlib_header_include(UMBRELLA_IO_LATE_IF_PRESENT[0])
    self.assertIn(late_file, paths)
    self.assertLess(paths.index(bulk_io_proto), paths.index(late_file))
    self.assertNotIn(stdlib_header_include("io"), paths)

  def test_operators_suffix(self):
    paths = [
      _unwrap_umbrella_path(p)
      for p in expand_umbrella_include_paths(self.runtime_prefix, self.modules)
    ]
    self.assertEqual(paths[-2:], [f"{self.runtime_prefix}/operators.h", f"{self.runtime_prefix}/operators.inl"])


if __name__ == "__main__":
  unittest.main()
