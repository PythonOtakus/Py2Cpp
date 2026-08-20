"""``long`` / 任意精度整数（``int`` 仍为 32 位 ``PyInt``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class LongBasicsTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    a: long = 100
    b: long = 23
    self.assertEqual(int(a), 100)
    self.assertEqual(int(b), 23)
    self.assertEqual(hash(a), 100)
    self.assertEqual(hash(b), 23)
    self.assertEqual(str(a), "100")
    self.assertEqual(str(b), "23")
    c: long = a + b
    self.assertEqual(int(c), 123)
    self.assertEqual(str(c), "123")
    self.assertTrue(c > b)
    self.assertEqual(c.bitLength(), 7)


class LongUnaryTests(TestCaseMixin):
  _testTag = 21

  @override
  def test(self):
    z: long = 0
    self.assertFalse(z)
    self.assertEqual(hash(z), 0)
    self.assertEqual(int(z), 0)
    self.assertEqual(str(z), "0")
    p: long = 42
    self.assertTrue(p)
    neg: long = -p
    self.assertEqual(int(neg), -42)
    self.assertEqual(str(neg), "-42")
    back: long = -neg
    self.assertEqual(int(back), 42)
    pos: long = +p
    self.assertEqual(int(pos), 42)
    absVal: long = abs(neg)
    self.assertEqual(int(absVal), 42)
    invZ: long = ~z
    self.assertEqual(int(invZ), -1)
    invP: long = ~p
    self.assertEqual(int(invP), -43)
    minusOne: long = -1
    self.assertEqual(hash(minusOne), -2)


class LongArithmeticTests(TestCaseMixin):
  _testTag = 22

  @override
  def test(self):
    a: long = 7
    b: long = 3
    three: long = 3
    ten: long = 10
    zero: long = 0
    minusOne: long = -1
    diff: long = a - b
    self.assertEqual(int(diff), 4)
    rev: long = b - a
    self.assertEqual(int(rev), -4)
    prod: long = a * b
    self.assertEqual(int(prod), 21)
    q: long = a // b
    self.assertEqual(int(q), 2)
    rem: long = a % b
    self.assertEqual(int(rem), 1)
    powAb: long = a ** b
    self.assertEqual(int(powAb), 343)
    powBa: long = b ** a
    self.assertEqual(int(powBa), 2187)
    rsub: long = three - a
    self.assertEqual(int(rsub), -4)
    rfdiv: long = ten // a
    self.assertEqual(int(rfdiv), 1)
    rmod: long = ten % a
    self.assertEqual(int(rmod), 3)
    negA: long = -7
    nq: long = negA // b
    self.assertEqual(int(nq), -3)
    nrem: long = negA % b
    self.assertEqual(int(nrem), 2)
    self.assertEqual(a / b, 7.0 / 3.0)
    self.assertEqual(b / a, 3.0 / 7.0)
    zpow: long = negA ** zero
    self.assertEqual(int(zpow), 1)
    npow: long = a ** minusOne
    self.assertEqual(int(npow), 0)
    exp2: long = 2
    mod11: long = 11
    pm: long = pow(a, exp2, mod11)
    self.assertEqual(int(pm), 5)
    invExp: long = -1
    mod5: long = 5
    base3: long = 3
    invR: long = pow(base3, invExp, mod5)
    self.assertEqual(int(invR), 2)


class LongCompareTests(TestCaseMixin):
  _testTag = 23

  @override
  def test(self):
    lo: long = 3
    hi: long = 5
    zero: long = 0
    self.assertTrue(lo < hi)
    self.assertTrue(hi > lo)
    self.assertTrue(lo <= hi)
    self.assertTrue(hi >= lo)
    self.assertTrue(lo == lo)
    self.assertFalse(lo == hi)
    self.assertTrue(lo != hi)
    self.assertTrue(-hi < -lo)
    self.assertTrue(zero < lo)
    neg: long = -2
    self.assertTrue(neg < lo)


class LongBitwiseTests(TestCaseMixin):
  _testTag = 24

  @override
  def test(self):
    a: long = 12
    b: long = 10
    two: long = 2
    one: long = 1
    sh10: long = 10
    zero: long = 0
    five: long = 5
    three: long = 3
    band: long = a & b
    self.assertEqual(int(band), 8)
    bor: long = a | b
    self.assertEqual(int(bor), 14)
    bxor: long = a ^ b
    self.assertEqual(int(bxor), 6)
    fAnd: long = five & three
    self.assertEqual(int(fAnd), 1)
    fOr: long = five | three
    self.assertEqual(int(fOr), 7)
    fXor: long = five ^ three
    self.assertEqual(int(fXor), 6)
    shl: long = a << two
    self.assertEqual(int(shl), 48)
    shr: long = a >> two
    self.assertEqual(int(shr), 3)
    bigShl: long = one << sh10
    self.assertEqual(int(bigShl), 1024)
    self.assertEqual(a.bitCount(), 2)
    self.assertEqual(zero.bitCount(), 0)


class LongNumericApiTests(TestCaseMixin):
  _testTag = 25

  @override
  def test(self):
    v: long = 17
    self.assertEqual(str(v), "17")
    self.assertTrue(v.isInteger())
    conj: long = v.conjugate()
    self.assertEqual(int(conj), 17)
    num: long = v.numerator
    self.assertEqual(int(num), 17)
    den: long = v.denominator
    self.assertEqual(int(den), 1)
    realV: long = v.real
    self.assertEqual(int(realV), 17)
    self.assertEqual(v.imag, 0)
    ratio: (long, long) = v.asIntegerRatio()
    rNum: long = ratio[0]
    rDen: long = ratio[1]
    self.assertEqual(int(rNum), 17)
    self.assertEqual(int(rDen), 1)


class LongLargeTests(TestCaseMixin):
  _testTag = 26

  @override
  def test(self):
    million: long = 1000000
    self.assertEqual(int(million), 1000000)
    mul: long = million * million
    self.assertEqual(str(mul), "1000000000000")


class LongHugeTests(TestCaseMixin):
  _testTag = 27

  @override
  def test(self):
    i64Max: long = 9223372036854775807
    over: long = 9223372036854775808
    self.assertEqual(str(i64Max), "9223372036854775807")
    self.assertEqual(str(over), "9223372036854775808")
    self.assertTrue(over > i64Max)
    one: long = 1
    step: long = i64Max + one
    self.assertEqual(str(step), "9223372036854775808")
    dec20: long = 10000000000000000000
    self.assertEqual(str(dec20), "10000000000000000000")
    self.assertTrue(dec20 > over)
    ten: long = 10
    mul10: long = dec20 * ten
    self.assertEqual(str(mul10), "100000000000000000000")
    negHuge: long = -10000000000000000000
    self.assertEqual(str(negHuge), "-10000000000000000000")
    self.assertTrue(negHuge < i64Max)
    restored: long = -negHuge
    self.assertEqual(str(restored), "10000000000000000000")
    self.assertTrue(restored == dec20)
    exp300: long = 300
    huge: long = ten ** exp300
    self.assertEqual(str(huge), "1" + "0" * 300)
    mod: long = 999999937
    rem: long = huge % mod
    self.assertEqual(str(rem), "429485786")
    pm: long = pow(ten, exp300, mod)
    self.assertEqual(str(pm), "429485786")
    self.assertTrue(rem == pm)
    two: long = 2
    exp1000: long = 1000
    big: long = two ** exp1000
    self.assertTrue(big > huge)
    mod2: long = 1000000007
    bigRem: long = big % mod2
    self.assertEqual(str(bigRem), "688423210")
    bigPm: long = pow(two, exp1000, mod2)
    self.assertEqual(str(bigPm), "688423210")
    self.assertTrue(bigRem == bigPm)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
