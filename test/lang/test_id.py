"""``id(x)`` 取对象地址。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Widget:
  def __init__(self, tag: int):
    self.tag: int = tag


def sameSlot(w: Widget) -> bool:
  return id(w) == id(w)


def copyDiffAddr(src: Widget) -> bool:
  other: Widget = src
  return id(src) != id(other)


class IdTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    w: Widget = new(Widget(1))
    self.assertTrue(sameSlot(w))
    self.assertTrue(copyDiffAddr(w))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
