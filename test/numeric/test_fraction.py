"""``Fraction[T: Integral]`` 回归（``int`` / ``varint``）。"""
from py2cpp import *
from py2cpp.numeric.fraction import Fraction
from py2cpp.numeric.ratio import float_as_integer_ratio
from py2cpp.numeric.decimal import Decimal
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
type Frac = Fraction[int]

class FractionStrTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        a: Frac = new('3/8')
        self.assertEqual(str(a), '3/8')
        self.assertEqual(int(a.numerator), 3)
        self.assertEqual(int(a.denominator), 8)
        self.assertEqual(str(Frac('-35/4')), '-35/4')
        self.assertEqual(int(Frac('314')), 314)
        self.assertEqual(str(Frac('3.1415')), '6283/2000')
        self.assertEqual(str(Frac('-47e-2')), '-47/100')

class FractionFloatTests(TestCaseMixin):
    _test_tag = 10

    @override
    def test(self):
        self.assertEqual(str(Frac(2.25)), '9/4')
        self.assertNotEqual(str(Frac(0.3)), '3/10')

class FractionFloatRatioTests(TestCaseMixin):
    _test_tag = 15

    @override
    def test(self):
        ratio: (varint, varint) = float_as_integer_ratio(1.47)
        self.assertEqual(str(ratio[0]), '6620291452234629')
        self.assertEqual(str(ratio[1]), '4503599627370496')

class FractionArithmeticTests(TestCaseMixin):
    _test_tag = 20

    @override
    def test(self):
        a: Frac = new(1, 3)
        b: Frac = new(1, 6)
        c: Frac = a + b
        self.assertEqual(str(c), '1/2')
        d: Frac = a * b
        self.assertEqual(str(d), '1/18')
        e: Frac = a / b
        self.assertEqual(str(e), '2')

class FractionDecimalTests(TestCaseMixin):
    _test_tag = 30

    @override
    def test(self):
        self.assertEqual(str(Frac(Decimal('1.47'))), '147/100')

class FractionLimitTests(TestCaseMixin):
    _test_tag = 50

    @override
    def test(self):
        pi: Frac = new('22/7')
        approx: Frac = pi.limit_denominator(10)
        self.assertEqual(str(approx), '22/7')

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
