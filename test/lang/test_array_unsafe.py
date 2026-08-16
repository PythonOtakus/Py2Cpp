"""栈/堆数组 ``unsafeGet`` / ``unsafeSet``（无边界检查）。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class StackArrayUnsafeTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    buf: int[:4] = new()
    buf.unsafeSet(0, 10)
    buf.unsafeSet(1, 20)
    buf.unsafeSet(2, 30)
    buf.unsafeSet(3, 40)
    self.assertEqual(buf.unsafeGet(0), 10)
    self.assertEqual(buf.unsafeGet(1) + buf.unsafeGet(3), 60)


class StackArray2DUnsafeTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    grid: int[:2, :3] = new()
    grid.unsafeSet(0, 0, 1)
    grid.unsafeSet(0, 2, 3)
    grid.unsafeSet(1, 1, 5)
    self.assertEqual(grid.unsafeGet(0, 0), 1)
    self.assertEqual(grid.unsafeGet(0, 2), 3)
    self.assertEqual(grid.unsafeGet(1, 1), 5)


class HeapArrayUnsafeTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    arr: int[:] = new(3)
    arr.unsafeSet(0, 7)
    arr.unsafeSet(2, 9)
    self.assertEqual(arr.unsafeGet(0), 7)
    self.assertEqual(arr.unsafeGet(2), 9)


class HeapArray2DUnsafeTests(TestCaseMixin):
  _testTag = 4

  @override
  def test(self):
    mat: int[:, :] = new(2, 2)
    mat.unsafeSet(0, 1, 11)
    mat.unsafeSet(1, 0, 22)
    self.assertEqual(mat.unsafeGet(0, 1), 11)
    self.assertEqual(mat.unsafeGet(1, 0), 22)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
