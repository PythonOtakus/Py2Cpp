"""列表字面量链式查表：``[a,b,c][i]``、``x in {a,b,c}``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class ListLiteralSubscriptTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual([10, 20, 30][0], 10)
    self.assertEqual([10, 20, 30][2], 30)
    i: int = 1
    self.assertEqual([1, 2, 3][i], 2)


class SetLiteralMemberTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    self.assertTrue(2 in {1, 2, 3})
    self.assertFalse(9 in {1, 2, 3})


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
