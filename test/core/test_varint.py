"""``varint`` / 任意精度整数（``int`` 仍为 32 位 ``PyInt``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class VarIntBasicsTests(TestCaseMixin):
  _test_tag = 20

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
    self.assertEqual(c.bit_length(), 7)


class VarIntUnaryTests(TestCaseMixin):
  _test_tag = 21

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
    abs_val: varint = abs(neg)
    self.assertEqual(int(abs_val), 42)
    inv_z: varint = ~z
    self.assertEqual(int(inv_z), -1)
    inv_p: varint = ~p
    self.assertEqual(int(inv_p), -43)
    minus_one: varint = -1
    self.assertEqual(hash(minus_one), -2)


class VarIntArithmeticTests(TestCaseMixin):
  _test_tag = 22

  @override
  def test(self):
    a: varint = 7
    b: varint = 3
    three: varint = 3
    ten: varint = 10
    zero: varint = 0
    minus_one: varint = -1
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
    pow_ab: varint = a ** b
    self.assertEqual(int(pow_ab), 343)
    pow_ba: varint = b ** a
    self.assertEqual(int(pow_ba), 2187)
    rsub: varint = three - a
    self.assertEqual(int(rsub), -4)
    rfdiv: varint = ten // a
    self.assertEqual(int(rfdiv), 1)
    rmod: varint = ten % a
    self.assertEqual(int(rmod), 3)
    neg_a: varint = -7
    nq: varint = neg_a // b
    self.assertEqual(int(nq), -3)
    nrem: varint = neg_a % b
    self.assertEqual(int(nrem), 2)
    self.assertEqual(a / b, 7.0 / 3.0)
    self.assertEqual(b / a, 3.0 / 7.0)
    zpow: varint = neg_a ** zero
    self.assertEqual(int(zpow), 1)
    npow: varint = a ** minus_one
    self.assertEqual(int(npow), 0)
    exp2: varint = 2
    mod11: varint = 11
    pm: varint = pow(a, exp2, mod11)
    self.assertEqual(int(pm), 5)
    inv_exp: varint = -1
    mod5: varint = 5
    base3: varint = 3
    inv_r: varint = pow(base3, inv_exp, mod5)
    self.assertEqual(int(inv_r), 2)


class VarIntCompareTests(TestCaseMixin):
  _test_tag = 23

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
  _test_tag = 24

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
    f_and: varint = five & three
    self.assertEqual(int(f_and), 1)
    f_or: varint = five | three
    self.assertEqual(int(f_or), 7)
    f_xor: varint = five ^ three
    self.assertEqual(int(f_xor), 6)
    shl: varint = a << two
    self.assertEqual(int(shl), 48)
    shr: varint = a >> two
    self.assertEqual(int(shr), 3)
    big_shl: varint = one << sh10
    self.assertEqual(int(big_shl), 1024)
    self.assertEqual(a.bit_count(), 2)
    self.assertEqual(zero.bit_count(), 0)


class VarIntNumericApiTests(TestCaseMixin):
  _test_tag = 25

  @override
  def test(self):
    v: varint = 17
    self.assertEqual(str(v), "17")
    self.assertTrue(v.is_integer())
    conj: varint = v.conjugate()
    self.assertEqual(int(conj), 17)
    num: varint = v.numerator
    self.assertEqual(int(num), 17)
    den: varint = v.denominator
    self.assertEqual(int(den), 1)
    real_v: varint = v.real
    self.assertEqual(int(real_v), 17)
    self.assertEqual(v.imag, 0)
    ratio: (varint, varint) = v.as_integer_ratio()
    r_num: varint = ratio[0]
    r_den: varint = ratio[1]
    self.assertEqual(int(r_num), 17)
    self.assertEqual(int(r_den), 1)


class VarIntLargeTests(TestCaseMixin):
  _test_tag = 26

  @override
  def test(self):
    million: varint = 1000000
    self.assertEqual(int(million), 1000000)
    mul: varint = million * million
    self.assertEqual(str(mul), "1000000000000")


class VarIntHugeTests(TestCaseMixin):
  _test_tag = 27

  @override
  def test(self):
    i64_max: varint = 9223372036854775807
    over: varint = 9223372036854775808
    self.assertEqual(str(i64_max), "9223372036854775807")
    self.assertEqual(str(over), "9223372036854775808")
    self.assertTrue(over > i64_max)
    one: varint = 1
    step: varint = i64_max + one
    self.assertEqual(str(step), "9223372036854775808")
    dec20: varint = 10000000000000000000
    self.assertEqual(str(dec20), "10000000000000000000")
    self.assertTrue(dec20 > over)
    ten: varint = 10
    mul10: varint = dec20 * ten
    self.assertEqual(str(mul10), "100000000000000000000")
    neg_huge: varint = -10000000000000000000
    self.assertEqual(str(neg_huge), "-10000000000000000000")
    self.assertTrue(neg_huge < i64_max)
    restored: varint = -neg_huge
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
    big_rem: varint = big % mod2
    self.assertEqual(str(big_rem), "688423210")
    big_pm: varint = pow(two, exp1000, mod2)
    self.assertEqual(str(big_pm), "688423210")
    self.assertTrue(big_rem == big_pm)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
