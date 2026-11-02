"""``load_stdlib_exception_types`` 与 ``exceptions.py`` 一致。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from src.analysis.stubs.class_stubs import load_stdlib_exception_types
from src.analysis.runtime_symbols import CPP_EXCEPTION_TYPES

_REPO = Path(__file__).resolve().parents[2]
_EXCEPTIONS_PY = _REPO / "py2cpp" / "core" / "exceptions.py"


class ExceptionStubTests(unittest.TestCase):
  def test_matches_exceptions_module(self):
    tree = ast.parse(_EXCEPTIONS_PY.read_text(encoding="utf-8"))
    expected = frozenset(
      node.name for node in tree.body if isinstance(node, ast.ClassDef)
    )
    self.assertEqual(load_stdlib_exception_types(), expected)
    self.assertEqual(CPP_EXCEPTION_TYPES, expected)

  def test_core_builtins_present(self):
    for name in (
      "IndexError",
      "KeyError",
      "ValueError",
      "AssertionError",
      "EOFError",
    ):
      self.assertIn(name, CPP_EXCEPTION_TYPES, msg=name)


if __name__ == "__main__":
  unittest.main()
