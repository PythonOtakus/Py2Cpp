"""``__moved__`` 赋值移动语义（``test/lang/``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class ListMoveStateTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    a: list[int] = [1, 2]
    b: list[int] = a
    self.assertEqual(len(b), 2)
    self.assertTrue(a.__moved__)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
