"""``py2cpp.concur.parallel``：``prange`` / OpenMP / reduction。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.concur.parallel import prange


class PrangeFillTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    buf: int[:] = new(64)
    for i in prange(64):
      buf[i] = i
    self.assertTrue(buf[0] == 0)
    self.assertTrue(buf[63] == 63)


class PrangeReductionTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    total: int = 0
    for i in prange(101):
      total += i
    self.assertTrue(total == 5050)


class PrangeNegativeStepTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    total: int = 0
    for i in prange(10, 0, -2):
      total += i
    self.assertTrue(total == 30)


class PrangeScheduleTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    acc: int = 0
    for i in prange(32, schedule="dynamic", chunksize=4):
      acc += 1
    self.assertTrue(acc == 32)


class PrangeThresholdTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    buf: int[:] = new(64)
    for i in prange(64, th=10000):
      buf[i] = i
    self.assertTrue(buf[0] == 0)
    self.assertTrue(buf[63] == 63)
    total: int = 0
    for i in prange(101, th=0):
      total += i
    self.assertTrue(total == 5050)


class PrangeLenThresholdTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    s: int[:] = new(64)
    for i in prange(len(s), th=10000):
      s[i] = i
    self.assertTrue(s[0] == 0)
    self.assertTrue(s[63] == 63)
    total: int = 0
    for i in prange(len(s), th=10000):
      total += i
    self.assertTrue(total == 2016)


def main() -> int:
  suite: TestSuite = TestSuite()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
