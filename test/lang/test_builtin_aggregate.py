"""内建 min / max / sum / any / all 译期内联回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def _neg(v: int) -> int:
  return -v


class BuiltinMinMaxTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    self.assertEqual(min(3, 1, 2), 1)
    self.assertEqual(max(3, 1, 2), 3)
    xs: list[int] = [3, 1, 4, 1]
    self.assertEqual(min(xs), 1)
    self.assertEqual(max(xs), 4)
    self.assertEqual(min(xs, key=_neg), 4)
    self.assertEqual(max(xs, key=_neg), 1)
    self.assertEqual(min(xs, default=0), 1)
    empty: list[int] = []
    self.assertEqual(min(empty, default=9), 9)
    self.assertEqual(min("bac"), ord("a"))
    self.assertEqual(max("bac"), ord("c"))
    self.assertEqual(min(range(5)), 0)
    self.assertEqual(max(range(2, 7)), 6)


class BuiltinSumTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    nums: list[int] = [1, 2, 3]
    self.assertEqual(sum(nums), 6)
    self.assertEqual(sum(range(4)), 6)
    pair: list[int] = [1, 2]
    self.assertEqual(sum(pair, 10), 13)
    acc: int = 0
    for x in range(3):
      acc += x
    self.assertEqual(sum(range(3)), acc)


class BuiltinGenExpTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    xs: list[int] = [1, 2, 3]
    ys: list[int] = [10, 20]
    self.assertEqual(sum(x * 2 for x in xs), 12)
    self.assertEqual(sum(x * y for x in xs for y in ys), 180)
    self.assertEqual(min(x for x in xs), 1)
    self.assertEqual(max(x * 2 for x in xs), 6)
    self.assertTrue(any(x > 2 for x in xs))
    self.assertFalse(all(x < 2 for x in xs))
    view: int[1:3] = [20, 30]
    self.assertEqual(sum(x for x in view), 50)


class BuiltinAnyAllTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    mix: list[int] = [0, 1, 0]
    self.assertTrue(any(mix))
    zeros: list[int] = [0, 0]
    self.assertFalse(any(zeros))
    all_pos: list[int] = [1, 2, 3]
    self.assertTrue(all(all_pos))
    has_zero: list[int] = [1, 0, 3]
    self.assertFalse(all(has_zero))
    none_left: list[int] = []
    self.assertFalse(any(none_left))
    self.assertTrue(all(none_left))
    self.assertTrue(any(range(1, 3)))
    self.assertFalse(all(range(2)))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
