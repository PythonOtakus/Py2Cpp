"""类体 ``name: T @const = v`` → ``static constexpr`` 成员。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Limits:
  MAX: int @const = 100
  MIN: int @const = 0


class ConstMemberTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Limits.MAX, 100)
    self.assertEqual(Limits.MIN, 0)
    self.assertTrue(Limits.MAX > Limits.MIN)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
