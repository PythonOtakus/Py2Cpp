"""``FuncTypeParams``：``@protocol`` 形参注解与 PEP 695 模板形参映射。"""
from __future__ import annotations

import ast
import unittest

from src.analysis.ir import FuncTypeParametricBound, FuncTypeParams


def _collect(src: str) -> FuncTypeParams:
  tree = ast.parse(src)
  func = tree.body[0]
  assert isinstance(func, ast.FunctionDef)
  return FuncTypeParams.collect(func)


class FuncTypeParamsProtocolTests(unittest.TestCase):
  def test_bare_protocol_annotation(self):
    ft = _collect("def check(x: ComparableType) -> int: ...")
    self.assertEqual(ft.template_names, ["__T0"])
    self.assertEqual(ft.constraints, {"__T0": "ComparableType"})
    self.assertEqual(ft.arg_types, {"x": "__T0"})

  def test_protocol_subscript_with_type_param(self):
    ft = _collect("def enumerate[T](xs: IterableType[T], start: int = 0): ...")
    self.assertEqual(ft.template_names, ["T", "__T0"])
    self.assertEqual(
      ft.constraints,
      {"__T0": FuncTypeParametricBound("IterableType", "T")},
    )
    self.assertEqual(ft.arg_types, {"xs": "__T0"})

  def test_two_unannotated_params_distinct_templates(self):
    ft = _collect("def Compare(a, b) -> int: ...")
    self.assertEqual(ft.template_names, ["__T0", "__T1"])
    self.assertEqual(ft.arg_types, {"a": "__T0", "b": "__T1"})

  def test_pep695_unannotated_still_allocates_t0_t1(self):
    ft = _collect(
      "def zip[ItL: IteratorElementType, ItR: IteratorElementType](left, right): ..."
    )
    self.assertEqual(ft.template_names, ["ItL", "ItR", "__T0", "__T1"])
    self.assertEqual(
      ft.constraints,
      {"ItL": "IteratorElementType", "ItR": "IteratorElementType"},
    )
    self.assertEqual(ft.arg_types, {"left": "__T0", "right": "__T1"})

  def test_astar_node_only_header(self):
    ft = _collect(
      "def astar[Node: DictKeyType](nav: NavigatableType[Node], start: Node, goal: Node) -> list[Node]: ..."
    )
    self.assertEqual(ft.template_names, ["Node", "__T0"])
    self.assertEqual(ft.arg_types["nav"], "__T0")
    self.assertEqual(ft.constraints["Node"], "DictKeyType")

  def test_pep695_protocol_bound_on_type_param(self):
    ft = _collect(
      "def astar[Nav: NavigatableType[Node], Node: DictKeyType]"
      "(nav: Nav, start: Node, goal: Node) -> list[Node]: ..."
    )
    self.assertEqual(
      ft.constraints["Nav"],
      FuncTypeParametricBound("NavigatableType", "Node"),
    )

  def test_navigatable_param_annotation_allocates_receiver(self):
    """``nav: NavigatableType[Node]`` 新增接收者模板 ``__T0``（标准库推荐写法）。"""
    ft = _collect(
      "def astar[Node: DictKeyType]"
      "(nav: NavigatableType[Node], start: Node, goal: Node) -> list[Node]: ..."
    )
    self.assertEqual(ft.template_names, ["Node", "__T0"])
    self.assertEqual(ft.arg_types["nav"], "__T0")
    self.assertEqual(
      ft.constraints["__T0"],
      FuncTypeParametricBound("NavigatableType", "Node"),
    )
    self.assertEqual(ft.constraints["Node"], "DictKeyType")
    self.assertNotIn("Nav", ft.arg_types.values())

  def test_navigatable_concrete_assoc_no_header(self):
    """``nav: NavigatableType[Cell]`` 无 PEP 695 头：``__T0`` + 具体 ``Cell``。"""
    ft = _collect(
      "def walk(nav: NavigatableType[Cell], start: Cell, goal: Cell) -> list[Cell]: ..."
    )
    self.assertEqual(ft.template_names, ["__T0"])
    self.assertEqual(ft.arg_types["nav"], "__T0")
    self.assertEqual(
      ft.constraints["__T0"],
      FuncTypeParametricBound("NavigatableType", "Cell"),
    )
    self.assertNotIn("Cell", ft.template_names)

  def test_iterable_concrete_int_assoc(self):
    """``xs: IterableType[int]``：``int`` 为具体元素类型，勿当作模板形参。"""
    ft = _collect("def total(xs: IterableType[int], start: int = 0) -> int: ...")
    self.assertEqual(ft.template_names, ["__T0"])
    self.assertEqual(
      ft.constraints["__T0"],
      FuncTypeParametricBound("IterableType", "PyInt"),
    )
    self.assertNotIn("int", ft.template_names)
    self.assertNotIn("PyInt", ft.template_names)

  def test_two_iterable_params_share_element_type(self):
    ft = _collect("def merge[T](a: IterableType[T], b: IterableType[T]) -> int: ...")
    self.assertEqual(ft.template_names, ["T", "__T0", "__T1"])
    self.assertEqual(ft.arg_types, {"a": "__T0", "b": "__T1"})
    self.assertEqual(
      ft.constraints["__T0"],
      FuncTypeParametricBound("IterableType", "T"),
    )
    self.assertEqual(
      ft.constraints["__T1"],
      FuncTypeParametricBound("IterableType", "T"),
    )

  def test_pep695_explicit_type_params_on_args(self):
    ft = _collect(
      "def zip[ItL: IteratorElementType, ItR: IteratorElementType]"
      "(left: ItL, right: ItR): ..."
    )
    self.assertEqual(ft.template_names, ["ItL", "ItR"])
    self.assertEqual(ft.arg_types, {})


if __name__ == "__main__":
  unittest.main()
