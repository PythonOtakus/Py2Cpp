"""``@overload``：同名方法多签名（用户类）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Scaler:
  base: int = 1

  @overload
  def scale(self) -> int:
    return self.base

  @overload
  def scale(self, factor: int) -> int:
    return self.base * factor


class OverloadMethodTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    s: Scaler = new()
    self.assertEqual(s.scale(), 1)
    self.assertEqual(s.scale(7), 7)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
