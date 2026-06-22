"""``expand_descriptors``：``T @Desc(...) = default`` 与 ``__get__``/``__set__`` 形参校验。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.ir import ClassInfo
from src.passes.descriptors import (
  LEGACY_DESCRIPTOR_ASSIGN_MSG,
  _validate_descriptor_method_signature,
  expand_descriptors,
)
from src.translator import Translator


class DescriptorPassTests(unittest.TestCase):
  def test_extra_get_param_raises(self):
    get_m = ast.FunctionDef(
      name="__get__",
      args=ast.arguments(
        posonlyargs=[],
        args=[ast.arg(arg="self"), ast.arg(arg="owner")],
        kwonlyargs=[],
        kw_defaults=[],
        defaults=[],
      ),
      body=[ast.Pass()],
      decorator_list=[],
    )
    with self.assertRaises(ValueError) as ctx:
      _validate_descriptor_method_signature("D", get_m)
    self.assertIn("owner", str(ctx.exception))

  def test_legacy_rhs_assign_raises(self):
    src = """
from py2cpp import descriptor

@descriptor
class D:
  def __get__(self):
    ...
  def __set__(self, value: int):
    ...

class Host:
  x: int = D()
"""
    tree = ast.parse(src)
    tr = Translator.__new__(Translator)
    tr.classes = {}
    for node in tree.body:
      if isinstance(node, ast.ClassDef):
        tr.classes[node.name] = ClassInfo(node, module_path="mod")
    with self.assertRaises(ValueError) as ctx:
      expand_descriptors(tr)
    self.assertIn("等号右侧", str(ctx.exception))

  def test_matmult_field_inlines(self):
    src = '''
from py2cpp import descriptor

@descriptor
class D:
  def __get__(self):
    ...
  def __set__(self, value: int):
    ...

class Host:
  x: int @D() = 7
'''
    tree = ast.parse(src)
    tr = Translator.__new__(Translator)
    tr.classes = {}
    for node in tree.body:
      if isinstance(node, ast.ClassDef):
        tr.classes[node.name] = ClassInfo(node, module_path="mod")
    expand_descriptors(tr)
    host = tr.classes["Host"]
    self.assertIn("x", host.properties)
    self.assertIn("x__value", host.fields)
    self.assertEqual(host.field_defaults.get("x__value").value, 7)
    self.assertEqual([a.arg for a in host.properties["x"].getter.args.args], ["self"])

  def test_generic_descriptor_substitutes_value_type(self):
    src = """
from py2cpp import descriptor
from py2cpp.core.protocols import Comparable

@descriptor
class RangeVar[T: Comparable]:
  def __init__(self, lo: T, hi: T):
    self._lo = lo
    self._hi = hi
  def __get__(self):
    ...
  def __set__(self, value: T):
    if value < self._lo or value > self._hi:
      raise ValueError("out of range")
    self.__value__ = value

class Host:
  level: int @RangeVar(0, 10) = 0
"""
    tree = ast.parse(src)
    tr = Translator.__new__(Translator)
    tr.classes = {}
    for node in tree.body:
      if isinstance(node, ast.ClassDef):
        tr.classes[node.name] = ClassInfo(node, module_path="mod")
    expand_descriptors(tr)
    host = tr.classes["Host"]
    setter = host.properties["level"].setter
    value_arg = [a for a in setter.args.args if a.arg != "self"][0]
    self.assertIsInstance(value_arg.annotation, ast.Name)
    self.assertEqual(value_arg.annotation.id, "int")
    self.assertEqual(host.properties["level"].descriptor_protocol_bounds, ("Comparable",))


if __name__ == "__main__":
  unittest.main()
