"""``_can_write_stdlib_artifact``：并行 build 时禁止 test 入口重写 runtime。"""
from __future__ import annotations

import unittest

from src.constant.stdlib_layout import RUNTIME_PKG
from src.translator import Translator


def _tr(entry: str) -> Translator:
  tr = Translator(entry, f"{entry}.py")
  tr.entry_module_path = entry
  return tr


class StdlibWriteGuardTests(unittest.TestCase):
  def test_bootstrap_writes_all_stdlib(self):
    tr = _tr(RUNTIME_PKG)
    self.assertTrue(tr._can_write_stdlib_artifact(f"{RUNTIME_PKG}/util/list"))
    self.assertTrue(tr._can_write_stdlib_artifact(f"{RUNTIME_PKG}/spatial/matrix"))

  def test_test_entry_writes_no_stdlib(self):
    tr = _tr("test/misc/test_containers")
    self.assertFalse(tr._can_write_stdlib_artifact(f"{RUNTIME_PKG}/util/list"))
    self.assertFalse(tr._can_write_stdlib_artifact(f"{RUNTIME_PKG}/member_access"))
    self.assertFalse(tr._can_write_stdlib_artifact(f"{RUNTIME_PKG}/test/unittest"))

  def test_bootstrap_can_write_member_access(self):
    tr = _tr(RUNTIME_PKG)
    self.assertTrue(tr._can_write_stdlib_artifact(f"{RUNTIME_PKG}/member_access"))

  def test_single_stdlib_entry_writes_only_self(self):
    mod = f"{RUNTIME_PKG}/spatial/matrix"
    tr = _tr(mod)
    self.assertTrue(tr._can_write_stdlib_artifact(mod))
    self.assertFalse(tr._can_write_stdlib_artifact(f"{RUNTIME_PKG}/util/list"))


if __name__ == "__main__":
  unittest.main()
