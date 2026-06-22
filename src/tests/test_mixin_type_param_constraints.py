"""``propagate_mixin_type_param_constraints``：混入泛型约束并入宿主。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.ir import ClassInfo
from src.passes.mixins import expand_mixins, is_mixin_class
from src.translator import Translator


def _parse_classes(src: str, module: str = "mod") -> dict[str, ClassInfo]:
  mod = ast.parse(src)
  out: dict[str, ClassInfo] = {}
  for node in mod.body:
    if isinstance(node, ast.ClassDef):
      info = ClassInfo(node, module)
      info.is_mixin = is_mixin_class(info)
      out[node.name] = info
  return out


class MixinTypeParamConstraintTests(unittest.TestCase):
  def test_mixin_protocol_constraint_merged_into_host(self):
    src = """
from py2cpp import mixin

@mixin
class ElemMixin[T: DictKey]:
  pass

class Box[T](ElemMixin[T]):
  x: int = 0
"""
    tr = Translator("mod", "mod.py")
    tr.classes = _parse_classes(src)
    expand_mixins(tr)
    host = tr.classes["Box"]
    self.assertEqual(host.type_param_constraints.get("T"), ("DictKey",))

  def test_mixin_multi_param_constraint_maps_to_host(self):
    src = """
from py2cpp import mixin

@mixin
class PairMixin[A, B: DictKey]:
  pass

class Container[A, B: DictKey](PairMixin[A, B]):
  pass
"""
    tr = Translator("mod", "mod.py")
    tr.classes = _parse_classes(src)
    expand_mixins(tr)
    host = tr.classes["Container"]
    self.assertEqual(host.type_param_constraints.get("B"), ("DictKey",))


if __name__ == "__main__":
  unittest.main()
