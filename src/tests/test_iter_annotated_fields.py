"""``Self.iter_fields`` 混入展开：``@Ann`` 容器类 / 字段 ``@Ann``。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.ir import ClassInfo
from src.passes.mixins import (
  annotated_fields,
  expand_iter_fields_subscript_loop,
  is_mixin_class,
)


class TestIterAnnotatedFields(unittest.TestCase):
  def test_annotated_fields_by_container_class(self):
    src = '''
@ComponentTableMeta
class Table:
  pass

class World:
  position: Table[Position] @property = new()
  other: int = 0
'''
    mod = ast.parse(src)
    table = ClassInfo(mod.body[0])
    world = ClassInfo(mod.body[1])
    world.field_types["__ann__position"] = ast.parse("Table[Position]", mode="eval").body
    world.field_types["position"] = world.field_types["__ann__position"]
    world.fields = ["position", "other"]
    classes = {"Table": table, "World": world}
    self.assertEqual(annotated_fields(world, "ComponentTableMeta", classes), ["position"])

  def test_expand_destroy_loop(self):
    mixin_src = '''
@mixin
class Mixin:
  def destroy(self, e: int):
    for field in Self.iter_fields[ComponentTableMeta]():
      x = getattr(self, field)
'''
    host_src = '''
@ComponentTableMeta
class Table:
  pass

class Host(Mixin):
  position: Table[Position] @property = new()
  velocity: Table[Velocity] @property = new()
'''
    mod = ast.parse(mixin_src + host_src)
    mixin = ClassInfo(mod.body[0])
    mixin.is_mixin = is_mixin_class(mixin)
    table = ClassInfo(mod.body[1])
    host = ClassInfo(mod.body[2])
    host.bases = ["Mixin"]
    host.fields = ["position", "velocity"]
    for fname, ann_src in (
      ("position", "Table[Position]"),
      ("velocity", "Table[Velocity]"),
    ):
      ann = ast.parse(ann_src, mode="eval").body
      host.field_types[fname] = ann
      host.field_types[f"__ann__{fname}"] = ann
    classes = {
      "Mixin": mixin,
      "Table": table,
      "Host": host,
    }
    method = mixin.methods["destroy"]
    expanded = expand_iter_fields_subscript_loop(method, host, classes)
    self.assertIsNotNone(expanded)
    assert expanded is not None
    self.assertEqual(len(expanded.body), 2)
    for stmt in expanded.body:
      self.assertIsInstance(stmt, ast.Assign)


if __name__ == "__main__":
  unittest.main()
