"""``apply_header_fixups`` / ``finalize_module_headers`` 表驱动破环。"""
from __future__ import annotations

import unittest

from src.analysis.analyzer import finalize_module_headers
from src.constant.header_fixups_data import HEADER_FORWARD_DECLS
from src.analysis.header_fixups import apply_header_fixups
from src.constant.stdlib_layout import CORE_PKG, RUNTIME_PKG, stdlib_header_include, stdlib_module_path

_PROTOCOL_TRAITS_H = f"{CORE_PKG}/protocol_traits.h"
_STR_H = stdlib_header_include("text/str")
_LIST_H = stdlib_header_include("util/list")
_SLICE_H = stdlib_header_include("util/slice")
_PROT_H = stdlib_header_include("core/protocols")
_ITER_H = stdlib_header_include("core/iter_result")
_OPS_H = f"{RUNTIME_PKG}/operators.h"
_PKG_H = stdlib_header_include(RUNTIME_PKG)


class HeaderFixupsTests(unittest.TestCase):
  def test_finalize_delegates_to_apply(self):
    mp = stdlib_module_path("util/list")
    inc = [_STR_H, _LIST_H]
    self.assertEqual(finalize_module_headers(mp, list(inc)), apply_header_fixups(mp, inc))

  def test_pystr_forward_only_removes_str_header(self):
    mp = stdlib_module_path("util/list")
    pre, fwd, post = apply_header_fixups(mp, [_STR_H, _LIST_H])
    self.assertNotIn(_STR_H, pre)
    self.assertIn(HEADER_FORWARD_DECLS["pystr"], fwd)
    self.assertIn(HEADER_FORWARD_DECLS["pylist_tpl"], fwd)
    self.assertEqual(post, [])

  def test_text_str_moves_post_class_and_forward_if_post(self):
    mp = stdlib_module_path("text/str")
    inc = [
      stdlib_header_include("text/bytes"),
      stdlib_header_include("util/list"),
      _PROT_H,
      _PROTOCOL_TRAITS_H,
      _ITER_H,
    ]
    pre, fwd, post = apply_header_fixups(mp, inc)
    self.assertNotIn(stdlib_header_include("text/bytes"), pre)
    self.assertIn(stdlib_header_include("text/bytes"), post)
    self.assertNotIn(_PROT_H, pre)
    self.assertNotIn(_PROTOCOL_TRAITS_H, pre)
    self.assertNotIn(_ITER_H, pre)
    self.assertIn(HEADER_FORWARD_DECLS["py_iter_result"], fwd)
    self.assertIn(HEADER_FORWARD_DECLS["pybytes"], fwd)
    self.assertEqual(pre[0], _SLICE_H)
    self.assertEqual(pre[1], f"{RUNTIME_PKG}/py_types.h")

  def test_runtime_pkg_moves_str_to_post(self):
    pre, fwd, post = apply_header_fixups(RUNTIME_PKG, [_STR_H, _OPS_H, _PROT_H])
    self.assertNotIn(_STR_H, pre)
    self.assertIn(_STR_H, post)
    self.assertNotIn(_OPS_H, pre)
    self.assertIn(HEADER_FORWARD_DECLS["pystr"], fwd)
    self.assertEqual(pre[0], f"{RUNTIME_PKG}/py_types.h")
    self.assertEqual(pre[1], _PROT_H)

  def test_io_inserts_stdio(self):
    pre, _, _ = apply_header_fixups(stdlib_module_path("io"), [_PKG_H])
    self.assertIn("<stdio.h>", pre)

  def test_generic_module_pkg_root_to_front(self):
    mp = stdlib_module_path("util/vars")
    pre, _, _ = apply_header_fixups(mp, [_LIST_H, _PKG_H])
    self.assertEqual(pre[0], _PKG_H)


if __name__ == "__main__":
  unittest.main()
