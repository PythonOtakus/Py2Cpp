"""``__base__`` 类型别名：实体基类 / 根基 ``void`` / 泛型特化。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.exceptions import KeyError, StatisticsError


class ContainerType[Element]:
  pass


class Box[Element](ContainerType[Element]):
  pass


class TypeBaseTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    k: KeyError = new()
    self.assertEqual(k.__class_id__, KeyError.__id__)
    excView: KeyError.__base__ = k
    se: StatisticsError = new()
    self.assertEqual(se.__class_id__, StatisticsError.__id__)
    statView: StatisticsError.__base__ = se
    boxView: Box[int].__base__ = new()


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
