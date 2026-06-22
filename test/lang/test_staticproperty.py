"""``@staticproperty`` / ``@staticproperty.setter``；``Self.__value__`` 存储字段。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@copyable
class Point:
  x: int = 0
  y: int = 0

  def __init__(self, x: int = 0, y: int = 0):
    self.x = x
    self.y = y

  @staticproperty
  def origin() -> Self:
    return Self.__value__

  @staticproperty.setter
  def origin(value: Self) -> None:
    Self.__value__ = value


class StaticPropertyReadTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    p: Point = Point.origin
    self.assertEqual(p.x, 0)
    self.assertEqual(p.y, 0)
    q: Point = new(3, 4)
    self.assertEqual(q.x, 3)


class StaticPropertyWriteTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    fresh: Point = new(9, 8)
    Point.origin = fresh
    p: Point = Point.origin
    self.assertEqual(p.x, 9)
    self.assertEqual(p.y, 8)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
