"""``py2cpp.math.stat``：描述统计回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import isClose, sqrt
from py2cpp.math.stat import LinearRegression, NormalDist, correlation, covariance, fmean, geometricMean, harmonicMean, linearRegression, mean, median, medianGrouped, medianHigh, medianLow, mode, multiMode, pstdev, pvariance, quantiles, stdev, variance
_Rel: float64 = 1e-09
_Abs: float64 = 1e-06

class StatMeanMedianTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        xs: list[float64] = [1.0, 2.0, 3.0, 4.0, 4.0]
        expectedMean: float64 = 14.0 / 5.0
        self.assertTrue(isClose(mean(xs), expectedMean, _Rel, _Abs))
        self.assertTrue(isClose(fmean(xs), expectedMean, _Rel, _Abs))
        medData: list[float64] = [2.0, 3.0, 4.0, 5.0]
        self.assertTrue(isClose(median(medData), 3.5, _Rel, _Abs))
        lowData: list[float64] = [1.0, 3.0, 5.0, 7.0]
        self.assertTrue(isClose(medianLow(lowData), 3.0, _Rel, _Abs))
        self.assertTrue(isClose(medianHigh(lowData), 5.0, _Rel, _Abs))
        grouped: list[float64] = [2.0, 2.0, 3.0, 3.0, 3.0, 4.0]
        self.assertTrue(isClose(medianGrouped(grouped), 2.8333333333333335, _Rel, _Abs))

class StatModeTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        modeData: list[int] = [1, 1, 2, 3, 3, 3, 3, 4]
        self.assertEqual(mode(modeData), 3)
        mmData: list[int] = [1, 1, 2, 2, 3]
        mm: list[int] = multiMode(mmData)
        self.assertEqual(len(mm), 2)

class StatSpreadTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        data: list[float64] = [2.75, 1.75, 1.25, 0.25, 0.5, 1.25, 3.5]
        self.assertTrue(isClose(variance(data), 1.3720238095238095, _Rel, _Abs))
        self.assertTrue(isClose(stdev(data), sqrt(variance(data)), _Rel, 0.0))
        pop: list[float64] = [0.0, 0.25, 0.25, 1.25, 1.5, 1.75, 2.75, 3.25]
        self.assertTrue(isClose(pvariance(pop), 1.25, _Rel, _Abs))
        self.assertTrue(isClose(pstdev(pop), sqrt(pvariance(pop)), _Rel, 0.0))

class StatMeansTests(TestCaseMixin):
    _testTag = 30

    @override
    def test(self):
        geo: list[float64] = [54.0, 24.0, 36.0]
        self.assertTrue(isClose(geometricMean(geo), 36.0, _Rel, _Abs))
        har: list[float64] = [40.0, 60.0]
        self.assertTrue(isClose(harmonicMean(har), 48.0, _Rel, _Abs))
        weights: list[float64] = [5.0, 30.0]
        speeds: list[float64] = [40.0, 60.0]
        self.assertTrue(isClose(harmonicMean(speeds, weights), 56.0, _Rel, _Abs))

class StatQuantilesTests(TestCaseMixin):
    _testTag = 40

    @override
    def test(self):
        qData: list[float64] = [1.0, 2.0, 3.0, 4.0, 5.0]
        qs: list[float64] = quantiles(qData, n=4)
        self.assertEqual(len(qs), 3)

class StatRelationTests(TestCaseMixin):
    _testTag = 50

    @override
    def test(self):
        x: list[float64] = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        y: list[float64] = [1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0]
        self.assertTrue(isClose(covariance(x, y), 0.75, _Rel, _Abs))
        self.assertTrue(isClose(correlation(x, y), 0.3162277660168379, _Rel, _Abs))
        lr: LinearRegression = linearRegression(x, y)
        self.assertTrue(isClose(lr.slope, 0.1, _Rel, _Abs))
        self.assertTrue(isClose(lr.intercept, 1.5, _Rel, _Abs))

class StatNormalDistTests(TestCaseMixin):
    _testTag = 60

    @override
    def test(self):
        n: NormalDist = new(0.0, 1.0)
        self.assertTrue(isClose(n.cdf(0.0), 0.5, _Rel, _Abs))
        self.assertTrue(isClose(n.pdf(0.0), 0.3989422804014327, 1e-06, _Abs))
        self.assertTrue(isClose(n.invCdf(0.5), 0.0, _Rel, 1e-06))
        samples: list[float64] = [1.0, 2.0, 3.0, 4.0, 5.0]
        fitted: NormalDist = new.fromSamples(samples)
        self.assertTrue(fitted.stdev > 0.0)
        n1: NormalDist = new(2.4, 1.6)
        self.assertTrue(n1.overlap(NormalDist(3.2, 2.0)) > 0.8)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
