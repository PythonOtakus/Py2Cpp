"""``match`` 用户类 ``case new(kw=…)`` 模式。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@dataclass
class Point:
  x: int = 0
  y: int = 0


class Labeled:
  tag: int = 0
  value: int @property = 0


def dispatch_point(p: Point) -> int:
  match p:
    case new(x=0, y=y):
      return y
    case new(x=x, y=0):
      return x
    case new(x=x, y=y):
      return x + y
    case _:
      return -1


def dispatch_or(p: Point) -> int:
  match p:
    case new(x=1) | new(x=2):
      return 10
    case new(x=x, y=y):
      return x + y
    case _:
      return 0


def dispatch_or_reorder(p: Point) -> int:
  match p:
    case new(x=a, y=b) | new(y=b, x=a):
      return a + b
    case _:
      return 0


def dispatch_guard(p: Point) -> int:
  match p:
    case new(x=x, y=y) if x > y:
      return 1
    case new(x=x, y=y):
      return 0
    case _:
      return -1


def dispatch_labeled(h: Labeled) -> int:
  match h:
    case new(value=0, tag=t):
      return t
    case new(value=v):
      return v
    case _:
      return -1


class MatchNewPointTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    origin: Point = new(x=0, y=0)
    self.assertEqual(dispatch_point(origin), 0)
    on_axis: Point = new(x=0, y=5)
    self.assertEqual(dispatch_point(on_axis), 5)
    other: Point = new(x=2, y=3)
    self.assertEqual(dispatch_point(other), 5)
    one: Point = new(x=1, y=9)
    self.assertEqual(dispatch_or(one), 10)
    two: Point = new(x=2, y=3)
    self.assertEqual(dispatch_or(two), 10)
    other_or: Point = new(x=3, y=4)
    self.assertEqual(dispatch_or(other_or), 7)
    reorder: Point = new(x=2, y=5)
    self.assertEqual(dispatch_or_reorder(reorder), 7)
    gt: Point = new(x=3, y=1)
    self.assertEqual(dispatch_guard(gt), 1)
    le: Point = new(x=1, y=2)
    self.assertEqual(dispatch_guard(le), 0)


class MatchNewPropertyTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    zero: Labeled = new(tag=0)
    self.assertEqual(dispatch_labeled(zero), 0)
    tagged: Labeled = new(tag=5)
    self.assertEqual(dispatch_labeled(tagged), 5)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
