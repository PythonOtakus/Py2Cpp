"""``T[:R, :C]`` 栈二维、``span2d`` 视图与 ``int[:,:]`` 堆 ``view``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.util.span import span2d


class StackArray2dBasicTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    grid: int[:2, :3] = [[1, 2, 3], [4, 5, 6]]
    self.assertEqual(grid[0, 0], 1)
    self.assertEqual(grid[1, 2], 6)
    grid[0, 1] = 9
    self.assertEqual(grid[0, 1], 9)
    grid.fill(7)
    self.assertEqual(grid[0, 0], 7)
    self.assertEqual(grid[1, 2], 7)


class StackArray2dViewTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    grid: int[:2, :3] = new()
    grid[0, 0] = 10
    grid[0, 1] = 20
    grid[1, 2] = 30
    vw: span2d[int] = grid.view
    self.assertEqual(vw[0, 0], 10)
    sub: span2d[int] = vw[0:2, 1:3]
    self.assertEqual(sub[0, 0], 20)
    self.assertEqual(sub[0, 1], 0)
    sub[0, 0] = 55
    self.assertEqual(grid[0, 1], 55)
    sub.fill(88)
    self.assertEqual(grid[0, 1], 88)
    self.assertEqual(grid[1, 2], 88)


class StackArray2dHeapSliceTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    grid: int[:2, :3] = [[1, 2, 3], [4, 5, 6]]
    patch: int[:, :] = grid[0:2, 1:3]
    self.assertEqual(patch[0, 0], 2)
    self.assertEqual(patch[1, 1], 6)
    grid[0, 1] = 99
    self.assertEqual(patch[0, 0], 2)


class Array2dViewTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    heap: int[:, :] = new(2, 3)
    heap[0, 0] = 7
    heap[1, 2] = 9
    vw: span2d[int] = heap.view
    self.assertEqual(vw[0, 0], 7)
    self.assertEqual(vw[1, 2], 9)
    vw[1, 2] = 11
    self.assertEqual(heap[1, 2], 11)
    heap.fill(42)
    self.assertEqual(heap[0, 0], 42)
    self.assertEqual(heap[1, 2], 42)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
