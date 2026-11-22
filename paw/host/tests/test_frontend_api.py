"""宿主前端 API、MidIR 空树、冲突检测（无 LEGACY / ast.parse）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from host.analysis.import_resolver import ModulePathConflictError, _pick_source_file
from host.frontend.api import Dialect, clear_parse_cache, parse_module
from host.frontend.dialect import dialect_from_path


class FrontendApiTests(unittest.TestCase):
  def setUp(self) -> None:
    clear_parse_cache()

  def test_dialect_from_suffix(self) -> None:
    self.assertEqual(dialect_from_path("a.paw"), Dialect.PAW)
    self.assertEqual(dialect_from_path("a.py"), Dialect.PAW)
    self.assertEqual(dialect_from_path("a.pyi"), Dialect.PAW)
    self.assertFalse(hasattr(Dialect, "LEGACY"))

  def test_py_suffix_uses_paw_not_ast_parse(self) -> None:
    """``.py`` 走 Paw；简单 Paw 可接受源可解析且空 tree。"""
    src = "x: int = 1\n"
    parsed = parse_module(src, path="t.py", dialect=Dialect.PAW)
    self.assertEqual(parsed.dialect, Dialect.PAW)
    self.assertEqual(parsed.tree.body, [])
    self.assertIsNotNone(parsed.mid)
    self.assertTrue(any("兼容后缀" in d for d in parsed.diagnostics))

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
    self.assertEqual(parsed.tree.body, [])
    from compiler.py.mid.nodes import MidClass, MidEnum

    by_name = {
      it.name: it
      for it in parsed.mid.items
      if isinstance(it, (MidClass, MidEnum))
    }
    self.assertEqual(set(by_name), {"Mode", "Flag", "Node", "Seal"})
    from compiler.py.frontend.syntax_nodes import ObjectModel

    self.assertTrue(isinstance(by_name["Mode"], MidEnum))
    self.assertTrue(by_name["Flag"].flag)
    self.assertIs(by_name["Node"].object_model, ObjectModel.REF_COUNT)
    self.assertTrue(by_name["Seal"].is_final)

  def test_paw_parse_module(self) -> None:
    src = "enum Mode:\n  Off = 0\n"
    parsed = parse_module(src, path="t.paw", dialect=Dialect.PAW)
    self.assertEqual(parsed.dialect, Dialect.PAW)
    self.assertEqual(parsed.tree.body, [])
    self.assertIsNotNone(parsed.hir)
    self.assertIsNotNone(parsed.mid)

  def test_record_midir(self) -> None:
    src = "record Point:\n  x: int = 0\n"
    parsed = parse_module(src, path="t.paw", dialect=Dialect.PAW)
    self.assertIsNotNone(parsed.mid)
    from compiler.py.mid.nodes import MidClass

    point = next(it for it in parsed.mid.items if isinstance(it, MidClass))
    self.assertEqual(point.name, "Point")
    self.assertTrue(point.is_record)

  def test_module_path_conflict(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      d = Path(td)
      (d / "foo.py").write_text("x=1\n", encoding="utf-8")
      (d / "foo.paw").write_text("x=1\n", encoding="utf-8")
      with self.assertRaises(ModulePathConflictError):
        _pick_source_file(d, "foo")


if __name__ == "__main__":
  unittest.main()
