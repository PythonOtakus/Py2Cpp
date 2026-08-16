"""``*args: T[:]`` 整包 ``PyArray<T>``：空调用、多实参、定参交错 ``*pack``、``*args`` 转发。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def sumVararg(*nums: int[:]) -> int:
  total: int = 0
  for x in nums:
    total += x
  return total


def headPlusCount(first: int, *rest: int[:]) -> int:
  return first + len(rest)


def packLen(*nums: int[:]) -> int:
  return len(nums)


def forwardAll(*nums: int[:]) -> int:
  return packLen(*nums)


def forwardWithHead(first: int, *rest: int[:]) -> int:
  return first + packLen(*rest)


def packSum(*nums: int[:]) -> int:
  total: int = 0
  for x in nums:
    total += x
  return total


def asPack(*nums: int[:]) -> int[:]:
  return nums


def interleavePacks(a: int[:], b: int[:]) -> int:
  return packSum(3, *a, 4, *b, 5)


def interleaveWithHead(first: int, *rest: int[:]) -> int:
  return packSum(first, *rest)


class VarargEmptyPackTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(sumVararg(), 0)


class VarargThreeValuesTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    self.assertEqual(sumVararg(1, 2, 3), 6)


class VarargHeadAndRestTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    self.assertEqual(headPlusCount(5, 1, 2), 7)


class VarargForwardWholePackTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    self.assertEqual(forwardAll(1, 2, 3), 3)


class VarargForwardWithHeadTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    self.assertEqual(forwardWithHead(10, 1, 2), 12)


class VarargInterleaveStarredPacksTests(TestCaseMixin):
  _testTag = 6

  @override
  def test(self):
    left: int[:] = asPack(1, 2)
    right: int[:] = asPack(7)
    self.assertEqual(interleavePacks(left, right), 22)


class VarargInterleaveScalarAndStarTests(TestCaseMixin):
  _testTag = 7

  @override
  def test(self):
    mid: int[:] = asPack(2, 3)
    self.assertEqual(interleaveWithHead(10, *mid, 4), 19)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
