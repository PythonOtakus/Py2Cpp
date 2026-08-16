"""并行多目标赋值 ``a, b, c = b, c, a + b`` 与下标交换。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class ParallelAssignIntTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    a: int = 1
    b: int = 2
    c: int = 3
    a, b, c = b, c, a + b
    self.assertTrue(a == 2)
    self.assertTrue(b == 3)
    self.assertTrue(c == 3)


class ParallelAssignSwapTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    xs: list[int] = []
    xs.append(10)
    xs.append(20)
    xs[0], xs[1] = xs[1], xs[0]
    self.assertTrue(xs[0] == 20)
    self.assertTrue(xs[1] == 10)


def main() -> int:
  suite: TestSuite = TestSuite()
  suite.addTest(ParallelAssignIntTests())
  suite.addTest(ParallelAssignSwapTests())
  runner: TextTestRunner = TextTestRunner()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
