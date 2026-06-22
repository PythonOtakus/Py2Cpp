"""类体 ``name: T @property = new()``；``@property`` getter/setter 内 ``self.__value__``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class Holder:
  value: int @property = 0

  def bump(self) -> int:
    self.value += 1
    return self.value


class Window:
  @property
  def title(self) -> str:
    return self.__value__

  @property.setter
  def title(self, value: str) -> None:
    self.__value__ = value

  def assign_title(self, value: str) -> None:
    self.title = value


class FieldPropertyTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    h: Holder = new()
    self.assertEqual(h.value, 0)
    self.assertEqual(h.bump(), 1)
    self.assertEqual(h.value, 1)


class PropertyValueFieldTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    win: Window = new()
    self.assertEqual(win.title, "")
    win.assign_title("hello")
    self.assertEqual(win.title, "hello")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
