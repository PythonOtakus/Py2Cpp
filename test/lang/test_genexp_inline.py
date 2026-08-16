"""``IterableType[int]`` 形参 + genexp 实参：调用点内联集成测。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def total(xs: IterableType[int], start: int = 0) -> int:
  acc: int = start
  for x in xs:
    acc += x
  return acc


class GenexpInlineTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    data: list[int] = [1, 2, 3]
    self.assertEqual(total(data), 6)
    self.assertEqual(total(x * 2 for x in data), 12)
    plain: int = 0
    for x in data:
      plain += x
    self.assertEqual(plain, 6)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
