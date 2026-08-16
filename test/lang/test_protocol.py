from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
"""``@protocol`` 约束：``ComparableType`` / ``ArithmeticType`` / ``numbers`` 塔（应编译通过）。"""


def sorted[T: ComparableType](s: list[T]) -> list[T]:
  out: list[T] = []
  out.extend(s)
  out.sort()
  return out


def half[T: ArithmeticType](x: T) -> float:
  return x / 2


def scale[T: ComplexType](x: T, n: int) -> int:
  return int(x * n)


def clamp[T: RealType](lo: T, hi: T, x: T) -> T:
  if x < lo:
    return lo
  if x > hi:
    return hi
  return x


def parity[T: IntegralType](x: T) -> int:
  return int(x & 1)


class ComparableSortedTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    xs: list[int] = [3, 1, 2]
    ys: list[int] = sorted(xs)
    self.assertEqual(ys[0], 1)
    self.assertEqual(ys[2], 3)


class ArithmeticOpsTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    a: int = 7
    b: int = 3
    self.assertEqual(a % b, 1)
    self.assertEqual(a // b, 2)


class NumbersTowerTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    self.assertEqual(scale(3, 4), 12)
    self.assertEqual(clamp(0, 10, 15), 10)
    self.assertEqual(parity(7), 1)


class HashModTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    x: int = 10
    y: int = 3
    self.assertEqual(hash(x), x)
    self.assertEqual(x % y, 1)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
