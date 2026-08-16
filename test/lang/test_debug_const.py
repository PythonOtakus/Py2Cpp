"""``__debug__`` 编译期常量（默认构建为 ``false``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner



class DebugConstTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertFalse(__debug__)
    ran: bool = False
    if __debug__:
      ran = True
    self.assertFalse(ran)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
