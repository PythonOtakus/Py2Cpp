"""``import`` / ``from … import``（绝对、相对、``*``、属性链）回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from .helper import get_import_value


class RelativeImportTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(get_import_value(), 42)


class StdlibFromImportTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    xs: list[int] = [1, 2, 3]
    self.assertEqual(len(xs), 3)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
