"""``id(x)`` 取对象地址。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Widget:
  def __init__(self, tag: int):
    self.tag: int = tag


def same_slot(w: Widget) -> bool:
  return id(w) == id(w)


def copy_diff_addr(src: Widget) -> bool:
  other: Widget = src
  return id(src) != id(other)


class IdTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    w: Widget = new(Widget(1))
    self.assertTrue(same_slot(w))
    self.assertTrue(copy_diff_addr(w))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
