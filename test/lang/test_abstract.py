"""``@abstract`` 纯虚方法与抽象类 ``new()`` 约束。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Shape:
  @abstract
  def area(self) -> int:
    ...


class Rect(Shape):
  w: int
  h: int

  def __init__(self, w: int, h: int):
    self.w = w
    self.h = h

  @override
  def area(self) -> int:
    return self.w * self.h


class Poly(Shape):
  @abstract
  @override
  def area(self) -> int:
    ...


class Square(Poly):
  side: int

  def __init__(self, side: int):
    self.side = side

  @override
  def area(self) -> int:
    return self.side * self.side


class AbstractTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    r: Rect = new(3, 4)
    self.assertEqual(r.area(), 12)
    s: Square = new(5)
    self.assertEqual(s.area(), 25)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
