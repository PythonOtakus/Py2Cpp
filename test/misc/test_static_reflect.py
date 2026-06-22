"""编译期 ``getattr`` / ``setattr``（字面量字段名）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Holder:
  x: int = 0
  y: int = 0


def read_x(h: Holder) -> int:
  return getattr(h, "x")


def write_y(h: Holder) -> None:
  setattr(h, "y", 9)


class StaticReflectTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    h: Holder = new()
    h.x = 3
    self.assertEqual(read_x(h), 3)
    write_y(h)
    self.assertEqual(h.y, 9)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
