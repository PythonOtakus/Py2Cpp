"""``math.random``：MT19937 确定性、状态往返与基本分布回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math.random import Random


class RandomReproTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    r: Random = new()
    r.seed(99)
    a: float64 = r.random()
    r.seed(99)
    b: float64 = r.random()
    self.assertTrue(a == b)


class RandomRandintRangeTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    r: Random = new()
    r.seed(7)
    v: int = r.randint(1, 6)
    self.assertTrue(v >= 1)
    self.assertTrue(v <= 6)
    w: int = r.randrange(100)
    self.assertTrue(w >= 0)
    self.assertTrue(w < 100)


class RandomGetrandbitsTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    r: Random = new()
    r.seed(3)
    b: int = r.getrandbits(8)
    self.assertTrue(b >= 0)
    self.assertTrue(b < 256)


class RandomStateRoundtripTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    r: Random = new()
    r.seed(7)
    r.random()
    st = r.getstate()
    b: float64 = r.random()
    r.setstate(st)
    c: float64 = r.random()
    self.assertTrue(b == c)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(RandomReproTests())
  suite.addTest(RandomRandintRangeTests())
  suite.addTest(RandomGetrandbitsTests())
  suite.addTest(RandomStateRoundtripTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
