"""``Decimal`` 回归（P0 子集）。"""
from py2cpp import *
from py2cpp.numeric.decimal import (
  RoundingMode,
  Context,
  Decimal,
  getcontext,
  setcontext,
)
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class DecimalStrTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    a: Decimal = new("3.14")
    self.assertEqual(str(a), "3.14")
    b: Decimal = new("-0.5")
    self.assertEqual(str(b), "-0.5")
    c: Decimal = new("1e3")
    self.assertEqual(str(c), "1000")
    nan: Decimal = new("NaN")
    self.assertTrue(nan.is_nan())
    inf: Decimal = new("Infinity")
    self.assertTrue(inf.is_infinite())


class DecimalArithmeticTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    a: Decimal = new("1.5")
    b: Decimal = new("2.5")
    c: Decimal = a + b
    self.assertEqual(str(c), "4")
    d: Decimal = b - a
    self.assertEqual(str(d), "1")
    e: Decimal = a * b
    self.assertEqual(str(e.normalize()), "3.75")


class DecimalCompareTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    a: Decimal = new("1.0")
    b: Decimal = new("1.00")
    self.assertTrue(a == b)
    self.assertFalse(a < b)
    self.assertTrue(Decimal("2") > Decimal("1.99"))


class DecimalContextTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    ctx: Context = getcontext()
    self.assertEqual(ctx.prec, 28)
    self.assertEqual(ctx.rounding, int(RoundingMode.ROUND_HALF_EVEN))
    custom: Context = new(prec=10)
    setcontext(custom)
    self.assertEqual(getcontext().prec, 10)
    setcontext(ctx)


class DecimalRatioTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    d: Decimal = new("1.25")
    ratio: (varint, varint) = d.as_integer_ratio()
    self.assertEqual(int(ratio[0]), 5)
    self.assertEqual(int(ratio[1]), 4)


class DecimalQuantizeTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    x: Decimal = new("1.234")
    exp: Decimal = new("0.01")
    q: Decimal = x.quantize(exp)
    self.assertEqual(str(q), "1.23")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
