"""``py2cpp.math.stat``：描述统计回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import isclose, sqrt
from py2cpp.math.stat import (
  LinearRegression,
  NormalDist,
  correlation,
  covariance,
  fmean,
  geometric_mean,
  harmonic_mean,
  linear_regression,
  mean,
  median,
  median_grouped,
  median_high,
  median_low,
  mode,
  multimode,
  pstdev,
  pvariance,
  quantiles,
  stdev,
  variance,
)

# ``isclose`` 关键字在译期未展开；字面量经 ``f`` 后缀与 ``double`` 运算结果混比时需 ``abs_tol``。
_REL: float64 = 1e-9
_ABS: float64 = 1e-6


class StatMeanMedianTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    xs: list[float64] = [1.0, 2.0, 3.0, 4.0, 4.0]
    expected_mean: float64 = 14.0 / 5.0
    self.assertTrue(isclose(mean(xs), expected_mean, _REL, _ABS))
    self.assertTrue(isclose(fmean(xs), expected_mean, _REL, _ABS))
    med_data: list[float64] = [2.0, 3.0, 4.0, 5.0]
    self.assertTrue(isclose(median(med_data), 3.5, _REL, _ABS))
    low_data: list[float64] = [1.0, 3.0, 5.0, 7.0]
    self.assertTrue(isclose(median_low(low_data), 3.0, _REL, _ABS))
    self.assertTrue(isclose(median_high(low_data), 5.0, _REL, _ABS))
    grouped: list[float64] = [2.0, 2.0, 3.0, 3.0, 3.0, 4.0]
    self.assertTrue(isclose(median_grouped(grouped), 2.8333333333333335, _REL, _ABS))


class StatModeTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    mode_data: list[int] = [1, 1, 2, 3, 3, 3, 3, 4]
    self.assertEqual(mode(mode_data), 3)
    mm_data: list[int] = [1, 1, 2, 2, 3]
    mm: list[int] = multimode(mm_data)
    self.assertEqual(len(mm), 2)


class StatSpreadTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    data: list[float64] = [2.75, 1.75, 1.25, 0.25, 0.5, 1.25, 3.5]
    self.assertTrue(isclose(variance(data), 1.3720238095238095, _REL, _ABS))
    self.assertTrue(isclose(stdev(data), sqrt(variance(data)), _REL, 0.0))
    pop: list[float64] = [0.0, 0.25, 0.25, 1.25, 1.5, 1.75, 2.75, 3.25]
    self.assertTrue(isclose(pvariance(pop), 1.25, _REL, _ABS))
    self.assertTrue(isclose(pstdev(pop), sqrt(pvariance(pop)), _REL, 0.0))


class StatMeansTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    geo: list[float64] = [54.0, 24.0, 36.0]
    self.assertTrue(isclose(geometric_mean(geo), 36.0, _REL, _ABS))
    har: list[float64] = [40.0, 60.0]
    self.assertTrue(isclose(harmonic_mean(har), 48.0, _REL, _ABS))
    weights: list[float64] = [5.0, 30.0]
    speeds: list[float64] = [40.0, 60.0]
    self.assertTrue(isclose(harmonic_mean(speeds, weights), 56.0, _REL, _ABS))


class StatQuantilesTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    q_data: list[float64] = [1.0, 2.0, 3.0, 4.0, 5.0]
    qs: list[float64] = quantiles(q_data, n=4)
    self.assertEqual(len(qs), 3)


class StatRelationTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    x: list[float64] = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    y: list[float64] = [1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0]
    self.assertTrue(isclose(covariance(x, y), 0.75, _REL, _ABS))
    self.assertTrue(isclose(correlation(x, y), 0.3162277660168379, _REL, _ABS))
    lr: LinearRegression = linear_regression(x, y)
    self.assertTrue(isclose(lr.slope, 0.1, _REL, _ABS))
    self.assertTrue(isclose(lr.intercept, 1.5, _REL, _ABS))


class StatNormalDistTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    n: NormalDist = new(0.0, 1.0)
    self.assertTrue(isclose(n.cdf(0.0), 0.5, _REL, _ABS))
    self.assertTrue(isclose(n.pdf(0.0), 0.3989422804014327, 1e-6, _ABS))
    self.assertTrue(isclose(n.inv_cdf(0.5), 0.0, _REL, 1e-6))
    samples: list[float64] = [1.0, 2.0, 3.0, 4.0, 5.0]
    fitted: NormalDist = new.from_samples(samples)
    self.assertTrue(fitted.stdev > 0.0)
    n1: NormalDist = new(2.4, 1.6)
    n2: NormalDist = new(3.2, 2.0)
    self.assertTrue(n1.overlap(n2) > 0.8)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
