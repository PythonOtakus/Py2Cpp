"""``check_moved_use`` 翻译期检查。"""
from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from src.analysis.analyzer import SemanticAnalyzer
from src.analysis.import_resolver import discover_translation_modules
from src.passes.access import expand_member_access
from src.passes.copyable import expand_copyable
from src.passes.dataclass_expand import expand_dataclass
from src.passes.decorators import expand_decorators
from src.passes.descriptors import expand_descriptors
from src.passes.generators import expand_generators
from src.passes.kwargs_options import expand_kwargs_options
from src.passes.mixins import expand_mixins, expand_static_reflect
from src.passes.move_state import expand_move_state
from src.passes.moved_use_check import check_moved_use
from src.passes.protocol import expand_protocol
from src.translator import Translator


def _root() -> Path:
  return Path(__file__).resolve().parents[2]


def _analyze_body(body: str) -> Translator:
  root = _root()
  src = f"from py2cpp import *\n\n{body}"
  with tempfile.TemporaryDirectory() as tmp:
    project_root = Path(tmp)
    entry_py = project_root / "test_move_min.py"
    entry_py.write_text(src, encoding="utf-8")
    entry_mod = "test_move_min"
    modules = discover_translation_modules(
      entry_py,
      include_stdlib=True,
      runtime_root=root / "py2cpp",
      project_root=project_root,
    )
    tr = Translator("test_move_min", str(entry_py))
    tr.entry_module_path = entry_mod
    tr._import_project_root_cache = project_root
    tr._parse_modules(modules)
  expand_dataclass(tr)
  expand_descriptors(tr)
  expand_mixins(tr)
  expand_kwargs_options(tr)
  expand_static_reflect(tr)
  expand_generators(tr)
  expand_decorators(tr)
  expand_copyable(tr)
  expand_move_state(tr)
  expand_protocol(tr)
  expand_member_access(tr)
  SemanticAnalyzer().analyze(tr)
  return tr


_MOVE_ONLY_BOX = """class Box:
  def __init__(self):
    self.x: int = 0

  def __move__(self, other: Self):
    self.x = other.x
    other.x = 0

"""


class MovedUseCheckTests(unittest.TestCase):
  def test_allows_moved_flag(self):
    tr = _analyze_body(
      _MOVE_ONLY_BOX
      + """def main():
  a: Box = new()
  b: Box = a
  return a.__moved__
"""
    )
    check_moved_use(tr)

  def test_rejects_load_after_move(self):
    tr = _analyze_body(
      _MOVE_ONLY_BOX
      + """def main():
  a: Box = new()
  b: Box = a
  return a.x
"""
    )
    with self.assertRaises(ValueError) as ctx:
      check_moved_use(tr)
    self.assertIn("移动", str(ctx.exception))
    self.assertIn("`a`", str(ctx.exception))

  def test_reassign_clears_moved(self):
    tr = _analyze_body(
      _MOVE_ONLY_BOX
      + """def main():
  a: Box = new()
  b: Box = a
  a: Box = new()
  return a.x
"""
    )
    check_moved_use(tr)


if __name__ == "__main__":
  unittest.main()
