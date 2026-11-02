"""宿主前端 API、MidIR 物化、冲突检测（无全文 rewrite）。"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from src.analysis.import_resolver import ModulePathConflictError, _pick_source_file
from src.frontend.api import Dialect, clear_parse_cache, parse_module
from src.frontend.dialect import dialect_from_path


def _deco_names(node: ast.ClassDef) -> list[str]:
  out: list[str] = []
  for d in node.decorator_list:
    if isinstance(d, ast.Name):
      out.append(d.id)
    elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name):
      out.append(d.func.id)
  return out


class FrontendApiTests(unittest.TestCase):
  def setUp(self) -> None:
    clear_parse_cache()

  def test_dialect_from_suffix(self) -> None:
    self.assertEqual(dialect_from_path("a.paw"), Dialect.PAW)
    self.assertEqual(dialect_from_path("a.py"), Dialect.LEGACY)
    self.assertEqual(dialect_from_path("a.pyi"), Dialect.LEGACY)

  def test_legacy_parse_roundtrip(self) -> None:
    src = "x: int = 1\n"
    parsed = parse_module(src, path="t.py", dialect=Dialect.LEGACY)
    self.assertIsInstance(parsed.tree, ast.Module)
    self.assertEqual(len(parsed.tree.body), 1)

  def test_paw_enum_ref_final_const_midir(self) -> None:
    src = (
      "enum Mode:\n"
      "  Off = 0\n"
      "  On = ...\n"
      "\n"
      "enum Flag(flag=True):\n"
      "  A = ...\n"
      "\n"
      "ref class Node:\n"
      "  value: int = 0\n"
      "\n"
      "final class Seal:\n"
      "  const MAX: int = 3\n"
    )
    parsed = parse_module(src, path="t.paw", dialect=Dialect.PAW)
    self.assertIsNotNone(parsed.mid)
    self.assertEqual(parsed.legacy_source, "")
    tree = parsed.tree
    by_name = {
      n.name: n for n in tree.body if isinstance(n, ast.ClassDef)
    }
    self.assertEqual(set(by_name), {"Mode", "Flag", "Node", "Seal"})
    self.assertIn("enum", _deco_names(by_name["Mode"]))
    self.assertIn("enum", _deco_names(by_name["Flag"]))
    self.assertIn("refcount", _deco_names(by_name["Node"]))
    self.assertIn("final", _deco_names(by_name["Seal"]))
    # const → AnnAssign with MatMult @const
    const_assigns = [
      s
      for s in by_name["Seal"].body
      if isinstance(s, ast.AnnAssign)
      and isinstance(s.target, ast.Name)
      and s.target.id == "MAX"
    ]
    self.assertEqual(len(const_assigns), 1)
    self.assertIsInstance(const_assigns[0].annotation, ast.BinOp)

  def test_paw_parse_module(self) -> None:
    src = "enum Mode:\n  Off = 0\n"
    parsed = parse_module(src, path="t.paw", dialect=Dialect.PAW)
    self.assertEqual(parsed.dialect, Dialect.PAW)
    self.assertTrue(any(isinstance(n, ast.ClassDef) for n in parsed.tree.body))
    self.assertIsNotNone(parsed.hir)

  def test_record_midir(self) -> None:
    src = "record Point:\n  x: int = 0\n"
    parsed = parse_module(src, path="t.paw", dialect=Dialect.PAW)
    point = next(n for n in parsed.tree.body if isinstance(n, ast.ClassDef))
    self.assertEqual(point.name, "Point")
    self.assertIn("dataclass", _deco_names(point))

  def test_module_path_conflict(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      d = Path(td)
      (d / "foo.py").write_text("x=1\n", encoding="utf-8")
      (d / "foo.paw").write_text("x=1\n", encoding="utf-8")
      with self.assertRaises(ModulePathConflictError):
        _pick_source_file(d, "foo")


if __name__ == "__main__":
  unittest.main()
