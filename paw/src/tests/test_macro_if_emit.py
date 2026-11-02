"""``"NAME" in __macro__`` if 链 → C 预编译指令。"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from src.passes.macro_if import (
  collect_macro_if_chain,
  looks_like_macro_if_head,
  parse_macro_if_test,
)
from src.translator import Translator


class MacroIfParseTests(unittest.TestCase):
  def test_parses_in_and_not_in(self):
    self.assertEqual(
      parse_macro_if_test(ast.parse('"_WIN32" in __macro__', mode="eval").body),
      ("_WIN32", True),
    )
    self.assertEqual(
      parse_macro_if_test(ast.parse('"_WIN32" not in __macro__', mode="eval").body),
      ("_WIN32", False),
    )

  def test_rejects_not_name_in_macro(self):
    with self.assertRaises(ValueError) as ctx:
      parse_macro_if_test(ast.parse('not "_WIN32" in __macro__', mode="eval").body, loc="t")
    self.assertIn("not in __macro__", str(ctx.exception))

  def test_rejects_non_literal(self):
    with self.assertRaises(ValueError):
      parse_macro_if_test(ast.parse("name in __macro__", mode="eval").body, loc="t")

  def test_collects_elif_else_chain(self):
    src = """
if "_WIN32" in __macro__:
  x = 1
elif "__APPLE__" in __macro__:
  x = 2
elif "_WIN32" not in __macro__:
  x = 3
else:
  x = 0
"""
    tree = ast.parse(src)
    stmt = tree.body[0]
    assert isinstance(stmt, ast.If)
    self.assertTrue(looks_like_macro_if_head(stmt.test))
    chain = collect_macro_if_chain(stmt)
    self.assertEqual(len(chain.branches), 3)
    self.assertEqual(chain.branches[0].macro, "_WIN32")
    self.assertTrue(chain.branches[0].positive)
    self.assertEqual(chain.branches[2].macro, "_WIN32")
    self.assertFalse(chain.branches[2].positive)
    self.assertIsNotNone(chain.else_body)

  def test_rejects_mixed_elif(self):
    src = """
if "_WIN32" in __macro__:
  x = 1
elif True:
  x = 2
"""
    tree = ast.parse(src)
    stmt = tree.body[0]
    assert isinstance(stmt, ast.If)
    with self.assertRaises(ValueError):
      collect_macro_if_chain(stmt)


class MacroIfEmitTests(unittest.TestCase):
  def test_emits_preprocessor_chain(self):
    src = """
def pick() -> int:
  if "_WIN32" in __macro__:
    return 1
  elif "_WIN32" not in __macro__:
    return 0
  else:
    return -1
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("#ifdef _WIN32", cpp)
      self.assertIn("#elif !defined(_WIN32)", cpp)
      self.assertIn("#else", cpp)
      self.assertIn("#endif", cpp)
      self.assertNotIn("__macro__", cpp)

  def test_nested_macro_if_in_branch(self):
    src = """
def f() -> int:
  if "_WIN32" in __macro__:
    if "NDEBUG" in __macro__:
      return 1
    return 2
  else:
    return 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("#ifdef _WIN32", cpp)
      self.assertIn("#ifdef NDEBUG", cpp)
      self.assertEqual(cpp.count("#endif"), 2)


if __name__ == "__main__":
  unittest.main()
