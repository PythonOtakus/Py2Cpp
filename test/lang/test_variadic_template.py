"""形参包：``*args: Ts`` / 无注解 ``*args``（独立 ``Args`` 包）、``len``、转发与 ``*PyTuple`` 交错。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def sumAll[*Ts](*args: Ts) -> int:
  total: int = 0
  for x in args:
    total += x
  return total


def headPlusCount[*Ts](first: int, *rest) -> int:
  return first + len(rest)


def packLen[*Ts](*args) -> int:
  return len(args)


def forwardAll[*Ts](*args: Ts) -> int:
  return sumAll(*args)


def viaTuple[*Ts](*args: Ts) -> int:
  t: (*Ts,) = args
  return sumAll(*t)


def interleaveScalarsAndTuple(a: (int, int), b: (int, int)) -> int:
  return sumAll(3, *a, 4, *b, 5)


class VariadicTemplateSumThreeTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(sumAll(1, 2, 3), 6)


class VariadicTemplateSumEmptyTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    self.assertEqual(sumAll(), 0)


class VariadicTemplateHeadRestTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    self.assertEqual(headPlusCount(10, 20, 30), 12)


class VariadicTemplatePackLenTests(TestCaseMixin):
  _testTag = 6

  @override
  def test(self):
    self.assertEqual(packLen(1, 2, 3), 3)
    self.assertEqual(packLen(), 0)


class VariadicTemplateForwardTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    self.assertEqual(forwardAll(1, 2), 3)


class VariadicTemplateViaTupleTests(TestCaseMixin):
  _testTag = 7

  @override
  def test(self):
    self.assertEqual(viaTuple(1, 2, 3), 6)


class VariadicTemplateInterleaveTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    a: (int, int) = (1, 2)
    b: (int, int) = (7, 8)
    self.assertEqual(interleaveScalarsAndTuple(a, b), 30)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
