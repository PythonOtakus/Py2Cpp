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
    ft = _collect("def check(x: Comparable) -> int: ...")
    self.assertEqual(ft.template_names, ["__T0"])
    self.assertEqual(ft.constraints, {"__T0": "Comparable"})
    self.assertEqual(ft.arg_types, {"x": "__T0"})

  def test_protocol_subscript_with_type_param(self):
    ft = _collect("def enumerate[T](xs: Iterable[T], start: int = 0): ...")
    self.assertEqual(ft.template_names, ["T", "__T0"])
    self.assertEqual(
      ft.constraints,
      {"__T0": FuncTypeParametricBound("Iterable", "T")},
    )
    self.assertEqual(ft.arg_types, {"xs": "__T0"})

  def test_two_unannotated_params_distinct_templates(self):
    ft = _collect("def Compare(a, b) -> int: ...")
    self.assertEqual(ft.template_names, ["__T0", "__T1"])
    self.assertEqual(ft.arg_types, {"a": "__T0", "b": "__T1"})

  def test_pep695_unannotated_still_allocates_t0_t1(self):
    ft = _collect(
      "def zip[ItL: IteratorElement, ItR: IteratorElement](left, right): ..."
    )
    self.assertEqual(ft.template_names, ["ItL", "ItR", "__T0", "__T1"])
    self.assertEqual(
      ft.constraints,
      {"ItL": "IteratorElement", "ItR": "IteratorElement"},
    )
    self.assertEqual(ft.arg_types, {"left": "__T0", "right": "__T1"})

  def test_astar_node_only_header(self):
    ft = _collect(
      "def astar[Node: DictKey](nav: Navigatable[Node], start: Node, goal: Node) -> list[Node]: ..."
    )
    self.assertEqual(ft.template_names, ["Node", "__T0"])
    self.assertEqual(ft.arg_types["nav"], "__T0")
    self.assertEqual(ft.constraints["Node"], "DictKey")

  def test_pep695_protocol_bound_on_type_param(self):
    ft = _collect(
      "def astar[Nav: Navigatable[Node], Node: DictKey]"
      "(nav: Nav, start: Node, goal: Node) -> list[Node]: ..."
    )
    self.assertEqual(
      ft.constraints["Nav"],
      FuncTypeParametricBound("Navigatable", "Node"),
    )

  def test_navigatable_param_annotation_allocates_receiver(self):
    """``nav: Navigatable[Node]`` 新增接收者模板 ``__T0``（标准库推荐写法）。"""
    ft = _collect(
      "def astar[Node: DictKey]"
      "(nav: Navigatable[Node], start: Node, goal: Node) -> list[Node]: ..."
    )
    self.assertEqual(ft.template_names, ["Node", "__T0"])
    self.assertEqual(ft.arg_types["nav"], "__T0")
    self.assertEqual(
      ft.constraints["__T0"],
      FuncTypeParametricBound("Navigatable", "Node"),
    )
    self.assertEqual(ft.constraints["Node"], "DictKey")
    self.assertNotIn("Nav", ft.arg_types.values())

  def test_navigatable_concrete_assoc_no_header(self):
    """``nav: Navigatable[Cell]`` 无 PEP 695 头：``__T0`` + 具体 ``Cell``。"""
    ft = _collect(
      "def walk(nav: Navigatable[Cell], start: Cell, goal: Cell) -> list[Cell]: ..."
    )
    self.assertEqual(ft.template_names, ["__T0"])
    self.assertEqual(ft.arg_types["nav"], "__T0")
    self.assertEqual(
      ft.constraints["__T0"],
      FuncTypeParametricBound("Navigatable", "Cell"),
    )
    self.assertNotIn("Cell", ft.template_names)

  def test_iterable_concrete_int_assoc(self):
    """``xs: Iterable[int]``：``int`` 为具体元素类型，勿当作模板形参。"""
    ft = _collect("def total(xs: Iterable[int], start: int = 0) -> int: ...")
    self.assertEqual(ft.template_names, ["__T0"])
    self.assertEqual(
      ft.constraints["__T0"],
      FuncTypeParametricBound("Iterable", "PyInt"),
    )
    self.assertNotIn("int", ft.template_names)
    self.assertNotIn("PyInt", ft.template_names)

  def test_two_iterable_params_share_element_type(self):
    ft = _collect("def merge[T](a: Iterable[T], b: Iterable[T]) -> int: ...")
    self.assertEqual(ft.template_names, ["T", "__T0", "__T1"])
    self.assertEqual(ft.arg_types, {"a": "__T0", "b": "__T1"})
    self.assertEqual(
      ft.constraints["__T0"],
      FuncTypeParametricBound("Iterable", "T"),
    )
    self.assertEqual(
      ft.constraints["__T1"],
      FuncTypeParametricBound("Iterable", "T"),
    )

  def test_pep695_explicit_type_params_on_args(self):
    ft = _collect(
      "def zip[ItL: IteratorElement, ItR: IteratorElement]"
      "(left: ItL, right: ItR): ..."
    )
    self.assertEqual(ft.template_names, ["ItL", "ItR"])
    self.assertEqual(ft.arg_types, {})


if __name__ == "__main__":
  unittest.main()
