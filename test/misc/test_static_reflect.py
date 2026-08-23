"""编译期 ``getattr`` / ``setattr``（字面量字段名）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Holder:
  x: int = 0
  y: int = 0


def readX(h: Holder) -> int:
  return getattr(h, "x")


def writeY(h: Holder) -> None:
  setattr(h, "y", 9)


class StaticReflectTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    h: Holder = new(x=3)
    self.assertEqual(readX(h), 3)
    writeY(h)
    self.assertEqual(h.y, 9)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
