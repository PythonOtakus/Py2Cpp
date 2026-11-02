"""``expand_move_state``：剥除手写 ``__moved__`` 赋值。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.ir import ClassInfo
from src.passes.move_state import (
  MOVE_STATE_FIELD,
  _is_move_state_bool_assign,
  _strip_move_state_assigns,
  expand_move_state,
)
from src.translator import Translator


class MoveStatePassTests(unittest.TestCase):
  def test_strip_move_assigns(self):
    body = ast.parse(
      """def __move__(self, other):
  self.x = other.x
  self.__moved__ = False
  other.__moved__ = True
"""
    ).body[0].body  # type: ignore[attr-defined]
    stripped = _strip_move_state_assigns(body)
    self.assertEqual(len(stripped), 1)
    self.assertIsInstance(stripped[0], ast.Assign)

  def test_detect_legacy_moved(self):
    stmt = ast.parse("self.moved = True").body[0]
    self.assertTrue(_is_move_state_bool_assign(stmt))

  def test_expand_strips_init_and_move(self):
    src = """
class Box:
  def __init__(self):
    self.__moved__: bool = False
    self.v: int = 0
  def __move__(self, other: Box):
    self.v = other.v
    self.__moved__ = False
    other.__moved__ = True
"""
    mod = ast.parse(src)
    cls = mod.body[0]
    assert isinstance(cls, ast.ClassDef)
    info = ClassInfo(cls, "test/box")
    info.has_move = True
    for stmt in cls.body:
      if isinstance(stmt, ast.FunctionDef):
        if stmt.name == "__init__":
          info.inits.append(stmt)
          info.methods["__init__"] = stmt
        elif stmt.name == "__move__":
          info.methods["__move__"] = stmt
    tr = Translator("test/box", "test/box.py")
    tr.classes["Box"] = info
    expand_move_state(tr)
    init_body = info.inits[0].body
    self.assertFalse(
      any(
        isinstance(s, ast.AnnAssign)
        and isinstance(s.target, ast.Attribute)
        and s.target.attr == MOVE_STATE_FIELD
        for s in init_body
      )
    )
    move_body = info.methods["__move__"].body
    self.assertEqual(len(move_body), 1)
    self.assertIn(MOVE_STATE_FIELD, info.fields)


if __name__ == "__main__":
  unittest.main()
