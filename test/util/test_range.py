"""``py2cpp.util.range``：``range`` / ``RangeIterator``（CPython 3.13 子集）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class RangeLenIterTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    self.assertEqual(len(range(10)), 10)
    n: int = 0
    for i in range(5):
      n += 1
    self.assertEqual(n, 5)
    it: RangeIterator = iter(range(4))
    self.assertEqual(next(it), 0)
    self.assertEqual(next(it), 1)


class RangePropertiesTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    r: range = range(2, 10, 3)
    self.assertTrue(r.start == 2)
    self.assertTrue(r.stop == 10)
    self.assertTrue(r.step == 3)


class RangeContainsGetitemTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    r: range = range(0, 10, 2)
    self.assertTrue(4 in r)
    self.assertFalse(5 in r)
    self.assertTrue(r[2] == 4)
    self.assertTrue(r[-1] == 8)


class RangeCountIndexTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    r: range = range(0, 10, 2)
    self.assertEqual(r.count(4), 1)
    self.assertEqual(r.count(5), 0)
    self.assertEqual(r.index(4), 2)


class RangeCompareTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    a: range = range(0, 10, 2)
    b: range = range(0, 10, 2)
    c: range = range(0, 10, 3)
    self.assertTrue(a == b)
    self.assertFalse(a != b)
    self.assertFalse(a == c)
    self.assertTrue(a != c)
    self.assertTrue(range(1, 5, 2) == range(1, 4, 2))
    self.assertFalse(range(0, 10, 2) == range(0, 11, 2))
    self.assertTrue(range(5, 5) == range(0))


class RangeReversedTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    it: RangeIterator = reversed(range(0, 10, 2))
    self.assertEqual(next(it), 8)
    self.assertEqual(next(it), 6)
    self.assertEqual(next(it), 4)


class RangeNegativeStepTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    r: range = range(10, 0, -2)
    self.assertEqual(len(r), 5)
    self.assertTrue(6 in r)
    self.assertTrue(r[1] == 8)


class RangeBoolTests(TestCaseMixin):
  _testTag = 80

  @override
  def test(self):
    self.assertFalse(range(0))
    self.assertTrue(range(1))


def main() -> int:
  suite: TestSuite = TestSuite()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
