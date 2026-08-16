"""容器回归：``deque``。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

class DequeLiteralTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    dq: deque[int] = [10, 20, 30]
    self.assertEqual(len(dq), 3)
    self.assertEqual(dq[0], 10)
    self.assertEqual(dq[2], 30)


class DequeCompTests(TestCaseMixin):
  _testTag = 15

  @override
  def test(self):
    src: list[int] = [1, 2, 3]
    dq: deque[int] = [x * 2 for x in src]
    self.assertEqual(len(dq), 3)
    self.assertEqual(dq[0], 2)
    self.assertEqual(dq[2], 6)


class DequeMethodsTests(TestCaseMixin):
  """对齐 Python 3.13 ``collections.deque`` 双端与查询方法。"""

  _testTag = 20

  @override
  def test(self):
    d: deque[int] = []
    d.append(1)
    d.append(2)
    d.appendLeft(0)
    self.assertEqual(len(d), 3)
    self.assertEqual(d[0], 0)
    self.assertEqual(d[2], 2)
    self.assertEqual(d.popLeft(), 0)
    self.assertEqual(d.pop(), 2)
    self.assertEqual(len(d), 1)
    other: deque[int] = [3, 4]
    d.extend(other)
    self.assertEqual(len(d), 3)
    self.assertEqual(d[1], 3)
    left: deque[int] = [10, 20]
    d.extendLeft(left)
    self.assertEqual(d[0], 20)
    self.assertEqual(d[1], 10)
    self.assertEqual(d.count(4), 1)
    self.assertEqual(d.index(10), 1)
    d.insert(2, 99)
    self.assertEqual(d[2], 99)
    d.remove(99)
    self.assertFalse(99 in d)
    snap: deque[int] = d.copy()
    self.assertEqual(len(snap), len(d))
    self.assertEqual(snap[0], d[0])
    seq: deque[int] = [1, 2, 3]
    seq.reverse()
    self.assertEqual(seq[0], 3)
    self.assertEqual(seq[2], 1)
    seq.rotate(1)
    self.assertEqual(seq[0], 1)
    self.assertEqual(seq[1], 3)
    self.assertEqual(seq[2], 2)
    revSum: int = 0
    for x in reversed(seq):
      revSum += x
    self.assertEqual(revSum, 6)
    bounded: deque[int] = new(2)
    bounded.append(1)
    bounded.append(2)
    bounded.append(3)
    self.assertEqual(len(bounded), 2)
    self.assertEqual(bounded[0], 2)
    bounded.appendLeft(0)
    self.assertEqual(len(bounded), 2)
    self.assertEqual(bounded[0], 0)
    self.assertEqual(bounded[1], 2)
    cat: deque[int] = seq + other
    self.assertEqual(len(cat), 5)
    dup: deque[int] = seq * 2
    self.assertEqual(len(dup), 6)
    seq.clear()
    self.assertEqual(len(seq), 0)



def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
