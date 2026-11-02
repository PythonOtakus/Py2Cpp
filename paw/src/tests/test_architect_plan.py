"""RefactorPlan 与 architect graph 单测。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.codegen.architect_graph import (
  ARCHITECT_GRAPH_FILE,
  ARCHITECT_GRAPH_VERSION,
  architect_cache_dir,
)
from src.tools.architect_plan import apply_plan, load_plan, validate_plan
from src.translator import Translator


_RENAME_FIELD_SRC = '''\
from py2cpp import dataclass

@dataclass
class Widget:
  score: int

  def bump(self) -> None:
    self.score = self.score + 1
'''


class ArchitectPlanTests(unittest.TestCase):
  def test_validate_rename_field_ok(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      mod = root / "widget_snip.py"
      mod.write_text(_RENAME_FIELD_SRC, encoding="utf-8")
      plan = {
        "version": 1,
        "id": "t1",
        "ops": [{
          "op": "rename_symbol",
          "kind": "field",
          "module": "widget_snip",
          "owner": "Widget",
          "from": "score",
          "to": "points",
        }],
      }
      self.assertEqual(validate_plan(plan, root), [])

  def test_rename_field_dry_run(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      mod = root / "widget_snip.py"
      mod.write_text(_RENAME_FIELD_SRC, encoding="utf-8")
      plan = {
        "version": 1,
        "id": "t2",
        "ops": [{
          "op": "rename_symbol",
          "kind": "field",
          "module": "widget_snip.py",
          "owner": "Widget",
          "from": "score",
          "to": "points",
        }],
      }
      result = apply_plan(plan, root, write=False)
      self.assertTrue(result.ok, result.errors)
      self.assertEqual(len(result.changes), 1)
      new_text = result.changes[0].new_text
      self.assertIn("points: int", new_text)
      self.assertIn("self.points", new_text)
      self.assertNotIn("self.score", new_text)
      self.assertEqual(mod.read_text(encoding="utf-8"), _RENAME_FIELD_SRC)

  def test_rename_method(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      src = '''\
class Box:
  def old_name(self) -> int:
    return 1

  def caller(self) -> int:
    return self.old_name()
'''
      mod = root / "box.py"
      mod.write_text(src, encoding="utf-8")
      plan = {
        "version": 1,
        "id": "t3",
        "ops": [{
          "op": "rename_symbol",
          "kind": "method",
          "module": "box",
          "owner": "Box",
          "from": "old_name",
          "to": "new_name",
        }],
      }
      result = apply_plan(plan, root, write=True)
      self.assertTrue(result.ok, result.errors)
      out = mod.read_text(encoding="utf-8")
      self.assertIn("def new_name", out)
      self.assertIn("self.new_name()", out)

  def test_reserved_name_rejected(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      mod = root / "x.py"
      mod.write_text("class C:\n  pass\n", encoding="utf-8")
      plan = {
        "version": 1,
        "id": "t4",
        "ops": [{
          "op": "rename_symbol",
          "kind": "field",
          "module": "x",
          "owner": "C",
          "from": "a",
          "to": "select",
        }],
      }
      errors = validate_plan(plan, root)
      self.assertTrue(any("保留名" in e for e in errors))

  def test_load_plan_from_file(self):
    with tempfile.TemporaryDirectory() as tmp:
      path = Path(tmp) / "plan.json"
      path.write_text('{"version": 1, "ops": []}', encoding="utf-8")
      data = load_plan(path)
      self.assertEqual(data["version"], 1)

  def test_update_select_path(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      pkg = root / "test_pkg"
      pkg.mkdir()
      mod = pkg / "use_sel.py"
      mod.write_text(
        '''\
class Team:
  members: list

  def hits(self) -> list:
    return self.members.select('.members{.score > 0}')
''',
        encoding="utf-8",
      )
      plan = {
        "version": 1,
        "id": "t5",
        "ops": [{
          "op": "update_select_path",
          "module": "test_pkg/use_sel",
          "from": ".members{.score > 0}",
          "to": ".members{.points > 0}",
        }],
      }
      result = apply_plan(plan, root, write=True)
      self.assertTrue(result.ok, result.errors)
      out = mod.read_text(encoding="utf-8")
      self.assertIn(".members{.points > 0}", out)
      self.assertNotIn(".score", out)

  def test_rename_field_updates_select_literals(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      py2cpp = root / "py2cpp"
      test_dir = root / "test"
      py2cpp.mkdir()
      test_dir.mkdir()
      owner = py2cpp / "widget.py"
      user = test_dir / "use_widget.py"
      owner.write_text(_RENAME_FIELD_SRC, encoding="utf-8")
      user.write_text(
        '''\
from py2cpp.widget import Widget

def pick(w: Widget) -> int:
  rows = w.select('.score')
  return rows[0]
''',
        encoding="utf-8",
      )
      plan = {
        "version": 1,
        "id": "t6",
        "ops": [{
          "op": "rename_symbol",
          "kind": "field",
          "module": "py2cpp/widget",
          "owner": "Widget",
          "from": "score",
          "to": "points",
          "update_select_literals": True,
        }],
      }
      result = apply_plan(plan, root, write=True)
      self.assertTrue(result.ok, result.errors)
      self.assertGreaterEqual(len(result.changes), 2)
      self.assertIn("points: int", owner.read_text(encoding="utf-8"))
      self.assertIn(".points", user.read_text(encoding="utf-8"))


class ArchitectGraphTests(unittest.TestCase):
  def test_graph_written_on_translate(self):
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "graph_snip.py"
      py.write_text(
        '''\
from py2cpp import *

@dataclass
class Item:
  value: int
''',
        encoding="utf-8",
      )
      Translator.translate_file(str(py), output_dir=str(out), include_stdlib=False)
      graph_path = architect_cache_dir(out) / ARCHITECT_GRAPH_FILE
      self.assertTrue(graph_path.is_file(), graph_path)
      graph = json.loads(graph_path.read_text(encoding="utf-8"))
      self.assertEqual(graph["version"], ARCHITECT_GRAPH_VERSION)
      self.assertIn("graph_snip", graph["modules"])
      entry = graph["modules"]["graph_snip"]
      self.assertIn("exports", entry)
      self.assertIn("imports", entry)
      self.assertIn("symbols", entry)
      self.assertIn("Item", entry["exports"])
      self.assertTrue(any(s.get("name") == "Item" for s in entry["symbols"]))
      item_cls = next(s for s in entry["symbols"] if s.get("name") == "Item")
      self.assertEqual(item_cls.get("role"), "dataclass")
      item_field = next(s for s in entry["symbols"] if s.get("name") == "value")
      self.assertEqual(item_field.get("typeAnn"), "int")
      self.assertIsInstance(graph.get("refs"), list)


if __name__ == "__main__":
  unittest.main()
