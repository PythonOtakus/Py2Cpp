"""``RangeVar`` / ``LenRangeVar`` 泛型描述符（标准库）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


class HostRange:
  level: int @RangeVar(0, 10) = 0
  rate: float @RangeVar(0.0, 1.0) = 0.5


class HostLen:
  name: str @LenRangeVar(1, 8) = "a"


def scale(x: int @RangeVar(0, 100)) -> int @RangeVar(0, 200):
  return x + x


class RangeVarIntTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    row: HostRange = new()
    row.level = 7
    self.assertEqual(row.level, 7)
    row.level = 0
    self.assertEqual(row.level, 0)
    row.level = 10
    self.assertEqual(row.level, 10)
    row.rate = 0.25
    self.assertEqual(row.rate, 0.25)


class RangeVarFloatTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    row: HostRange = new()
    row.rate = 1.0
    self.assertEqual(row.rate, 1.0)


class LenRangeVarStrTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    box: HostLen = new()
    box.name = "hello"
    self.assertEqual(box.name, "hello")
    box.name = "ab"
    self.assertEqual(len(box.name), 2)


class RangeVarFuncParamTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    self.assertEqual(scale(40), 80)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
