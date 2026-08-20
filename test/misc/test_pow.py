"""全局 ``pow`` / 模幂（含 ``pow(3, -1, 5)`` 逆元）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class PowIntTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    self.assertEqual(pow(2, 10), 1024)
    self.assertEqual(pow(3, 2, 5), 4)
    self.assertEqual(pow(3, -1, 5), 2)
    self.assertEqual(pow(7, 0, 13), 1)
    self.assertEqual(pow(10, 100, 1000), 0)


class PowLongTests(TestCaseMixin):
  _testTag = 11

  @override
  def test(self):
    a: long = 3
    m: long = 5
    exp2: long = 2
    inv: long = -1
    r1: long = pow(a, exp2, m)
    self.assertEqual(int(r1), 4)
    r2: long = pow(a, inv, m)
    self.assertEqual(int(r2), 2)
    b: long = 7
    mod13: long = 13
    zero: long = 0
    r3: long = pow(b, zero, mod13)
    self.assertEqual(int(r3), 1)
    base: long = 10
    exp100: long = 100
    bigMod: long = 1000
    r4: long = pow(base, exp100, bigMod)
    self.assertEqual(int(r4), 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
