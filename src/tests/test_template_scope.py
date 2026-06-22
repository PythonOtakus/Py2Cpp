"""``template_scope`` 宏头生成。"""
from __future__ import annotations

import unittest

from src.codegen.template_scope import (
  format_macro_header,
  namespace_qualifier_for_module_rel,
)


class TemplateScopeTests(unittest.TestCase):
  def test_namespace_qualifier_sqlite(self):
    self.assertEqual(
      namespace_qualifier_for_module_rel("sql/sqlite"),
      "py2cpp::sql::sqlite",
    )

  def test_macro_header_includes_namespace_define(self):
    text = format_macro_header(
      "sql/+sqlite.inl",
      "sql/sqlite",
      has_begin_scope=False,
    )
    self.assertIn("#define PY2CPP_NAMESPACE py2cpp::sql::sqlite", text)


if __name__ == "__main__":
  unittest.main()
