"""``Decimal`` 回归（P0 子集）。"""
from py2cpp import *
from py2cpp.numeric.decimal import RoundingModeEnum, Context, Decimal, getContext, setContext
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

class DecimalStrTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        self.assertEqual(str(Decimal('3.14')), '3.14')
        self.assertEqual(str(Decimal('-0.5')), '-0.5')
        self.assertEqual(str(Decimal('1e3')), '1000')
        nan: Decimal = new('NaN')
        self.assertTrue(nan.isNan())
        inf: Decimal = new('Infinity')
        self.assertTrue(inf.isInfinite())

class DecimalArithmeticTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        a: Decimal = new('1.5')
        b: Decimal = new('2.5')
        c: Decimal = a + b
        self.assertEqual(str(c), '4')
        d: Decimal = b - a
        self.assertEqual(str(d), '1')
        e: Decimal = a * b
        self.assertEqual(str(e.normalize()), '3.75')

class DecimalCompareTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        a: Decimal = new('1.0')
        b: Decimal = new('1.00')
        self.assertTrue(a == b)
        self.assertFalse(a < b)
        self.assertTrue(Decimal('2') > Decimal('1.99'))

class DecimalContextTests(TestCaseMixin):
    _testTag = 30

    @override
    def test(self):
        ctx: Context = getContext()
        self.assertEqual(ctx.prec, 28)
        self.assertEqual(ctx.rounding, int(RoundingModeEnum.RoundHalfEven))
        setContext(Context(prec=10))
        self.assertEqual(getContext().prec, 10)
        setContext(ctx)

class DecimalRatioTests(TestCaseMixin):
    _testTag = 40

    @override
    def test(self):
        d: Decimal = new('1.25')
        ratio: (varint, varint) = d.asIntegerRatio()
        self.assertEqual(int(ratio[0]), 5)
        self.assertEqual(int(ratio[1]), 4)

class DecimalQuantizeTests(TestCaseMixin):
    _testTag = 50

    @override
    def test(self):
        x: Decimal = new('1.234')
        q: Decimal = x.quantize(Decimal('0.01'))
        self.assertEqual(str(q), '1.23')

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
