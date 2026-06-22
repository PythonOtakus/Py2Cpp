"""链式比较 ``a < x < b``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def in_open_interval(x: int) -> bool:
  return 1 < x < 10


def in_closed_interval(x: int) -> bool:
  return 1 <= x <= 10


class ChainCompareTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertTrue(in_open_interval(5))
    self.assertFalse(in_open_interval(1))
    self.assertFalse(in_open_interval(10))
    self.assertTrue(in_closed_interval(1))
    self.assertTrue(in_closed_interval(10))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
