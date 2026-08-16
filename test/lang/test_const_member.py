"""类体 ``name: T @const = v`` → ``static constexpr`` 成员。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Limits:
  Max: int @const = 100
  Min: int @const = 0


class ConstMemberTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(Limits.Max, 100)
    self.assertEqual(Limits.Min, 0)
    self.assertTrue(Limits.Max > Limits.Min)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
