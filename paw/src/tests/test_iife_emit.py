"""``iife_emit`` 格式化回归。"""
from __future__ import annotations

import unittest

from src.emit.iife_emit import emit_iife


class IifeEmitTests(unittest.TestCase):
  def test_multiline_for_loop(self):
    cpp = emit_iife(
      "PyInt",
      [
        "PyInt acc = 0",
        (
          "for (PyInt fi = 0; fi < xs.__len__(); fi += 1) "
          "{ PyInt x = xs.__getitem__(fi); acc = (acc + x); }"
        ),
        "return acc",
      ],
    )
    self.assertIn("[&]() -> PyInt\n{\n", cpp)
    self.assertIn("for (PyInt fi = 0; fi < xs.__len__(); fi += 1)\n  {\n", cpp)
    self.assertIn("    PyInt x = xs.__getitem__(fi);", cpp)
    self.assertIn("    acc = (acc + x);", cpp)
    self.assertIn("  return acc;\n})()", cpp)

  def test_nested_for_in_block(self):
    cpp = emit_iife(
      "PyInt",
      [
        (
          "for (PyInt fi = 0; fi < xs.__len__(); fi += 1) "
          "{ PyInt x = xs.__getitem__(fi); "
          "for (PyInt fj = 0; fj < ys.__len__(); fj += 1) "
          "{ PyInt y = ys.__getitem__(fj); acc = (acc + (x * y)); } }"
        ),
        "return acc",
      ],
    )
    self.assertIn(
      "for (PyInt fj = 0; fj < ys.__len__(); fj += 1)\n    {\n",
      cpp,
    )
    self.assertNotIn("for (PyInt fj = 0;\n", cpp)

  def test_iife_rhs_assignment_stays_intact(self):
    inner = emit_iife(None, ["auto bo65 = a;", "return b;"])
    cpp = emit_iife(None, [f"auto bo64 = {inner};", "return bo64;"])
    self.assertIn("  auto bo64 = ([&]()\n  {\n", cpp)
    self.assertIn("  })();", cpp)
    self.assertNotIn("\n  )();", cpp)

  def test_braces_align_with_sig_line(self):
    """``{``/``}`` 与 ``[&]()`` 同级；由 ``write_line`` 再套语句缩进。"""
    from src.translator import Translator

    tr = Translator.__new__(Translator)
    tr.indent_level = 2
    lines: list[str] = []
    tr.source_lines = lines
    tr.in_header = False
    tr.header_target = None
    tr.source_target = None
    tr.inl_target = None
    tr.per_module_header_lines = {}
    tr.per_module_source_lines = {}
    tr.per_module_inl_lines = {}
    iife = emit_iife("PyInt", ["return 1;"])
    tr.write_line(f"this->assertEqual({iife}, 1);")
    self.assertEqual(
      lines,
      [
        "    this->assertEqual(([&]() -> PyInt",
        "    {",
        "      return 1;",
        "    })(), 1);",
      ],
    )

  def test_nested_if_block(self):
    cpp = emit_iife(
      None,
      [
        (
          "if (step > 0) { if (n < 0) return (PyInt)0; "
          "return ::__floordiv__((n + step - 1), step); }"
        ),
      ],
    )
    self.assertIn("if (step > 0)\n  {\n", cpp)
    self.assertIn("    if (n < 0) return (PyInt)0;", cpp)


if __name__ == "__main__":
  unittest.main()
