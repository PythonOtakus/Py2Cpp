"""``expand_class_type_base``：``__base__`` 注入与实体基类解析。"""
import ast
import unittest

from src.analysis.ir import ClassInfo, class_base_name
from src.passes.class_type_base import _entity_base_ast, expand_class_type_base
from src.passes.mixins import is_mixin_class


def _parse_class(src: str) -> ast.ClassDef:
  return ast.parse(src).body[0]  # type: ignore[return-value]


def _mixin_info(name: str, bases: list[str] | None = None) -> ClassInfo:
  b = bases or []
  node = ast.ClassDef(
    name=name,
    bases=[ast.Name(id=x, ctx=ast.Load()) for x in b],
    keywords=[],
    body=[ast.Pass()],
    decorator_list=[ast.Name(id="mixin", ctx=ast.Load())],
  )
  info = ClassInfo(node, module_path="m")
  info.is_mixin = is_mixin_class(info)
  return info


class _TrStub:
  def __init__(self, classes: dict[str, ClassInfo]):
    self.classes = classes
    self.module_order = ["m"]
    self.module_asts = {"m": ast.Module(body=[c.node for c in classes.values()], type_ignores=[])}


class TestClassTypeBase(unittest.TestCase):
  def test_explicit_entity_with_mixin(self):
    base = ClassInfo(_parse_class("class Base: pass"), "m")
    mixin = _mixin_info("IncMixin")
    host_node = _parse_class("class Host(IncMixin, Base): pass")
    host = ClassInfo(host_node, "m")
    tr = _TrStub({"Base": base, "IncMixin": mixin, "Host": host})
    host.bases = ["IncMixin", "Base"]
    ast_obj = _entity_base_ast(host, tr)
    self.assertEqual(class_base_name(ast_obj), "Base")

  def test_mixin_carrier_entity(self):
    testcase = ClassInfo(_parse_class("class TestCase: pass"), "m")
    mixin = _mixin_info("TestCaseMixin", ["TestCase"])
    host_node = _parse_class("class Host(TestCaseMixin): pass")
    host = ClassInfo(host_node, "m")
    tr = _TrStub({"TestCase": testcase, "TestCaseMixin": mixin, "Host": host})
    host.bases = ["TestCaseMixin", "TestCase"]
    ast_obj = _entity_base_ast(host, tr)
    self.assertEqual(class_base_name(ast_obj), "TestCase")

  def test_root_void(self):
    root = ClassInfo(_parse_class("class Root: pass"), "m")
    tr = _TrStub({"Root": root})
    root.bases = []
    self.assertIsNone(_entity_base_ast(root, tr))
    expand_class_type_base(tr)  # type: ignore[arg-type]
    alias = root.type_aliases["__base__"]
    self.assertIsInstance(alias.value, ast.Name)
    self.assertEqual(alias.value.id, "void")

  def test_generic_entity_base_ast(self):
    container_node = _parse_class("class Container[T]: pass")
    container = ClassInfo(container_node, "m")
    box_node = ast.parse("class Box[T](Container[T]): pass").body[0]
    box = ClassInfo(box_node, "m")
    tr = _TrStub({"Container": container, "Box": box})
    box.bases = ["Container"]
    ast_obj = _entity_base_ast(box, tr)
    self.assertIsInstance(ast_obj, ast.Subscript)
    self.assertEqual(class_base_name(ast_obj), "Container")


if __name__ == "__main__":
  unittest.main()
