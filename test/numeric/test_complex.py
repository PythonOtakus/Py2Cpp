"""``py2cpp.numeric.complex``：复数字面量与算术。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class ComplexLiteralTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    j: complex = 1.25j
    self.assertEqual(j.real, 0)
    self.assertEqual(j.imag, 1.25)
    z: complex = 3 + 4j
    self.assertEqual(z.real, 3)
    self.assertEqual(z.imag, 4)
    w: complex = -2.5j
    self.assertEqual(w.real, 0)
    self.assertEqual(w.imag, -2.5)
    c128: complex[float64] = 1.5j
    self.assertEqual(c128.imag, 1.5)


class ComplexArithmeticTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    a: complex = 1 + 2j
    b: complex = 3 - 4j
    s: complex = a + b
    self.assertEqual(s.real, 4)
    self.assertEqual(s.imag, -2)
    d: complex = a - b
    self.assertEqual(d.real, -2)
    self.assertEqual(d.imag, 6)
    p: complex = a * b
    self.assertEqual(p.real, 11)
    self.assertEqual(p.imag, 2)
    q: complex = a / b
    self.assertTrue(q.real > -0.25 and q.real < -0.15)
    self.assertTrue(q.imag > 0.38 and q.imag < 0.42)
    cj: complex = a.conjugate()
    self.assertEqual(cj.real, 1)
    self.assertEqual(cj.imag, -2)
    self.assertTrue(a)
    zero: complex = 0j
    self.assertFalse(zero)
    sq: complex = (1 + 1j) ** 2
    self.assertEqual(sq.real, 0)
    self.assertEqual(sq.imag, 2)
    mixed: complex = 1j + 2
    self.assertEqual(mixed.real, 2)
    self.assertEqual(mixed.imag, 1)
    rev: complex = 2 + 1j
    self.assertEqual(rev.real, 2)
    self.assertEqual(rev.imag, 1)
    sm: complex = 2 * (1 + 1j)
    self.assertEqual(sm.real, 2)
    self.assertEqual(sm.imag, 2)
    rpow: complex = 2 ** (1 + 1j)
    self.assertTrue(rpow.real > 1.45 and rpow.real < 1.62)
    self.assertTrue(rpow.imag > 1.2 and rpow.imag < 1.35)
    tri: complex = 3 + 4j
    self.assertEqual(abs(tri), 5)
    realOnly: complex = 7 + 0j
    self.assertEqual(abs(realOnly), 7)
    self.assertEqual(float(realOnly), 7.0)
    c128: complex[float64] = 3 + 4j
    self.assertEqual(abs(c128), 5)
    self.assertEqual(int(realOnly), 7)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
