"""栈/堆数组 ``unsafe_get`` / ``unsafe_set``（无边界检查）。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class StackArrayUnsafeTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    buf: int[:4] = new()
    buf.unsafe_set(0, 10)
    buf.unsafe_set(1, 20)
    buf.unsafe_set(2, 30)
    buf.unsafe_set(3, 40)
    self.assertEqual(buf.unsafe_get(0), 10)
    self.assertEqual(buf.unsafe_get(1) + buf.unsafe_get(3), 60)


class StackArray2DUnsafeTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    grid: int[:2, :3] = new()
    grid.unsafe_set(0, 0, 1)
    grid.unsafe_set(0, 2, 3)
    grid.unsafe_set(1, 1, 5)
    self.assertEqual(grid.unsafe_get(0, 0), 1)
    self.assertEqual(grid.unsafe_get(0, 2), 3)
    self.assertEqual(grid.unsafe_get(1, 1), 5)


class HeapArrayUnsafeTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    arr: int[:] = new(3)
    arr.unsafe_set(0, 7)
    arr.unsafe_set(2, 9)
    self.assertEqual(arr.unsafe_get(0), 7)
    self.assertEqual(arr.unsafe_get(2), 9)


class HeapArray2DUnsafeTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    mat: int[:, :] = new(2, 2)
    mat.unsafe_set(0, 1, 11)
    mat.unsafe_set(1, 0, 22)
    self.assertEqual(mat.unsafe_get(0, 1), 11)
    self.assertEqual(mat.unsafe_get(1, 0), 22)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
