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

  def test_user_entry_should_not_emit_stdlib_modules(self):
    tr = _tr("test/misc/test_containers")
    tr.entry_module_path = "test/misc/test_containers"
    self.assertFalse(tr._should_emit_module(f"{RUNTIME_PKG}/util/list"))
    self.assertTrue(tr._should_emit_module("test/misc/test_containers"))

  def test_mirror_modules_skip_stub_header_write(self):
    from src.codegen.stdlib_mirror_codegen import (
      write_stdlib_codegen_header,
      write_stdlib_codegen_inl,
    )

    tr = _tr(RUNTIME_PKG)
    coro = f"{RUNTIME_PKG}/core/coroutine"
    self.assertTrue(write_stdlib_codegen_header(tr, coro))
    self.assertTrue(write_stdlib_codegen_inl(tr, coro))
    self.assertFalse(write_stdlib_codegen_header(tr, f"{RUNTIME_PKG}/util/list"))


if __name__ == "__main__":
  unittest.main()
