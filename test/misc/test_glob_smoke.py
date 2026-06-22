"""``str.glob`` / ``bytes.glob`` 冒烟（隔离栈/堆问题）。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class StrGlobSmokeTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertTrue("readme.txt".glob("*.txt"))


class BytesGlobSmokeTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    self.assertTrue(b"readme.txt".glob(b"*.txt"))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
