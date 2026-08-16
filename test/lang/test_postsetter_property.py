"""``@property.postsetter`` / ``@staticproperty.postsetter`` 赋值后回调。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class PostCounter:
  lastSet: int = 0

  @property.postsetter
  def x(self, value: int) -> None:
    self.lastSet = value


class PostCounterShorthand:
  lastSet: int = 0

  def onX(self, value: int) -> None:
    self.lastSet = value

  x: int @property.postsetter(onX) = 0


class Point:
  x: int = 0
  y: int = 0

  def __init__(self, x: int = 0, y: int = 0):
    self.x = x
    self.y = y

  @staticproperty.postsetter
  def origin(value: Self) -> None:
    if value.x < 0:
      Self.__value__ = new(0, 0)
    else:
      Self.__value__ = value


class InstancePostsetterTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    c: PostCounter = new()
    self.assertEqual(c.x, 0)
    c.x = 7
    self.assertEqual(c.x, 7)
    self.assertEqual(c.lastSet, 7)


class InstancePostsetterShorthandTests(TestCaseMixin):
  _testTag = 3

  @override
  def test(self):
    c: PostCounterShorthand = new()
    self.assertEqual(c.x, 0)
    c.x = 7
    self.assertEqual(c.x, 7)
    self.assertEqual(c.lastSet, 7)


class StaticPostsetterTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    Point.origin = new(3, 4)
    self.assertEqual(Point.origin.x, 3)
    Point.origin = new(-1, 2)
    self.assertEqual(Point.origin.x, 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
