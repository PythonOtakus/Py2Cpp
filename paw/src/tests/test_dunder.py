"""模块内建常量 ``__name__`` / ``__file__`` / ``__line__`` / ``__debug__`` 的 C++ 降级。"""
from __future__ import annotations

import ast
import unittest

from src.translator import Translator


def _emit_expr(body: str, *, entry: str = "mod", debug: bool = False) -> str:
  mod_src = f"def probe():\n  {body}"
  tree = ast.parse(mod_src)
  func = tree.body[0]
  assert isinstance(func, ast.FunctionDef)
  stmt = func.body[0]
  assert isinstance(stmt, ast.Return) and stmt.value is not None
  tr = Translator(entry, f"{entry}.py", debug=debug)
  tr.entry_module_path = entry
  tr._parse_modules([(entry, mod_src)])
  return tr.visit(stmt.value)


class ModuleDunderEmitTests(unittest.TestCase):
  def test_name_is_main_for_entry_module(self):
    out = _emit_expr("return __name__\n")
    self.assertIn("__main__", out)

  def test_file_is_py_path(self):
    out = _emit_expr("return __file__\n")
    self.assertIn("mod.py", out)

  def test_line_is_ast_lineno(self):
    src = "return __line__\n"
    tree = ast.parse(f"def f():\n  {src}")
    ret = tree.body[0].body[0].value  # type: ignore[union-attr]
    tr = Translator("mod", "mod.py")
    tr.entry_module_path = "mod"
    tr._parse_modules([("mod", "def f():\n  return __line__\n")])
    self.assertEqual(tr.visit(ret), str(ret.lineno))

  def test_debug_false_without_flag(self):
    out = _emit_expr("return __debug__\n", debug=False)
    self.assertEqual(out, "false")

  def test_debug_true_with_flag(self):
    out = _emit_expr("return __debug__\n", debug=True)
    self.assertEqual(out, "true")


if __name__ == "__main__":
  unittest.main()
