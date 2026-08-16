"""``for`` / ``while`` 的 ``else``（无用户 ``break`` 时执行）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def forElseSum() -> int:
  acc: int = 0
  for i in range(3):
    acc += i
  else:
    acc += 100
  return acc


def forElseSkipOnBreak() -> int:
  acc: int = 0
  for i in range(10):
    if i == 2:
      break
    acc += i
  else:
    acc += 100
  return acc


def whileElseCount() -> int:
  acc: int = 0
  for n in range(3, 0, -1):
    acc += 1
  else:
    acc += 10
  return acc


class ForElseTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(forElseSum(), 103)
    self.assertEqual(forElseSkipOnBreak(), 1)


class WhileElseTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    self.assertEqual(whileElseCount(), 13)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
