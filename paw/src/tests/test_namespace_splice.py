"""``splice_before_innermost_namespace_close`` 单元测。"""
import unittest

from src.analysis.module_namespace import splice_before_innermost_namespace_close


class TestNamespaceSplice(unittest.TestCase):
  def test_splice_before_innermost_close(self):
    body = [
      "namespace py2cpp",
      "{",
      "  namespace io",
      "  {",
      "    namespace file",
      "    {",
      "      void foo();",
      "    } // namespace file",
      "  } // namespace io",
      "} // namespace py2cpp",
    ]
    insert = ["      class walk_generator;", ""]
    out = splice_before_innermost_namespace_close(body, insert)
    self.assertIn("      class walk_generator;", out)
    file_close = out.index("    } // namespace file")
    self.assertLess(out.index("      class walk_generator;"), file_close)
    self.assertEqual(out[file_close + 1], "  } // namespace io")


if __name__ == "__main__":
  unittest.main()
