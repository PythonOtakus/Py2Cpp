from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
"""``@protocol`` 约束：``Comparable`` / ``Arithmetic`` / ``numbers`` 塔（应编译通过）。"""


def sorted[T: Comparable](s: list[T]) -> list[T]:
  out: list[T] = []
  out.extend(s)
  out.sort()
  return out


def half[T: Arithmetic](x: T) -> float:
  return x / 2


def scale[T: Complex](x: T, n: int) -> int:
  return int(x * n)


def clamp[T: Real](lo: T, hi: T, x: T) -> T:
  if x < lo:
    return lo
  if x > hi:
    return hi
  return x


def parity[T: Integral](x: T) -> int:
  return int(x & 1)


class ComparableSortedTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    xs: list[int] = [3, 1, 2]
    ys: list[int] = sorted(xs)
    self.assertEqual(ys[0], 1)
    self.assertEqual(ys[2], 3)


class ArithmeticOpsTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    a: int = 7
    b: int = 3
    self.assertEqual(a % b, 1)
    self.assertEqual(a // b, 2)


class NumbersTowerTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    self.assertEqual(scale(3, 4), 12)
    self.assertEqual(clamp(0, 10, 15), 10)
    self.assertEqual(parity(7), 1)


class HashModTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    x: int = 10
    y: int = 3
    self.assertEqual(hash(x), x)
    self.assertEqual(x % y, 1)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
