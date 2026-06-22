"""``alg.sparse_table``：静态 RMQ（``__getitem__`` / 切片）。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.agg_mode import AggMode
from py2cpp.alg.sparse_table import SparseTable


class SparseTableMinTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    data: list[int] = []
    data.append(5)
    data.append(2)
    data.append(7)
    data.append(4)
    data.append(1)
    st: SparseTable = new(data, AggMode.Min)
    self.assertTrue(st[:5] == 1)
    self.assertTrue(st[1:4] == 2)
    self.assertTrue(st[2] == 7)


class SparseTableMaxTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    data: list[int] = []
    data.append(5)
    data.append(2)
    data.append(7)
    data.append(4)
    st: SparseTable = new(data, AggMode.Max)
    self.assertTrue(st[:4] == 7)
    self.assertTrue(st[:2] == 5)


class SparseTableContainsTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    data: list[int] = []
    data.append(1)
    st: SparseTable = new(data, AggMode.Min)
    self.assertTrue(0 in st)
    self.assertFalse(1 in st)
    self.assertTrue(len(st) == 1)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(SparseTableMinTests())
  suite.addTest(SparseTableMaxTests())
  suite.addTest(SparseTableContainsTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
