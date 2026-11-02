"""``__class_id__get`` 虚函数声明（仅当类含其它虚函数）。"""
import ast
import unittest

from src.analysis.ir import ClassInfo, FuncTypeParams, MethodSig
from src.emit.type_id_emit import type_id_class_id_decl_parts


class _TrStub:
  def __init__(self, classes: dict[str, ClassInfo]):
    self.classes = classes


def _info(name: str, bases: list[str], inject: bool = True, class_id: int = 1) -> ClassInfo:
  node = ast.ClassDef(name=name, bases=[ast.Name(id=b, ctx=ast.Load()) for b in bases], keywords=[], body=[ast.Pass()], decorator_list=[])
  info = ClassInfo(node, module_path="m")
  info.inject_type_id = inject
  info.class_id = class_id if inject else None
  info.bases = list(bases)
  return info


def _mark_virtual(info: ClassInfo) -> None:
  ft = FuncTypeParams([], None, {}, {})
  info.method_sigs["test"] = MethodSig(
    ft, "void", "", "", "", {}, (), False, "", is_virtual=True,
  )


class TestTypeIdEmit(unittest.TestCase):
  def test_exception_virtual_class_id(self):
    exc = _info("Exception", [])
    _mark_virtual(exc)
    tr = _TrStub({"Exception": exc})
    prefix, suffix = type_id_class_id_decl_parts(tr, exc)
    self.assertEqual(prefix, "virtual ")
    self.assertEqual(suffix, "")

  def test_exception_derived_override(self):
    exc = _info("Exception", [], class_id=1)
    _mark_virtual(exc)
    key = _info("KeyError", ["Exception"], class_id=4)
    tr = _TrStub({"Exception": exc, "KeyError": key})
    prefix, suffix = type_id_class_id_decl_parts(tr, key)
    self.assertEqual(prefix, "")
    self.assertEqual(suffix, " override")

  def test_derived_without_virtual_methods(self):
    exc = _info("Exception", [], class_id=1)
    key = _info("KeyError", ["Exception"], class_id=4)
    tr = _TrStub({"Exception": exc, "KeyError": key})
    prefix, suffix = type_id_class_id_decl_parts(tr, key)
    self.assertEqual(prefix, "")
    self.assertEqual(suffix, "")

  def test_virtual_root(self):
    exc = _info("TestCase", [])
    _mark_virtual(exc)
    tr = _TrStub({"TestCase": exc})
    prefix, suffix = type_id_class_id_decl_parts(tr, exc)
    self.assertEqual(prefix, "virtual ")
    self.assertEqual(suffix, "")

  def test_virtual_derived_override(self):
    base = _info("TestCase", [], class_id=1)
    _mark_virtual(base)
    derived = _info("MyTests", ["TestCase"], class_id=2)
    _mark_virtual(derived)
    tr = _TrStub({"TestCase": base, "MyTests": derived})
    prefix, suffix = type_id_class_id_decl_parts(tr, derived)
    self.assertEqual(prefix, "")
    self.assertEqual(suffix, " override")

  def test_derived_without_virtual_inherits_override(self):
    base = _info("TestCase", [], class_id=1)
    _mark_virtual(base)
    derived = _info("Plain", ["TestCase"], class_id=2)
    tr = _TrStub({"TestCase": base, "Plain": derived})
    prefix, suffix = type_id_class_id_decl_parts(tr, derived)
    self.assertEqual(prefix, "")
    self.assertEqual(suffix, " override")


if __name__ == "__main__":
  unittest.main()
