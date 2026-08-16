"""``alg.fen_tree``：泛型 BIT、``__getitem__`` / ``__setitem__``、``add``。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.fen_tree import FenTree


class FenTreePrefixTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    bit: FenTree[int] = new(5)
    bit.add(0, 3)
    bit.add(2, 5)
    bit.add(4, 2)
    self.assertTrue(bit[:1] == 3)
    self.assertTrue(bit[:3] == 8)
    self.assertTrue(bit[:5] == 10)


class FenTreeRangeTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    bit: FenTree[int] = new(6)
    for i in range(6):
      bit.add(i, i + 1)
    self.assertTrue(bit[1:4] == 2 + 3 + 4)
    self.assertTrue(bit[:6] == 21)


class FenTreeGetSetTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    bit: FenTree[int] = new(4)
    bit.add(1, 7)
    self.assertTrue(bit[1] == 7)
    bit[2] = 5
    self.assertTrue(bit[2] == 5)
    self.assertTrue(bit[:3] == 12)


class FenTreeSliceTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    bit: FenTree[int] = new(6)
    for i in range(6):
      bit[i] = i + 1
    self.assertTrue(bit[1:4] == 2 + 3 + 4)
    self.assertTrue(bit[:6] == 21)
    self.assertTrue(bit[3:3] == 0)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(FenTreePrefixTests())
  suite.addTest(FenTreeRangeTests())
  suite.addTest(FenTreeGetSetTests())
  suite.addTest(FenTreeSliceTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())

