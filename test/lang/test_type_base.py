"""``__base__`` 类型别名：实体基类 / 根基 ``void`` / 泛型特化。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.core.exceptions import KeyError, StatisticsError


class Container[T]:
  pass


class Box[T](Container[T]):
  pass


class TypeBaseTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    k: KeyError = new()
    self.assertEqual(k.__class_id__, KeyError.__id__)
    exc_view: KeyError.__base__ = k
    se: StatisticsError = new()
    self.assertEqual(se.__class_id__, StatisticsError.__id__)
    stat_view: StatisticsError.__base__ = se
    c: Container[int] = new()
    box_view: Box[int].__base__ = c


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
