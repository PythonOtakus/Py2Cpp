"""``header_only`` / ``library`` 链接模型表。"""
from __future__ import annotations

import ast
import os
import unittest

from src.analysis.ir import ClassInfo
from src.constant.runtime_libs import (
  LIBRARY_TU_MACRO,
  _LIBRARY_REL_PATHS,
  header_only_mode,
  is_library_module,
  library_module_paths,
  wrap_inl_include_for_header,
)
from src.constant.stdlib_layout import stdlib_module_path
from src.emit.layout_emit import _module_template_inl_ok_in_library_tu


def _cls(
  name: str,
  module_path: str,
  *,
  template: bool = False,
  nested_of: ClassInfo | None = None,
) -> ClassInfo:
  node = ast.ClassDef(
    name=name,
    bases=[],
    keywords=[],
    decorator_list=[],
    body=[ast.Pass()],
    lineno=1,
  )
  info = ClassInfo(node, module_path=module_path)
  if template:
    info.type_params = ["T"]
  if nested_of is not None:
    info.outer_class = nested_of
  return info


class _Tr:
  def __init__(self, classes: dict[str, ClassInfo]):
    self.classes = classes


class RuntimeLibsTests(unittest.TestCase):
  def test_p1_whitelist_is_library(self):
    for rel in _LIBRARY_REL_PATHS:
      mp = stdlib_module_path(rel)
      self.assertTrue(is_library_module(mp), msg=rel)
    paths = library_module_paths()
    self.assertEqual(len(paths), len(_LIBRARY_REL_PATHS))
    self.assertTrue(all(p.startswith("py2cpp/") for p in paths))

  def test_template_modules_stay_header_only(self):
    for rel in ("util/list", "util/dict", "text/str", "concur/thread"):
      self.assertFalse(is_library_module(stdlib_module_path(rel)), msg=rel)

  def test_wrap_inl_skips_in_library_tu(self):
    lines = wrap_inl_include_for_header('#include "py2cpp/text/str.inl"')
    self.assertEqual(lines[0], f"#ifndef {LIBRARY_TU_MACRO}")
    self.assertEqual(lines[1], '#include "py2cpp/text/str.inl"')
    self.assertEqual(lines[2], "#endif")

  def test_header_only_mode_env(self):
    old = os.environ.get("PY2CPP_HEADER_ONLY")
    os.environ["PY2CPP_HEADER_ONLY"] = "1"
    try:
      self.assertTrue(header_only_mode())
      self.assertFalse(is_library_module(stdlib_module_path("util/memory")))
    finally:
      if old is None:
        os.environ.pop("PY2CPP_HEADER_ONLY", None)
      else:
        os.environ["PY2CPP_HEADER_ONLY"] = old

  def test_optional_union_variants_do_not_block_template_inl(self):
    opt = _cls("Optional", "py2cpp/core/optional", template=True)
    none = _cls("None_", "py2cpp/core/optional", nested_of=opt)
    some = _cls("Some", "py2cpp/core/optional", nested_of=opt)
    tr = _Tr({"Optional": opt, "None_": none, "Some": some})
    self.assertTrue(_module_template_inl_ok_in_library_tu(tr, "py2cpp/core/optional"))

  def test_mixed_thread_queue_skips_inl_in_library_tu(self):
    queue = _cls("Queue", "py2cpp/concur/thread", template=True)
    thread = _cls("Thread", "py2cpp/concur/thread")
    tr = _Tr({"Queue": queue, "Thread": thread})
    self.assertFalse(_module_template_inl_ok_in_library_tu(tr, "py2cpp/concur/thread"))


if __name__ == "__main__":
  unittest.main()
