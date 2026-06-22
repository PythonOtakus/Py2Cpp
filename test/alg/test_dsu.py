"""``alg.dsu``：并查集 ``__getitem__`` / ``__setitem__`` / ``has`` / ``count``。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.dsu import DSU


class DsuBasicTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    dsu: DSU = new(5)
    dsu[0] = 1
    self.assertTrue(dsu.has(0, 1))
    dsu[0] = 1
    dsu[2] = 3
    self.assertFalse(dsu.has(0, 2))
    dsu[1] = 2
    self.assertTrue(dsu.has(0, 3))
    self.assertTrue(dsu.count(0) == 4)
    self.assertTrue(dsu.count(4) == 1)


class DsuFindTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    dsu: DSU = new(3)
    dsu[0] = 1
    r0: int = dsu[0]
    r1: int = dsu[1]
    self.assertTrue(r0 == r1)


class DsuContainsTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    dsu: DSU = new(3)
    self.assertTrue(0 in dsu)
    self.assertTrue(2 in dsu)
    self.assertFalse(3 in dsu)
    self.assertFalse(-1 in dsu)


class DsuLenBoolTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    empty: DSU = new(0)
    self.assertFalse(empty)
    self.assertFalse(bool(empty))
    dsu: DSU = new(5)
    self.assertTrue(len(dsu) == 5)
    self.assertTrue(bool(dsu))


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(DsuBasicTests())
  suite.addTest(DsuFindTests())
  suite.addTest(DsuContainsTests())
  suite.addTest(DsuLenBoolTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
