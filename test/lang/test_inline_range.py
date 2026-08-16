"""``inlineRange`` 集成：``@mixin`` 矩阵 ``Self._dim`` 定长循环。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.spatial.matrix import Matrix3


class InlineRangeMatrixTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    m: Matrix3 = Matrix3.identity
    self.assertTrue(m[0, 0] == 1.0)
    self.assertTrue(m[1, 1] == 1.0)
    inv: Matrix3 = m.inv
    self.assertTrue(inv[0, 0] == 1.0)
    prod: Matrix3 = m @ inv
    self.assertTrue(prod == Matrix3.identity)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
