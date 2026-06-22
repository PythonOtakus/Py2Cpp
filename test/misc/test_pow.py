"""全局 ``pow`` / 模幂（含 ``pow(3, -1, 5)`` 逆元）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class PowIntTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    self.assertEqual(pow(2, 10), 1024)
    self.assertEqual(pow(3, 2, 5), 4)
    self.assertEqual(pow(3, -1, 5), 2)
    self.assertEqual(pow(7, 0, 13), 1)
    self.assertEqual(pow(10, 100, 1000), 0)


class PowVarintTests(TestCaseMixin):
  _test_tag = 11

  @override
  def test(self):
    a: varint = 3
    m: varint = 5
    exp2: varint = 2
    inv: varint = -1
    r1: varint = pow(a, exp2, m)
    self.assertEqual(int(r1), 4)
    r2: varint = pow(a, inv, m)
    self.assertEqual(int(r2), 2)
    b: varint = 7
    mod13: varint = 13
    zero: varint = 0
    r3: varint = pow(b, zero, mod13)
    self.assertEqual(int(r3), 1)
    base: varint = 10
    exp100: varint = 100
    big_mod: varint = 1000
    r4: varint = pow(base, exp100, big_mod)
    self.assertEqual(int(r4), 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
