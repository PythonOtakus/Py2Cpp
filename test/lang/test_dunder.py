"""``__name__`` / ``__file__`` / ``__line__`` 回归（``test/lang/``）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class DunderModuleTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(__name__, "__main__")
    self.assertTrue(__file__)
    self.assertTrue(__file__.endsWith(".py"))
    self.assertGreater(__line__, 0)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
