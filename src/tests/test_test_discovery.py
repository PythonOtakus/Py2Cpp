"""``expand_test_discovery``：入口 ``main`` 内测试类自动注入。"""
from __future__ import annotations

import ast
import unittest

from src.passes.test_discovery import (
  _expand_main_body,
  _parse_add_test_from_class_loop,
  collect_ordered_mixin_hosts,
  sort_mixin_hosts,
)
from src.translator import Translator


class _FakeTr:
  entry_module_path = "mod"
  module_asts: dict
  classes: dict


def _parse_main(code: str) -> ast.FunctionDef:
  tree = ast.parse(code)
  for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == "main":
      return node
  raise AssertionError("no main")


class TestDiscoveryPass(unittest.TestCase):
  def test_collect_hosts_in_source_order(self):
    code = '''
class Alpha(TestCaseMixin):
  @override
  def test(self): pass
class Beta(TestCaseMixin):
  @override
  def test(self): pass
class Gamma(TestCase):
  @override
  def test(self): pass
'''
    tr = Translator("mod", "mod.py")
    tr.entry_module_path = "mod"
    tr._parse_modules([("mod", code)])
    from src.passes.mixins import expand_mixins

    expand_mixins(tr)
    names = collect_ordered_mixin_hosts(tr, "mod", "TestCaseMixin")
    self.assertEqual(names, ["Alpha", "Beta"])

  def test_expand_iter_subclasses_loop(self):
    main_src = '''
def main():
  suite: TestSuite = TestSuite()
  for Cls in TestCaseMixin.iterSubclasses():
    suite.addTest(Cls())
  return TextTestRunner().run(suite)
'''
    body_code = '''
class A(TestCaseMixin):
  @override
  def test(self): pass
class B(TestCaseMixin):
  @override
  def test(self): pass
''' + main_src
    tr = Translator("mod", "mod.py")
    tr.entry_module_path = "mod"
    tr._parse_modules([("mod", body_code)])
    from src.passes.mixins import expand_mixins

    expand_mixins(tr)
    main_fn = _parse_main(body_code)
    tr.module_functions.append(("mod", main_fn))
    expanded = _expand_main_body(tr, main_fn.body)
    adds = [
      s.value.args[0].func.id  # type: ignore[union-attr]
      for s in expanded
      if isinstance(s, ast.Expr)
      and isinstance(s.value, ast.Call)
      and isinstance(s.value.func, ast.Attribute)
      and s.value.func.attr == "addTest"
    ]
    self.assertEqual(adds, ["A", "B"])

  def test_parse_loop_pattern(self):
    loop = ast.parse(
      "for Cls in TestCaseMixin.iterSubclasses():\n"
      "  suite.addTest(Cls())\n"
    ).body[0]
    assert isinstance(loop, ast.For)
    parsed = _parse_add_test_from_class_loop(loop)
    self.assertEqual(parsed, ("suite", "Cls", "TestCaseMixin", None))

  def test_sort_hosts_by_test_tag(self):
    code = '''
class Z(TestCaseMixin):
  _testTag = 90
  @override
  def test(self): pass
class A(TestCaseMixin):
  _testTag = 1
  @override
  def test(self): pass
class M(TestCaseMixin):
  _testTag = 50
  @override
  def test(self): pass
'''
    tr = Translator("mod", "mod.py")
    tr.entry_module_path = "mod"
    tr._parse_modules([("mod", code)])
    from src.passes.mixins import expand_mixins

    expand_mixins(tr)
    hosts = collect_ordered_mixin_hosts(tr, "mod", "TestCaseMixin")
    self.assertEqual(sort_mixin_hosts(tr, hosts, "_testTag"), ["A", "M", "Z"])

  def test_expand_iter_subclasses_sort_const_loop(self):
    main_src = '''
def main():
  suite: TestSuite = TestSuite()
  for Cls in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Cls())
  return TextTestRunner().run(suite)
'''
    body_code = '''
class Late(TestCaseMixin):
  _testTag = 50
  @override
  def test(self): pass
class Early(TestCaseMixin):
  _testTag = 1
  @override
  def test(self): pass
''' + main_src
    tr = Translator("mod", "mod.py")
    tr.entry_module_path = "mod"
    tr._parse_modules([("mod", body_code)])
    from src.passes.mixins import expand_mixins

    expand_mixins(tr)
    main_fn = _parse_main(body_code)
    tr.module_functions.append(("mod", main_fn))
    expanded = _expand_main_body(tr, main_fn.body)
    adds = [
      s.value.args[0].func.id  # type: ignore[union-attr]
      for s in expanded
      if isinstance(s, ast.Expr)
      and isinstance(s.value, ast.Call)
      and isinstance(s.value.func, ast.Attribute)
      and s.value.func.attr == "addTest"
    ]
    self.assertEqual(adds, ["Early", "Late"])


if __name__ == "__main__":
  unittest.main()
