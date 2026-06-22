"""映射字面量链式查表：``{k:v}[i]``、``{k:v}.get(i, default)``。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class DictLiteralSubscriptTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual({1: 10, 2: 20}[1], 10)
    self.assertEqual({1: 10, 2: 20}[2], 20)
    k: int = 2
    self.assertEqual({1: 10, 2: 20}[k], 20)


class DictLiteralGetTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    self.assertEqual({1: 10, 2: 20}.get(1, -1), 10)
    self.assertEqual({1: 10, 2: 20}.get(9, -1), -1)
    k: int = 2
    self.assertEqual({1: 10, 2: 20}.get(k, 0), 20)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
