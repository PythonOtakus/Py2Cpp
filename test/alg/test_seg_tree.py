"""``alg.seg_tree``：点修 + 区间 min/max/sum（``__getitem__`` / ``__setitem__``）。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.agg_mode import AggMode
from py2cpp.alg.seg_tree import SegTree


class SegTreeSumTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    st: SegTree = new(5, AggMode.Sum)
    for i in range(5):
      st[i] = i + 1
    self.assertTrue(st[:5] == 15)
    st[2] = 10
    self.assertTrue(st[1:4] == 2 + 10 + 4)


class SegTreeMinMaxTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    mn: SegTree = new(4, AggMode.Min)
    mx: SegTree = new(4, AggMode.Max)
    vals: list[int] = [5, 2, 7, 4]
    for i in range(4):
      mn[i] = vals[i]
      mx[i] = vals[i]
    self.assertTrue(mn[:4] == 2)
    self.assertTrue(mx[:4] == 7)
    self.assertTrue(mn[1:3] == 2)
    self.assertTrue(mn[2] == 7)


class SegTreeContainsTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    st: SegTree = new(3, AggMode.Sum)
    self.assertTrue(0 in st)
    self.assertTrue(2 in st)
    self.assertFalse(3 in st)
    self.assertTrue(len(st) == 3)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(SegTreeSumTests())
  suite.addTest(SegTreeMinMaxTests())
  suite.addTest(SegTreeContainsTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
