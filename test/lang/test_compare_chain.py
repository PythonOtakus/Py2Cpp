"""链式比较 ``a < x < b``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def inOpenInterval(x: int) -> bool:
  return 1 < x < 10


def inClosedInterval(x: int) -> bool:
  return 1 <= x <= 10


class ChainCompareTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertTrue(inOpenInterval(5))
    self.assertFalse(inOpenInterval(1))
    self.assertFalse(inOpenInterval(10))
    self.assertTrue(inClosedInterval(1))
    self.assertTrue(inClosedInterval(10))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
