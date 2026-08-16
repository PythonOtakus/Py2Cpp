"""``chr`` / ``ord`` 与 ``byte`` 集成回归。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class ChrOrdTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(chr(65), "A")
    self.assertEqual(chr(0x4e2d), "\u4e2d")
    c: char = 65
    self.assertEqual(int(c), 65)
    b: byte = 65
    self.assertEqual(int(b), 65)
    s: str = "Z"
    self.assertEqual(int(s[0]), 90)
    self.assertEqual(ord("Z"), ord("Z"))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
