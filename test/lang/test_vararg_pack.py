"""``*args: T[:]`` 整包 ``PyArray<T>``：空调用、多实参、定参交错 ``*pack``、``*args`` 转发。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def sum_vararg(*nums: int[:]) -> int:
  total: int = 0
  for x in nums:
    total += x
  return total


def head_plus_count(first: int, *rest: int[:]) -> int:
  return first + len(rest)


def pack_len(*nums: int[:]) -> int:
  return len(nums)


def forward_all(*nums: int[:]) -> int:
  return pack_len(*nums)


def forward_with_head(first: int, *rest: int[:]) -> int:
  return first + pack_len(*rest)


def pack_sum(*nums: int[:]) -> int:
  total: int = 0
  for x in nums:
    total += x
  return total


def as_pack(*nums: int[:]) -> int[:]:
  return nums


def interleave_packs(a: int[:], b: int[:]) -> int:
  return pack_sum(3, *a, 4, *b, 5)


def interleave_with_head(first: int, *rest: int[:]) -> int:
  return pack_sum(first, *rest)


class VarargEmptyPackTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(sum_vararg(), 0)


class VarargThreeValuesTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    self.assertEqual(sum_vararg(1, 2, 3), 6)


class VarargHeadAndRestTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    self.assertEqual(head_plus_count(5, 1, 2), 7)


class VarargForwardWholePackTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    self.assertEqual(forward_all(1, 2, 3), 3)


class VarargForwardWithHeadTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    self.assertEqual(forward_with_head(10, 1, 2), 12)


class VarargInterleaveStarredPacksTests(TestCaseMixin):
  _test_tag = 6

  @override
  def test(self):
    left: int[:] = as_pack(1, 2)
    right: int[:] = as_pack(7)
    self.assertEqual(interleave_packs(left, right), 22)


class VarargInterleaveScalarAndStarTests(TestCaseMixin):
  _test_tag = 7

  @override
  def test(self):
    mid: int[:] = as_pack(2, 3)
    self.assertEqual(interleave_with_head(10, *mid, 4), 19)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
