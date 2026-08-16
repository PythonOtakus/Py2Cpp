"""``"NAME" in __macro__`` 预编译条件分派（Py2Cpp 扩展）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def platformTag() -> int:
  if "_WIN32" in __macro__:
    return 1
  elif "__linux__" in __macro__:
    return 2
  elif "_WIN32" not in __macro__:
    return 3
  else:
    return 0


class MacroIfModuleTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    tag: int = platformTag()
    if "_WIN32" in __macro__:
      self.assertEqual(tag, 1)
    elif "__linux__" in __macro__:
      self.assertEqual(tag, 2)
    elif "_WIN32" not in __macro__:
      self.assertEqual(tag, 3)
    else:
      self.assertEqual(tag, 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
