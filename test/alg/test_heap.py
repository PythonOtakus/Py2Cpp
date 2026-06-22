"""``alg.heap``：``Heap`` / ``IndexedHeap``。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.heap import Heap, IndexedHeap


class HeapMinOrderTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    h: Heap[int] = new()
    h.push(3)
    h.push(1)
    h.push(2)
    self.assertTrue(h.top() == 1)
    self.assertTrue(len(h) == 3)
    self.assertTrue(bool(h))
    self.assertTrue(h.pop() == 1)
    self.assertTrue(h.pop() == 2)
    self.assertTrue(h.pop() == 3)
    self.assertFalse(bool(h))


class HeapPushPopTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    h: Heap[int] = new()
    for x in range(10, 0, -1):
      h.push(x)
    prev: int = 0
    while h:
      cur: int = h.pop()
      self.assertTrue(cur > prev)
      prev = cur


class IndexedHeapMinOrderTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    h: IndexedHeap[int] = new()
    h.push(3)
    h.push(1)
    h.push(2)
    self.assertTrue(2 in h)
    self.assertFalse(9 in h)
    self.assertTrue(h.top() == 1)
    self.assertTrue(h.pop() == 1)
    self.assertTrue(h.pop() == 2)
    self.assertTrue(h.pop() == 3)
    self.assertFalse(h)


class IndexedHeapRemoveTests(TestCaseMixin):
  _test_tag = 21

  @override
  def test(self):
    h: IndexedHeap[int] = new()
    h.push(5)
    h.push(2)
    h.push(8)
    h.remove(8)
    self.assertFalse(8 in h)
    self.assertTrue(h.top() == 2)
    h.discard(99)
    h.remove(2)
    self.assertTrue(h.top() == 5)
    self.assertTrue(len(h) == 1)


class IndexedHeapDuplicatePushTests(TestCaseMixin):
  _test_tag = 22

  @override
  def test(self):
    h: IndexedHeap[int] = new()
    h.push(1)
    h.push(1)
    self.assertTrue(len(h) == 1)


class IndexedHeapClearTests(TestCaseMixin):
  _test_tag = 23

  @override
  def test(self):
    h: IndexedHeap[int] = new()
    h.push(1)
    h.clear()
    self.assertFalse(h)
    self.assertFalse(1 in h)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(HeapMinOrderTests())
  suite.addTest(HeapPushPopTests())
  suite.addTest(IndexedHeapMinOrderTests())
  suite.addTest(IndexedHeapRemoveTests())
  suite.addTest(IndexedHeapDuplicatePushTests())
  suite.addTest(IndexedHeapClearTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
