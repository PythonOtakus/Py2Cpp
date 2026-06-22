"""``py2cpp.math.complex``：``cmath`` 核心 API 回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import isclose as math_isclose
from py2cpp.math.complex import (
  asin,
  cos,
  exp,
  isclose,
  log,
  log10,
  phase,
  polar,
  rect,
  sin,
  sqrt as csqrt,
  tan,
)

_TOL: float64 = 1e-5


class CmathExpLogTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    z: complex = 1 + 1j
    w: complex = exp(z)
    self.assertTrue(isclose(w, 1.468694 + 2.287355j, _TOL, _TOL))
    ln: complex = log(w)
    self.assertTrue(isclose(ln, z, _TOL, _TOL))
    root: complex = csqrt(-1 + 0j)
    self.assertTrue(isclose(root, 1j, _TOL, _TOL))
    l10: complex = log10(100 + 0j)
    self.assertTrue(isclose(l10, 2 + 0j, _TOL, _TOL))


class CmathPolarTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    z: complex = 3 + 4j
    pr: float64 = polar(z)[0]
    ph: float64 = polar(z)[1]
    self.assertEqual(pr, 5)
    self.assertTrue(math_isclose(phase(z), ph, _TOL, _TOL))
    back: complex = rect(pr, ph)
    self.assertTrue(isclose(back, 3 + 4j, _TOL, _TOL))


class CmathTrigTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    z: complex = 0.5 + 0.25j
    s: complex = sin(z)
    c: complex = cos(z)
    ratio: complex = s / c
    self.assertTrue(isclose(ratio, tan(z), _TOL, _TOL))
    a: complex = asin(z)
    self.assertTrue(isclose(sin(a), z, _TOL, _TOL))


class CmathClassifyTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    z: complex = 1 + 2j
    self.assertTrue(complex.isfinite(z))
    self.assertFalse(complex.isInf(z))
    self.assertFalse(complex.isNaN(z))
    self.assertTrue(complex.isInf(complex.Infj))
    self.assertTrue(complex.isNaN(complex.NaNj))
    self.assertTrue(float.isNaN(float.NaN))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
