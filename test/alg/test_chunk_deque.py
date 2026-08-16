"""``alg.chunk_deque.ChunkDeque``：双端队列、``splice``/``extend``/``insert``、迭代。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.chunk_deque import ChunkDeque


class ChunkDequeAppendPopTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    dq: ChunkDeque[int] = new(4)
    dq.append(1)
    dq.append(2)
    dq.appendLeft(0)
    self.assertTrue(len(dq) == 3)
    self.assertTrue(dq.popLeft() == 0)
    self.assertTrue(dq.pop() == 2)
    self.assertTrue(dq.pop() == 1)
    self.assertFalse(dq)


class ChunkDequeGetItemTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    dq: ChunkDeque[int] = new(2)
    for i in range(5):
      dq.append(i)
    self.assertTrue(dq[0] == 0)
    self.assertTrue(dq[4] == 4)
    self.assertTrue(dq[2] == 2)


class ChunkDequeClearTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    dq: ChunkDeque[int] = new()
    dq.append(7)
    dq.clear()
    self.assertFalse(dq)


class ChunkDequeContainsDelTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    dq: ChunkDeque[int] = new(2)
    dq.append(1)
    dq.append(2)
    dq.append(3)
    self.assertTrue(2 in dq)
    self.assertFalse(9 in dq)
    del dq[1]
    self.assertTrue(len(dq) == 2)
    self.assertTrue(dq[0] == 1)
    self.assertTrue(dq[1] == 3)


class ChunkDequeSpliceTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    seq: ChunkDeque[int] = new(3)
    for i in range(7):
      seq.append(i)
    right: ChunkDeque[int] = seq.splice(4)
    self.assertTrue(len(seq) == 4)
    self.assertTrue(seq[0] == 0)
    self.assertTrue(seq[3] == 3)
    self.assertTrue(len(right) == 3)
    self.assertTrue(right[0] == 4)
    self.assertTrue(right[2] == 6)


class ChunkDequeExtendTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    left: ChunkDeque[int] = new(2)
    right: ChunkDeque[int] = new(2)
    left.append(1)
    left.append(2)
    right.append(3)
    right.append(4)
    left.extend(right)
    right.clear()
    self.assertTrue(len(left) == 4)
    self.assertTrue(left[0] == 1)
    self.assertTrue(left[3] == 4)
    self.assertFalse(right)


class ChunkDequeInsertPopTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    seq: ChunkDeque[int] = new(2)
    seq.append(1)
    seq.append(3)
    seq.insert(1, 2)
    self.assertTrue(len(seq) == 3)
    self.assertTrue(seq[1] == 2)
    self.assertTrue(seq.pop(1) == 2)
    self.assertTrue(len(seq) == 2)
    self.assertTrue(seq[0] == 1)
    self.assertTrue(seq[1] == 3)


class ChunkDequeSetItemTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    seq: ChunkDeque[int] = new(2)
    for i in range(4):
      seq.append(i)
    seq[2] = 9
    self.assertTrue(seq[2] == 9)
    self.assertTrue(seq[0] == 0)
    self.assertTrue(seq[3] == 3)


class ChunkDequeIterTests(TestCaseMixin):
  _testTag = 80

  @override
  def test(self):
    seq: ChunkDeque[int] = new(2)
    seq.append(5)
    seq.append(6)
    flat: list[int] = []
    for x in seq:
      flat.append(x)
    self.assertTrue(len(flat) == 2)
    self.assertTrue(flat[0] == 5)
    self.assertTrue(flat[1] == 6)


class ChunkDequeReversedTests(TestCaseMixin):
  _testTag = 90

  @override
  def test(self):
    seq: ChunkDeque[int] = new(2)
    for i in range(4):
      seq.append(i)
    rev: list[int] = []
    for x in reversed(seq):
      rev.append(x)
    self.assertTrue(len(rev) == 4)
    self.assertTrue(rev[0] == 3)
    self.assertTrue(rev[3] == 0)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(ChunkDequeAppendPopTests())
  suite.addTest(ChunkDequeGetItemTests())
  suite.addTest(ChunkDequeClearTests())
  suite.addTest(ChunkDequeContainsDelTests())
  suite.addTest(ChunkDequeSpliceTests())
  suite.addTest(ChunkDequeExtendTests())
  suite.addTest(ChunkDequeInsertPopTests())
  suite.addTest(ChunkDequeSetItemTests())
  suite.addTest(ChunkDequeIterTests())
  suite.addTest(ChunkDequeReversedTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
