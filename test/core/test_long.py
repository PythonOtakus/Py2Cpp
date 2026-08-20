"""``varint`` / 任意精度整数（``int`` 仍为 32 位 ``PyInt``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class VarIntBasicsTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    a: varint = 100
    b: varint = 23
    self.assertEqual(int(a), 100)
    self.assertEqual(int(b), 23)
    self.assertEqual(hash(a), 100)
    self.assertEqual(hash(b), 23)
    self.assertEqual(str(a), "100")
    self.assertEqual(str(b), "23")
    c: varint = a + b
    self.assertEqual(int(c), 123)
    self.assertEqual(str(c), "123")
    self.assertTrue(c > b)
    self.assertEqual(c.bitLength(), 7)


class VarIntUnaryTests(TestCaseMixin):
  _testTag = 21

  @override
  def test(self):
    z: varint = 0
    self.assertFalse(z)
    self.assertEqual(hash(z), 0)
    self.assertEqual(int(z), 0)
    self.assertEqual(str(z), "0")
    p: varint = 42
    self.assertTrue(p)
    neg: varint = -p
    self.assertEqual(int(neg), -42)
    self.assertEqual(str(neg), "-42")
    back: varint = -neg
    self.assertEqual(int(back), 42)
    pos: varint = +p
    self.assertEqual(int(pos), 42)
    absVal: varint = abs(neg)
    self.assertEqual(int(absVal), 42)
    invZ: varint = ~z
    self.assertEqual(int(invZ), -1)
    invP: varint = ~p
    self.assertEqual(int(invP), -43)
    minusOne: varint = -1
    self.assertEqual(hash(minusOne), -2)


class VarIntArithmeticTests(TestCaseMixin):
  _testTag = 22

  @override
  def test(self):
    a: varint = 7
    b: varint = 3
    three: varint = 3
    ten: varint = 10
    zero: varint = 0
    minusOne: varint = -1
    diff: varint = a - b
    self.assertEqual(int(diff), 4)
    rev: varint = b - a
    self.assertEqual(int(rev), -4)
    prod: varint = a * b
    self.assertEqual(int(prod), 21)
    q: varint = a // b
    self.assertEqual(int(q), 2)
    rem: varint = a % b
    self.assertEqual(int(rem), 1)
    powAb: varint = a ** b
    self.assertEqual(int(powAb), 343)
    powBa: varint = b ** a
    self.assertEqual(int(powBa), 2187)
    rsub: varint = three - a
    self.assertEqual(int(rsub), -4)
    rfdiv: varint = ten // a
    self.assertEqual(int(rfdiv), 1)
    rmod: varint = ten % a
    self.assertEqual(int(rmod), 3)
    negA: varint = -7
    nq: varint = negA // b
    self.assertEqual(int(nq), -3)
    nrem: varint = negA % b
    self.assertEqual(int(nrem), 2)
    self.assertEqual(a / b, 7.0 / 3.0)
    self.assertEqual(b / a, 3.0 / 7.0)
    zpow: varint = negA ** zero
    self.assertEqual(int(zpow), 1)
    npow: varint = a ** minusOne
    self.assertEqual(int(npow), 0)
    exp2: varint = 2
    mod11: varint = 11
    pm: varint = pow(a, exp2, mod11)
    self.assertEqual(int(pm), 5)
    invExp: varint = -1
    mod5: varint = 5
    base3: varint = 3
    invR: varint = pow(base3, invExp, mod5)
    self.assertEqual(int(invR), 2)


class VarIntCompareTests(TestCaseMixin):
  _testTag = 23

  @override
  def test(self):
    lo: varint = 3
    hi: varint = 5
    zero: varint = 0
    self.assertTrue(lo < hi)
    self.assertTrue(hi > lo)
    self.assertTrue(lo <= hi)
    self.assertTrue(hi >= lo)
    self.assertTrue(lo == lo)
    self.assertFalse(lo == hi)
    self.assertTrue(lo != hi)
    self.assertTrue(-hi < -lo)
    self.assertTrue(zero < lo)
    neg: varint = -2
    self.assertTrue(neg < lo)


class VarIntBitwiseTests(TestCaseMixin):
  _testTag = 24

  @override
  def test(self):
    a: varint = 12
    b: varint = 10
    two: varint = 2
    one: varint = 1
    sh10: varint = 10
    zero: varint = 0
    five: varint = 5
    three: varint = 3
    band: varint = a & b
    self.assertEqual(int(band), 8)
    bor: varint = a | b
    self.assertEqual(int(bor), 14)
    bxor: varint = a ^ b
    self.assertEqual(int(bxor), 6)
    fAnd: varint = five & three
    self.assertEqual(int(fAnd), 1)
    fOr: varint = five | three
    self.assertEqual(int(fOr), 7)
    fXor: varint = five ^ three
    self.assertEqual(int(fXor), 6)
    shl: varint = a << two
    self.assertEqual(int(shl), 48)
    shr: varint = a >> two
    self.assertEqual(int(shr), 3)
    bigShl: varint = one << sh10
    self.assertEqual(int(bigShl), 1024)
    self.assertEqual(a.bitCount(), 2)
    self.assertEqual(zero.bitCount(), 0)


class VarIntNumericApiTests(TestCaseMixin):
  _testTag = 25

  @override
  def test(self):
    v: varint = 17
    self.assertEqual(str(v), "17")
    self.assertTrue(v.isInteger())
    conj: varint = v.conjugate()
    self.assertEqual(int(conj), 17)
    num: varint = v.numerator
    self.assertEqual(int(num), 17)
    den: varint = v.denominator
    self.assertEqual(int(den), 1)
    realV: varint = v.real
    self.assertEqual(int(realV), 17)
    self.assertEqual(v.imag, 0)
    ratio: (varint, varint) = v.asIntegerRatio()
    rNum: varint = ratio[0]
    rDen: varint = ratio[1]
    self.assertEqual(int(rNum), 17)
    self.assertEqual(int(rDen), 1)


class VarIntLargeTests(TestCaseMixin):
  _testTag = 26

  @override
  def test(self):
    million: varint = 1000000
    self.assertEqual(int(million), 1000000)
    mul: varint = million * million
    self.assertEqual(str(mul), "1000000000000")


class VarIntHugeTests(TestCaseMixin):
  _testTag = 27

  @override
  def test(self):
    i64Max: varint = 9223372036854775807
    over: varint = 9223372036854775808
    self.assertEqual(str(i64Max), "9223372036854775807")
    self.assertEqual(str(over), "9223372036854775808")
    self.assertTrue(over > i64Max)
    one: varint = 1
    step: varint = i64Max + one
    self.assertEqual(str(step), "9223372036854775808")
    dec20: varint = 10000000000000000000
    self.assertEqual(str(dec20), "10000000000000000000")
    self.assertTrue(dec20 > over)
    ten: varint = 10
    mul10: varint = dec20 * ten
    self.assertEqual(str(mul10), "100000000000000000000")
    negHuge: varint = -10000000000000000000
    self.assertEqual(str(negHuge), "-10000000000000000000")
    self.assertTrue(negHuge < i64Max)
    restored: varint = -negHuge
    self.assertEqual(str(restored), "10000000000000000000")
    self.assertTrue(restored == dec20)
    exp300: varint = 300
    huge: varint = ten ** exp300
    self.assertEqual(str(huge), "1" + "0" * 300)
    mod: varint = 999999937
    rem: varint = huge % mod
    self.assertEqual(str(rem), "429485786")
    pm: varint = pow(ten, exp300, mod)
    self.assertEqual(str(pm), "429485786")
    self.assertTrue(rem == pm)
    two: varint = 2
    exp1000: varint = 1000
    big: varint = two ** exp1000
    self.assertTrue(big > huge)
    mod2: varint = 1000000007
    bigRem: varint = big % mod2
    self.assertEqual(str(bigRem), "688423210")
    bigPm: varint = pow(two, exp1000, mod2)
    self.assertEqual(str(bigPm), "688423210")
    self.assertTrue(bigRem == bigPm)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
