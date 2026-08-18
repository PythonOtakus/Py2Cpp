"""``inject_discovery`` 扫描 ``+`` / ``-`` ``*.inl``。"""
from __future__ import annotations

import unittest

from src.constant.inject_discovery import (
  discover_class_header_inject_templates,
  discover_module_paste_after_templates,
  discover_module_paste_before_templates,
)
from src.constant.template_module_bindings import (
  module_rel_from_inject_template,
  module_rel_from_paste_before_template,
)


class InjectDiscoveryTests(unittest.TestCase):
  def test_module_rel_from_inject_template(self):
    self.assertEqual(module_rel_from_inject_template("util/+memory.inl"), "util/memory")
    self.assertEqual(module_rel_from_inject_template("text/+bytes.inl"), "text/bytes")
    self.assertEqual(module_rel_from_inject_template("text/+str.inl"), "text/str")

  def test_module_rel_from_paste_before_template(self):
    self.assertEqual(module_rel_from_paste_before_template("system/-time.inl"), "system/time")
    self.assertEqual(module_rel_from_paste_before_template("system/-environ.inl"), "system/environ")

    self.assertEqual(module_rel_from_paste_before_template("io/-file.inl"), "io/file")

  def test_module_rel_from_inject_template_h(self):
    self.assertEqual(module_rel_from_inject_template("text/+str.h"), "text/str")

  def test_discover_text_str_header_inject(self):
    found = discover_class_header_inject_templates()
    self.assertIn(("text/str", "text/+str.h"), found)

  def test_discover_util_memory_and_text_bytes(self):
    found = discover_module_paste_after_templates()
    self.assertIn(("util/memory", "util/+memory.inl", True), found)
    self.assertIn(("text/bytes", "text/+bytes.inl", False), found)
    self.assertIn(("text/str", "text/+str.inl", False), found)
    self.assertIn(("sql/sqlite", "sql/+sqlite.inl", False), found)
    self.assertIn(("ui/layout", "ui/+layout.inl", False), found)
    self.assertIn(("ui/app", "ui/+app.inl", False), found)
    self.assertIn(("ui/window", "ui/+window.inl", False), found)
    self.assertIn(("ui/widget", "ui/+widget.inl", False), found)
    self.assertIn(("io", "+io.inl", False), found)
    self.assertIn(("web/socket", "web/+socket.inl", False), found)
    self.assertIn(("core/exceptions", "core/+exceptions.inl", False), found)

  def test_discover_system_time_and_environ(self):
    found = discover_module_paste_before_templates()
    self.assertIn(("system/time", "system/-time.inl"), found)
    self.assertIn(("system/environ", "system/-environ.inl"), found)

    self.assertIn(("io/file", "io/-file.inl"), found)


if __name__ == "__main__":
  unittest.main()
