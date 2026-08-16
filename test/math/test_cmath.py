"""``py2cpp.math.complex``：``cmath`` 核心 API 回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import isClose as math_isclose
from py2cpp.math.complex import (
  asin,
  cos,
  exp,
  isClose,
  log,
  log10,
  phase,
  polar,
  rect,
  sin,
  sqrt as csqrt,
  tan,
)

_Tol: float64 = 1e-5


class CmathExpLogTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    z: complex = 1 + 1j
    w: complex = exp(z)
    self.assertTrue(isClose(w, 1.468694 + 2.287355j, _Tol, _Tol))
    ln: complex = log(w)
    self.assertTrue(isClose(ln, z, _Tol, _Tol))
    root: complex = csqrt(-1 + 0j)
    self.assertTrue(isClose(root, 1j, _Tol, _Tol))
    l10: complex = log10(100 + 0j)
    self.assertTrue(isClose(l10, 2 + 0j, _Tol, _Tol))


class CmathPolarTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    z: complex = 3 + 4j
    pr: float64 = polar(z)[0]
    ph: float64 = polar(z)[1]
    self.assertEqual(pr, 5)
    self.assertTrue(math_isclose(phase(z), ph, _Tol, _Tol))
    back: complex = rect(pr, ph)
    self.assertTrue(isClose(back, 3 + 4j, _Tol, _Tol))


class CmathTrigTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    z: complex = 0.5 + 0.25j
    s: complex = sin(z)
    c: complex = cos(z)
    ratio: complex = s / c
    self.assertTrue(isClose(ratio, tan(z), _Tol, _Tol))
    a: complex = asin(z)
    self.assertTrue(isClose(sin(a), z, _Tol, _Tol))


class CmathClassifyTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    z: complex = 1 + 2j
    self.assertTrue(complex.isFinite(z))
    self.assertFalse(complex.isInf(z))
    self.assertFalse(complex.isNaN(z))
    self.assertTrue(complex.isInf(complex.Infj))
    self.assertTrue(complex.isNaN(complex.NaNj))
    self.assertTrue(float.isNaN(float.NaN))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
