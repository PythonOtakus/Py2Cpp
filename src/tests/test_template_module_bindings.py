"""``templates`` 镜像 / inject 模板须绑定 ``py2cpp/`` 模块。"""
from __future__ import annotations

import unittest

from src.constant.stdlib_discovery import STDLIB_REL_PATH_SET
from src.constant.template_module_bindings import (
  iter_bound_template_modules,
  module_rel_from_inject_template,
  module_rel_from_mirror_template,
  module_rel_from_template_rel,
  validate_template_module_bindings,
)


class TemplateModuleBindingsTests(unittest.TestCase):
  def test_validate_current_templates(self):
    validate_template_module_bindings()

  def test_mirror_module_rel(self):
    self.assertEqual(module_rel_from_mirror_template("sql/sqlite.inl"), "sql/sqlite")
    self.assertEqual(module_rel_from_mirror_template("util/tuple.h"), "util/tuple")

  def test_module_rel_from_template_rel_header(self):
    self.assertEqual(module_rel_from_template_rel("util/tuple.h"), "util/tuple")

  def test_inject_module_rel(self):
    self.assertEqual(module_rel_from_inject_template("text/+bytes.inl"), "text/bytes")

  def test_module_rel_from_template_rel(self):
    self.assertEqual(module_rel_from_template_rel("text/+bytes.inl"), "text/bytes")
    self.assertEqual(module_rel_from_template_rel("system/-time.inl"), "system/time")
    self.assertEqual(module_rel_from_template_rel("-math.inl"), "math")
    self.assertEqual(module_rel_from_template_rel("sql/sqlite.inl"), "sql/sqlite")
    self.assertEqual(module_rel_from_template_rel("+io.inl"), "io")
    self.assertEqual(module_rel_from_template_rel("web/+socket.inl"), "web/socket")
    self.assertEqual(module_rel_from_template_rel("text/+str.inl"), "text/str")
    self.assertEqual(
      module_rel_from_template_rel("core/~exception_group_dynamic_impl.inl"),
      "core/exceptions",
    )
    self.assertEqual(
      module_rel_from_template_rel("~test/~syntax_showcase.inl"),
      "util/memory",
    )

  def test_bound_templates_in_stdlib(self):
    for template_rel, module_rel, _ in iter_bound_template_modules():
      self.assertIn(module_rel, STDLIB_REL_PATH_SET, msg=template_rel)

  def test_rejects_orphan_mirror(self):
    rels = set(STDLIB_REL_PATH_SET)
    rels.discard("util/memory")
    with self.assertRaises(ValueError):
      validate_template_module_bindings(stdlib_rel_paths=frozenset(rels))


if __name__ == "__main__":
  unittest.main()
