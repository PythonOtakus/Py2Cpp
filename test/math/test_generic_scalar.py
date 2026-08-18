"""``py2cpp.math`` 标量泛型默认与显式特化回归。"""
from py2cpp import *
from py2cpp.math import isClose, sqrt
from py2cpp.math.complex import phase, sqrt as complexSqrt
from py2cpp.math.linalg import dot
from py2cpp.math.random import Random
from py2cpp.math.stat import LinearRegression, NormalDist, linearRegression
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class MathGenericScalarTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    root: float64 = sqrt[float64](81.0)
    self.assertTrue(isClose[float64](root, 9.0, 1e-12, 0.0))

    values: float64[:2] = [3.0, 4.0]
    self.assertTrue(isClose[float64](dot[float64](values.view, values.view), 25.0, 1e-12, 0.0))

    normal: NormalDist[float64] = new(0.0, 1.0)
    self.assertTrue(isClose[float64](normal.cdf(0.0), 0.5, 1e-12, 0.0))
    regression: LinearRegression[float64] = linearRegression[float64](values, values)
    self.assertTrue(isClose[float64](regression.slope, 1.0, 1e-12, 0.0))

    rng: Random[float64] = new()
    rng.seed(99)
    sample: float64 = rng.random()
    self.assertTrue(sample >= 0.0)
    self.assertTrue(sample < 1.0)

    rootZ: complex[float64] = complexSqrt[float64](complex[float64](-1.0, 0.0))
    self.assertTrue(isClose[float64](phase[float64](rootZ), 1.5707963267948966, 1e-12, 0.0))


def main() -> int:
  suite: TestSuite = new()
  suite.addTest(MathGenericScalarTests())
  return TextTestRunner().run(suite)