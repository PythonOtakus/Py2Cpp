"""``@protocol`` 内 ``@staticmethod`` + ``@virtual``/``@abstract`` 与泛型 ``T.method()`` 派发。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@protocol
class IParsableType:
  @staticmethod
  @abstract
  def parse(s: str) -> Self: ...


@protocol
class INamedType:
  @staticmethod
  @virtual
  def tag() -> str:
    return ""


class Widget:
  value: int

  def __init__(self, v: int = 0):
    self.value = v

  @staticmethod
  @override
  def parse(s: str) -> Self:
    return new(int(s))


class Labeled:
  label: str

  def __init__(self, label: str = ""):
    self.label = label

  @staticmethod
  @override
  def parse(s: str) -> Self:
    return new(s)

  @staticmethod
  @override
  def tag() -> str:
    return "labeled"


def tryParse[T: IParsableType](s: str) -> T:
  return T.parse(s)


def readTag[T: INamedType]() -> str:
  return T.tag()


class StaticVirtualTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    w: Widget = tryParse[Widget]("42")
    self.assertEqual(w.value, 42)
    lb: Labeled = tryParse[Labeled]("hello")
    self.assertEqual(lb.label, "hello")
    self.assertEqual(readTag[Labeled](), "labeled")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
