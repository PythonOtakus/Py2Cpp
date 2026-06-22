"""``int[:,:]``（``PyArray2D``）构造与 ``[row, col]`` 下标。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Array2dTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    grid: int[:,:] = new(2, 3)
    grid[0, 0] = 7
    grid[1, 2] = 9
    self.assertEqual(grid[0, 0], 7)
    self.assertEqual(grid[0, 1], 0)
    self.assertEqual(grid[1, 2], 9)


@copyable
class GridHolder:
  """成员嵌 ``int[:,:]``：默认构造、``__copy__``、``@immutable`` 读。"""

  def __init__(self, rows: int, cols: int):
    self._grid: int[:,:] = new(rows, cols)

  def __copy__(self, other: Self):
    self._grid.__copy__(other._grid)

  @immutable
  def get(self, r: int, c: int) -> int:
    return self._grid[r, c]

  def set(self, r: int, c: int, v: int) -> None:
    self._grid[r, c] = v


class Array2dMemberTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    a: GridHolder = new(2, 2)
    a.set(1, 0, 5)
    b: GridHolder = new(2, 2)
    b.__copy__(a)
    self.assertEqual(b.get(1, 0), 5)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
