"""``import`` / ``from … import``（绝对、相对、``*``、属性链）回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from .helper import getImportValue


class RelativeImportTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(getImportValue(), 42)


class StdlibFromImportTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    xs: list[int] = [1, 2, 3]
    self.assertEqual(len(xs), 3)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
