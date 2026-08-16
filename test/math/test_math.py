"""``py2cpp.math``：常量、libm 与纯 Python 组合回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import (
  comb,
  degrees,
  dist,
  factorial,
  fsum,
  gcd,
  hypot,
  isClose,
  isqrt,
  lcm,
  perm,
  pi,
  prod,
  radians,
  sin,
  sqrt,
)


class MathConstantsTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertTrue(pi > 3.14)
    self.assertTrue(pi < 3.15)


class MathScalarAttrTests(TestCaseMixin):
  _testTag = 5

  @override
  def test(self):
    self.assertTrue(float64.isInf(float64.Inf))
    self.assertTrue(float.isNaN(float.NaN))
    self.assertTrue(float64.isFinite(1.0))
    self.assertEqual(int.Min, -2147483648)
    self.assertEqual(int.Max, 2147483647)
    self.assertTrue(int64.Min < 0)
    self.assertTrue(uint.Min == 0)
    self.assertTrue(uint64.Max > 0)


class MathSqrtTrigTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    self.assertEqual(sqrt(9.0), 9.0 ** 0.5)
    s: float64 = sin(radians(90.0))
    self.assertTrue(isClose(s, 1.0, relTol=1e-12))


class MathHypotDistTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    self.assertEqual(hypot(3.0, 4.0), 5.0)
    p: list[float64] = [0.0, 0.0]
    q: list[float64] = [3.0, 4.0]
    self.assertEqual(dist(p, q), 5.0)


class MathIntegerTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    self.assertEqual(factorial(5), 120)
    self.assertEqual(gcd(48, 18), 6)
    self.assertEqual(lcm(12, 18), 36)
    self.assertEqual(isqrt(10), 3)
    self.assertEqual(comb(5, 2), 10)
    self.assertEqual(perm(5, 3), 60)
    self.assertEqual(perm(5), 120)


class MathAggregateTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    xs: list[float64] = [1.0, 2.0, 3.0, 4.0]
    self.assertEqual(prod(xs), 24.0)
    self.assertEqual(fsum(xs), 10.0)


class MathDegreesTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    self.assertTrue(isClose(degrees(pi), 180.0))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
