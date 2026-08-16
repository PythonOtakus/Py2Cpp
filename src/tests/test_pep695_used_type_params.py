"""``pep695_used_type_params``：未使用形参检测辅助。"""
import ast
import unittest

from src.analysis.ir import pep695_declared_type_params, pep695_used_type_params


class Pep695UsedTypeParamsTests(unittest.TestCase):
  def test_navigatable_header_node_only(self):
    mod = ast.parse(
      "def f[Node: DictKeyType](nav: NavigatableType[Node], start: Node) -> Node: return start\n"
    )
    fn = mod.body[0]
    declared = frozenset(pep695_declared_type_params(fn))
    self.assertEqual(declared, frozenset({"Node"}))
    used = pep695_used_type_params(fn, declared)
    self.assertEqual(used, {"Node"})

  def test_unused_nav_in_header(self):
    mod = ast.parse(
      "def f[Nav, Node: DictKeyType](nav: NavigatableType[Node], start: Node) -> Node: return start\n"
    )
    fn = mod.body[0]
    declared = frozenset(pep695_declared_type_params(fn))
    used = pep695_used_type_params(fn, declared)
    self.assertIn("Node", used)
    self.assertNotIn("Nav", used)


if __name__ == "__main__":
  unittest.main()
